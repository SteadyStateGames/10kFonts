"""Build the original Steady State Games font-root experiments (OFL-1.1).

python -m pip install -r requirements.txt
python build.py

No installed fonts, remote assets, or third-party outlines enter the build.
"""
from pathlib import Path
import hashlib
import html
import json
import math
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
# Optional local dependency cache used in this workspace; a venv also works.
CACHE = ROOT.parent / ('.font-build-deps314' if sys.version_info[:2] == (3,14) else '.font-build-deps')
if CACHE.exists():
    sys.path.insert(0, str(CACHE))

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.basePen import BasePen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import affinity
from PIL import Image, ImageDraw, ImageFont
from sources.glyphs import GLYPHS, PIXELS, ANGULAR

RECIPES = json.loads((ROOT / 'sources/roots.json').read_text('utf-8'))
LICENSE = (ROOT / 'OFL.txt').read_text('utf-8')
OUT = ROOT / 'fonts'
OUT.mkdir(exist_ok=True)
(ROOT / 'downloads').mkdir(exist_ok=True)


class FlattenPen(BasePen):
    def __init__(self):
        super().__init__(None)
        self.paths = []
        self.points = []

    def _moveTo(self, p):
        self.points = [p]

    def _lineTo(self, p):
        self.points.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.points[-1]
        for i in range(1, 25):
            t = i / 24
            u = 1-t
            self.points.append(tuple(u**3*p0[k]+3*u*u*t*p1[k]+3*u*t*t*p2[k]+t**3*p3[k] for k in (0,1)))

    def _qCurveToOne(self, p1, p2):
        p0 = self.points[-1]
        for i in range(1, 17):
            t = i / 16
            self.points.append(tuple((1-t)**2*p0[k]+2*(1-t)*t*p1[k]+t*t*p2[k] for k in (0,1)))

    def _closePath(self):
        self.points.append(self.points[0])
        self._endPath()

    def _endPath(self):
        if len(self.points) > 1:
            self.paths.append(self.points)
        self.points = []


def paths_for(ch, mode):
    drawings = ANGULAR.get(ch, GLYPHS[ch]) if mode == 'angular' else GLYPHS[ch]
    pen = FlattenPen()
    for d in drawings:
        parse_path(d, pen)
    return pen.paths


def make_geometry(ch, recipe):
    mode = recipe['mode']
    weight = recipe['weight']
    if recipe.get('optical_symbols') and ch in ('@','%','&'):
        # Dense symbols need finer strokes to keep their internal spaces.
        weight = min(weight,(68 if ch=='@' else 90)*recipe.get('path_width',1))
    paths = paths_for(ch, mode)
    # Optional centerline fit keeps the pen/stroke thickness unchanged.
    yscale, yshift = recipe.get('centerline_y', (1, 0))
    if (yscale, yshift) != (1, 0):
        paths = [[(x, y*yscale+yshift) for x,y in pts] for pts in paths]
    if recipe.get('path_width'):
        paths = [[(x*recipe['path_width'], y) for x,y in pts] for pts in paths]
    if mode in ('pixel', 'dots') and ch.upper() in PIXELS:
        pieces = []
        for y, row in enumerate(PIXELS[ch.upper()].split('/')):
            for x, bit in enumerate(row):
                if bit == '1':
                    px, py = (x*100+50)*recipe.get('path_width',1), (6-y)*100+50
                    radius = recipe.get('cell_radius',36 if mode=='dots' else 50)
                    pieces.append(affinity.scale(Point(px, py).buffer(radius, quad_segs=8),xfact=recipe.get('path_width',1),yfact=1,origin=(px,py)) if mode == 'dots' else box(px-radius*recipe.get('path_width',1), py-radius, px+radius*recipe.get('path_width',1), py+radius))
        shape = unary_union(pieces)
    elif mode in ('serif', 'nib'):
        # Sweep a thin horizontal nib. Vertical strokes are heavier than
        # horizontals. Nib roots use an angled parallelogram footprint.
        pieces = []
        for pts in paths:
            if LineString(pts).length <= 12:
                pieces.append(Point(pts[0]).buffer(weight*0.42,quad_segs=8))
                continue
            for a,b in zip(pts, pts[1:]):
                thin = recipe.get('hairline',12)
                nib = [(-weight/2,-thin),(weight/2,-thin),(weight/2,thin),(-weight/2,thin)]
                if mode == 'nib':
                    nib = [(-weight/2,-20),(weight/2,12),(weight/2,35),(-weight/2,3)]
                    nib = [(nx,ny*recipe.get('nib_height_scale',1)) for nx,ny in nib]
                pieces.append(Polygon([(p[0]+x,p[1]+y) for p in (a,b) for x,y in nib]).convex_hull)
        shape = unary_union(pieces)
    else:
        cap = 1 if mode in ('round','rail','outline','dots') else 2
        join = 1 if mode in ('round','rail','outline') else 2
        lines = [LineString(p) for p in paths]
        shape = unary_union([Point(p.coords[0]).buffer(weight/2,quad_segs=8) if p.length<=12 else p.buffer(weight/2, cap_style=cap, join_style=join, quad_segs=8,mitre_limit=recipe.get('miter_limit',5)) for p in lines])
        if mode == 'rail':
            inner = unary_union([p.buffer(weight*0.17, cap_style=1, join_style=1, quad_segs=8) for p in lines])
            shape = shape.difference(inner)
        elif mode == 'outline':
            wall = recipe.get('outline_thickness',24)
            if recipe.get('optical_symbols') and ch in ('@','%','&'):
                wall = min(wall,weight*.22)
            shape = shape.difference(shape.buffer(-wall, join_style=1))
        elif mode == 'stencil' and ch.isalnum():
            # Horizontal stencil bridges. Keep periods and accents intact.
            gap = recipe.get('stencil_gap',33)
            cut = box(-200, 322-gap/2, 1800, 322+gap/2)
            shape = shape.difference(cut)
        elif mode in ('dots','pixel'):
            # Punctuation is sampled from the centerline drawing on a 60-unit
            # grid; intersecting cells ensure small punctuation survives.
            cells = []
            xmin,ymin,xmax,ymax = shape.bounds
            for x in range(math.floor(xmin/60),math.ceil(xmax/60)):
                for y in range(math.floor(ymin/60),math.ceil(ymax/60)):
                    cell = box(x*60,y*60,x*60+60,y*60+60)
                    if shape.intersection(cell).area > 650:
                        cells.append(Point(x*60+30,y*60+30).buffer(22,quad_segs=6) if mode == 'dots' else cell)
            shape = unary_union(cells) if cells else shape

    if mode in ('serif','slab'):
        serifs = []
        depth = 15 if mode == 'serif' else 27
        extension = 94 if mode == 'serif' else 83
        for pts in paths:
            if pts[0] == pts[-1] or LineString(pts).length <= 12:
                continue
            for endpoint, near in ((pts[0],pts[1]),(pts[-1],pts[-2])):
                x,y = endpoint
                if abs((near[1]-y)/yscale) > abs(near[0]-x)*2 and any(abs(y-(anchor*yscale+yshift)) < .001 for anchor in (0,480,700,-200)):
                    serifs.append(box(x-extension,y-depth,x+extension,y+depth))
        shape = unary_union([shape]+serifs)
    shape = affinity.scale(shape, xfact=recipe['width'], yfact=1, origin=(0,0))
    if recipe.get('slant'):
        shape = affinity.affine_transform(shape,[1,recipe['slant'],0,1,0,0])
    shape = shape.simplify(0.5, preserve_topology=True)
    if not shape.is_valid and recipe.get('repair_affine_contacts'):
        # Affine transforms of touching grid cells can introduce numerical
        # self-contacts. A zero-distance cleanup restores their polygon union.
        shape = shape.buffer(0)
    if not shape.is_valid:
        raise ValueError(f'Invalid outline: {recipe["name"]} {ch!r}')
    return shape


def to_glyph(shape):
    pen = TTGlyphPen(None)
    if not shape.is_empty:
        polygons = [shape] if shape.geom_type == 'Polygon' else list(shape.geoms)
        for poly in polygons:
            if poly.geom_type != 'Polygon':
                continue
            # TrueType: clockwise outside, counterclockwise holes.
            poly = orient(poly, sign=-1)
            for ring in [poly.exterior] + list(poly.interiors):
                points = []
                for x,y in list(ring.coords)[:-1]:
                    pt = (round(x),round(y))
                    if not points or pt != points[-1]:
                        points.append(pt)
                if len(set(points)) < 3:
                    continue
                pen.moveTo(points[0])
                for pt in points[1:]:
                    pen.lineTo(pt)
                pen.closePath()
    return pen.glyph()


GLYPHS.update({
'\u2013':['M0 260 L500 260'], '\u2014':['M0 260 L850 260'],
'\u2018':['M80 730 L0 610'], '\u2019':['M80 700 L0 580'],
'\u201c':['M80 730 L0 610','M250 730 L170 610'],
'\u201d':['M80 700 L0 580','M250 700 L170 580'],
'\u2026':['M0 0 L0 8','M180 0 L180 8','M360 0 L360 8'],
'\u2022':['M0 300 L0 315'], '\u2212':['M0 300 L430 300'],
'\u2190':['M500 300 L0 300 L180 480','M0 300 L180 120'],
'\u2192':['M0 300 L500 300 L320 480','M500 300 L320 120']
})
CHARS = sorted(set(GLYPHS) | {' ','\u00a0'}, key=ord)


def build_font(recipe):
    family = recipe['name']
    style = recipe.get('style','Italic' if recipe.get('slant') else 'Regular')
    stem = family.replace(' ','') + '-' + style.replace(' ','')
    folder = OUT / recipe['id']
    folder.mkdir(exist_ok=True)
    cmap = {ord(ch):f'uni{ord(ch):04X}' for ch in CHARS}
    order = ['.notdef']+list(cmap.values())
    glyphs = {'.notdef':to_glyph(box(60,0,510,700).difference(box(110,50,460,650)))}
    metrics = {'.notdef':(570,60)}
    shapes = {}
    for ch in CHARS:
        name = cmap[ord(ch)]
        if ch in (' ','\u00a0'):
            glyphs[name] = TTGlyphPen(None).glyph()
            metrics[name] = (320,0)
            continue
        shape = make_geometry(ch,recipe)
        assert not shape.is_empty, (family,ch)
        xmin,ymin,xmax,ymax = shape.bounds
        side, right_side = recipe.get('sidebearings', {}).get(ch, (recipe['tracking'], recipe['tracking']))
        shape = affinity.translate(shape,xoff=side-xmin)
        glyphs[name] = to_glyph(shape)
        metrics[name] = (round(xmax-xmin+side+right_side),side)
        shapes[ch] = shape
    fb = FontBuilder(1000,isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    descent = recipe.get('descent',350)
    ascent = 950
    if recipe.get('auto_vertical_metrics'):
        for glyph in fb.font['glyf'].glyphs.values():
            if glyph.numberOfContours:
                glyph.recalcBounds(fb.font['glyf'])
                ascent=max(ascent,glyph.yMax)
                descent=max(descent,-glyph.yMin)
    fb.setupHorizontalHeader(ascent=ascent,descent=-descent,lineGap=0)
    fb.setupNameTable({
        'familyName':family+' '+style if recipe.get('style') else family,
        'styleName':'Regular' if recipe.get('style') else style,
        'typographicFamily':family, 'typographicSubfamily':style,
        'uniqueFontIdentifier':f'SSG:{recipe.get("version","0.100")}:{stem}',
        'fullName':family+' '+style, 'psName':stem,
        'version':'Version '+recipe.get('version','0.100'),
        'copyright':'Copyright (c) 2026, Steady State Games.',
        'manufacturer':'Steady State Games',
        'designer':'Steady State Games with OpenAI Codex',
        'description':recipe['description']+' Experimental display font.' if recipe.get('version') else recipe['description']+' Experimental display root, version 0.1.',
        'licenseDescription':LICENSE,
        'licenseInfoURL':'https://openfontlicense.org'
    })
    fb.setupOS2(sTypoAscender=ascent,sTypoDescender=-descent,sTypoLineGap=0,
                usWinAscent=ascent,usWinDescent=descent,usWeightClass=recipe.get('weight_class',400),
                usWidthClass=recipe.get('width_class',3 if recipe['width']<0.8 else 5),
                sxHeight=recipe.get('x_height',700 if recipe['mode'] in ('dots','pixel') else 480),
                sCapHeight=700,fsSelection=0x81 if recipe.get('slant') else 0xC0,achVendID='SSG ',version=4)
    fb.setupPost(italicAngle=-math.degrees(math.atan(recipe.get('slant',0))))
    fb.setupMaxp()
    fb.font['head'].macStyle = 2 if recipe.get('slant') else 0
    # Small initial pair set. Full optical spacing remains a release milestone.
    if recipe['mode'] not in ('pixel','dots','outline','rail'):
        pairs = ['AV','AW','AY','AT','FA','LT','LV','LY','PA','TA','TO','Ta','Te','To','Tr','Tu','VA','Va','Ve','Vo','WA','Wa','We','Wo','YA','Ya','Ye','Yo']
        amount = round(-30*recipe['width'])
        features = 'languagesystem DFLT dflt; languagesystem latn dflt; feature kern {\n'
        kerns = recipe.get('kerning_pairs', {pair:amount for pair in pairs})
        features += '\n'.join(f'pos {cmap[ord(pair[0])]} {cmap[ord(pair[1])]} {value};' for pair,value in kerns.items())
        features += '\n} kern;'
        addOpenTypeFeaturesFromString(fb.font,features)
    # Fixed OpenType epoch timestamp: byte-identical rebuilds in pinned runtime.
    fb.font['head'].created = fb.font['head'].modified = 3871584000
    fb.font.recalcTimestamp = False
    ttf = folder / (stem+'.ttf')
    fb.font.save(ttf)
    webfont = TTFont(ttf,recalcTimestamp=False)
    webfont.flavor = 'woff2'
    # Standard WOFF2 null transforms retain the original TrueType tables;
    # compression still uses Brotli. Avoid transform round-trip instability
    # observed in this Windows build environment on large batches.
    from fontTools.ttLib.woff2 import WOFF2FlavorData
    webfont.flavorData = WOFF2FlavorData(transformedTables=set())
    woff = folder / (stem+'.woff2')
    webfont.save(woff)
    webfont.close()
    (folder/'OFL.txt').write_text(LICENSE,encoding='utf-8')
    coverage = 'Unicase: lowercase inputs use capital forms.' if recipe['mode'] in ('dots','pixel') else 'Separate uppercase and lowercase drawings.'
    (folder/'FONTLOG.txt').write_text(f'{family} {style} {recipe.get('version','0.100')}\n2026-09-06: Experimental procedural display style.\n{coverage}\nOriginal procedural SSG drawings; no third-party font outlines.\nASCII, nonbreaking space, curly quotes, dashes, ellipsis, bullet, minus and horizontal arrows.\nNo Reserved Font Names are declared.\n',encoding='utf-8')
    archive = ROOT/'downloads'/f'{stem}.zip'
    write_zip(archive, [(p,p.name) for p in sorted(folder.iterdir())])
    result = dict(recipe,ttf=ttf.relative_to(ROOT).as_posix(),woff2=woff.relative_to(ROOT).as_posix(),
                  download=archive.relative_to(ROOT).as_posix(),coverage=coverage,
                  codepoints=len(cmap),ttf_bytes=ttf.stat().st_size,woff2_bytes=woff.stat().st_size,
                  sha256=hashlib.sha256(ttf.read_bytes()).hexdigest())
    validate(ttf,woff,cmap,shapes)
    return result


def write_zip(path, files):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for source, name in files:
            info = zipfile.ZipInfo(name,date_time=(2026,9,6,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info,source.read_bytes())


def validate(ttf,woff,cmap,shapes):
    for path in (ttf,woff):
        with TTFont(path,checkChecksums=2,recalcTimestamp=False) as font:
            assert font.getBestCmap() == cmap
            assert font['name'].getDebugName(13) == LICENSE
            for tag in font.keys():
                if tag != 'GlyphOrder':
                    _ = font[tag]  # Force all lazy tables to decompile.
            for code,name in cmap.items():
                glyph = font['glyf'][name]
                assert font['hmtx'][name][0] > 0
                if code not in (32,160):
                    assert glyph.numberOfContours > 0, (path,code)
                    assert -font['OS/2'].usWinDescent <= glyph.yMin <= glyph.yMax <= font['OS/2'].usWinAscent,(path,code)
    # Exercise the native FreeType renderer independently of fontTools.
    face = ImageFont.truetype(str(ttf),64)
    for ch in CHARS:
        if not ch.isspace():
            assert face.getmask(ch).getbbox(), (ttf,ch)


def specimen(manifest):
    faces = '\n'.join(f'@font-face{{font-family:"{r["name"]}";src:url("{r["woff2"]}") format("woff2");font-display:swap;}}' for r in manifest)
    cards = []
    for i,r in enumerate(manifest,1):
        cards.append(f'''<article><div class="meta"><span>{i:02d} / {html.escape(r['name'])}</span><span>ROOT 0.1 · OFL</span></div>
<p class="sample" style="font-family:'{r['name']}'" data-default="{r['sample']}">{r['sample']}</p>
<p class="alphabet" style="font-family:'{r['name']}'">Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm<br>0123456789 — “Hello, world!”</p>
<p>{html.escape(r['description'])}</p><div class="card-footer"><span>{r['coverage']}</span><a href="{r['download']}" download>Download font + license ↗</a></div></article>''')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Steady State Games — Font roots</title><style>FACES
:root{--ink:#21332e;--paper:#f4f1e7;--orange:#bb492b}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}main{max-width:1240px;margin:auto;padding:32px 40px 70px}nav{display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid #a9b4aa;padding-bottom:22px;font-size:12px;font-weight:700;letter-spacing:.13em}h1{font:clamp(42px,6vw,80px)/1.02 Georgia,serif;font-weight:normal;letter-spacing:-.045em;margin:50px 0 22px;max-width:800px}.intro{max-width:730px;font-size:19px}.eyebrow{color:var(--orange);font-size:12px;letter-spacing:.15em;font-weight:750}a{color:var(--ink);text-underline-offset:4px}a:hover{color:var(--orange)}.license{background:#dfe6d8;border-left:4px solid #506347;padding:19px 24px;margin:30px 0}.license p{margin:6px 0}.controls{display:flex;gap:24px;flex-wrap:wrap;align-items:end;margin:34px 0 26px}label{font-size:13px;font-weight:650}input[type=text]{display:block;width:min(510px,80vw);margin-top:8px;padding:14px;border:1px solid #829186;border-radius:0;background:transparent;color:var(--ink);font:16px system-ui}input[type=range]{display:block;width:180px;margin:17px 0;accent-color:var(--orange)}button{padding:14px;background:var(--ink);color:var(--paper);border:0;font:inherit;cursor:pointer}.grid{display:grid;grid-template-columns:1fr;gap:0}article{padding:30px 0 25px;border-top:1px solid #a9b4aa;min-width:0}.meta{display:flex;justify-content:space-between;gap:16px;font-size:12px;letter-spacing:.09em;text-transform:uppercase;font-weight:700}.meta span:last-child{color:#53634f}.sample{font-size:var(--size,52px);line-height:1.45;margin:24px 0 8px;overflow-wrap:anywhere}.alphabet{font-size:23px;line-height:1.65;margin:8px 0 14px;overflow-wrap:anywhere;color:#45584c}.card-footer{display:flex;justify-content:space-between;gap:20px;font-size:12px}.card-footer a{font-weight:700;white-space:nowrap}footer{border-top:1px solid #a9b4aa;margin-top:20px;padding-top:30px;font-size:14px}.notice{font-size:13px;max-width:780px;color:#526052}:focus-visible{outline:3px solid var(--orange);outline-offset:4px}@media(max-width:650px){main{padding:22px}.card-footer{display:block}.card-footer a{display:block;margin-top:10px}.meta{font-size:10px}.sample{font-size:min(var(--size,52px),42px)}}
</style><main><nav><span>STEADY STATE GAMES / TYPE LAB</span><span>COLLECTION 001</span></nav>
<h1>Good type.<br>Yours to build with.</h1><p class="eyebrow">10 ROOTS. ROOM TO GROW.</p>
<p class="intro">A small beginning for an open font library. Ten experimental display roots for games, posters, worlds, and whatever comes next.</p>
<div class="license"><strong>All Steady State Games fonts in this library are licensed under the SIL Open Font License 1.1.</strong><p>My fonts are free for commercial and noncommercial use. If you use one commercially, I ask you to consider an optional contribution of $20 USD. But I won’t make you. Enjoy the free fonts!</p><p>No payment or separate permission is required. <a href="OFL.txt">Read the font license</a>.</p></div>
<p class="notice">Prototype release 0.1 · Basic Latin display lettering. Signal and Quarry are unicase. These roots need further optical refinement; accented letters, additional scripts, and manual hinting are not included. Use the supported characters shown below.</p>
<div class="controls"><label>Try your own words<input id="preview" type="text" placeholder="Type to preview all ten fonts" maxlength="180"></label><label>Preview size <output id="sizeValue">52 px</output><input id="size" type="range" min="24" max="90" value="52"></label><button id="reset" type="button">Reset</button></div>
<p id="coverage-warning" class="notice" role="status" aria-live="polite"></p>
<div class="grid">CARDS</div><footer><a href="downloads/SSG-Ten-Roots-0.1.zip" download>Download all ten fonts + editable sources ↗</a><p>Made to be used, shared, and improved. <a href="README.md">Project notes</a> · <a href="LOGISTICS.md">Library roadmap</a> · <a href="OFL.txt">OFL 1.1</a></p><p class="notice">Optional contribution link will be added when a payment destination is configured.</p></footer></main>
<script>const input=document.querySelector('#preview'),size=document.querySelector('#size');const supported=new Set(CODEPOINTS);function update(){document.documentElement.style.setProperty('--size',size.value+'px');document.querySelector('#sizeValue').value=size.value+' px';document.querySelectorAll('.sample').forEach(el=>el.textContent=input.value||el.dataset.default);const missing=[...new Set([...input.value].filter(ch=>!supported.has(ch.codePointAt(0))))];document.querySelector('#coverage-warning').textContent=missing.length?'These characters are outside this prototype’s coverage and may use a fallback font: '+missing.join(' '):'';}input.addEventListener('input',update);size.addEventListener('input',update);document.querySelector('#reset').addEventListener('click',()=>{input.value='';size.value=52;update()});</script></html>'''
    page = page.replace('FACES',faces).replace('CARDS','\n'.join(cards)).replace('CODEPOINTS',json.dumps([ord(c) for c in CHARS]))
    (ROOT/'index.html').write_text(page,encoding='utf-8')


def render_proofs(manifest):
    paper = '#f4f1e7'
    im = Image.new('RGB',(1600,2340),paper)
    draw = ImageDraw.Draw(im)
    label = ImageFont.load_default(size=22)
    small = ImageFont.load_default(size=18)
    draw.text((65,35),'STEADY STATE GAMES / TEN OPEN FONT ROOTS',font=label,fill='#21332e')
    draw.text((65,77),'Original procedural display experiments · v0.1 · SIL Open Font License 1.1',font=small,fill='#586553')
    for i,r in enumerate(manifest):
        top = 132+i*216
        draw.line((65,top,1535,top),fill='#b5b9ab',width=1)
        draw.text((65,top+12),f'{i+1:02d}  /  {r["name"]}',font=small,fill='#ae492f')
        size = 64
        face = ImageFont.truetype(str(ROOT/r['ttf']),size)
        while draw.textlength(r['sample'],font=face)>1470:
            size -= 1
            face = ImageFont.truetype(str(ROOT/r['ttf']),size)
        draw.text((65,top+43),r['sample'],font=face,fill='#21332e')
        mini = ImageFont.truetype(str(ROOT/r['ttf']),30)
        draw.text((65,top+134),'Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm  0123456789',font=mini,fill='#435347')
    im.save(ROOT/'specimen.png')
    proof_dir=ROOT/'proofs'
    proof_dir.mkdir(exist_ok=True)
    for r in manifest:
        im=Image.new('RGB',(1400,1200),'white')
        d=ImageDraw.Draw(im)
        d.text((30,15),r['name']+' / every supported character',font=label,fill='black')
        f=ImageFont.truetype(str(ROOT/r['ttf']),56)
        for i,ch in enumerate(CHARS):
            x=30+(i%12)*113; y=65+(i//12)*120
            d.text((x,y),f'U+{ord(ch):04X}',font=small,fill='#777777')
            d.text((x,y+26),ch,font=f,fill='black')
        im.save(proof_dir/(r['id']+'.png'))


def main():
    manifest = [build_font(r) for r in RECIPES]
    (ROOT/'catalog.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    specimen(manifest)
    render_proofs(manifest)
    report = {
        'families':len(manifest),'codepoints_per_font':len(CHARS),
        'ttf_bytes':sum(r['ttf_bytes'] for r in manifest),
        'woff2_bytes':sum(r['woff2_bytes'] for r in manifest),
        'checks':['TTF and WOFF2 reopen; all tables decompile','Expected cmap and embedded license match','Every non-space glyph has contours and positive advance','Every glyph fits vertical metrics','Every supported non-space character renders via FreeType'],
        'limitations':['Not a FontBakery or OTS audit','No Godot integration test','Human optical review remains necessary','No accented Latin or complex scripts','No manual hinting','Six roots have a limited GPOS kerning set; four decorative roots have none']
    }
    (ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    files=[]
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and not any(part in ('.venv','__pycache__','downloads','proofs','collection-250','collection-1000') for part in p.relative_to(ROOT).parts) and p.suffix not in ('.pyc',):
            files.append((p,p.relative_to(ROOT).as_posix()))
    # Individual archives are included because the specimen links to them.
    files += [(ROOT/r['download'],r['download']) for r in manifest]
    write_zip(ROOT/'downloads/SSG-Ten-Roots-0.1.zip',files)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
