"""Build the 250-style experimental collection. See COLLECTION-250.md."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import build as engine
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
DEST = BASE / 'collection-250'
WIDTHS = [('Condensed',.78,3),('SemiCondensed',.89,4),('',1.0,5),('SemiExpanded',1.12,6),('Expanded',1.25,7)]
WEIGHTS = [('Light',.70,300),('Book',.85,350),('Regular',1.0,400),('Medium',1.15,500),('Bold',1.30,700)]


def recipes():
    result=[]
    for root in engine.RECIPES:
        for width,scale,wclass in WIDTHS:
            for i,(weight,factor,klass) in enumerate(WEIGHTS):
                r=dict(root)
                style=' '.join(p for p in (width,weight,'Italic' if root.get('slant') else '') if p)
                r.update(id=root['id']+'-'+style.lower().replace(' ','-'),
                         root_id=root['id'],style=style,path_width=scale,
                         weight=round(root['weight']*factor),weight_class=klass,miter_limit=1.8,optical_symbols=True,
                         width_class=wclass,tracking=round(root['tracking']*(1.12-.04*i)),
                         hairline=12*factor,outline_thickness=24*factor,
                         stencil_gap=round(33*(.85+.075*i)))
                if root['mode']=='dots': r['cell_radius']=[24,30,36,41,46][i]
                if root['mode']=='pixel': r['cell_radius']=[30,36,42,46,50][i]
                result.append(r)
    return result


def proofs(rows):
    folder=DEST/'proofs'
    folder.mkdir(exist_ok=True)
    label=ImageFont.load_default(size=21)
    small=ImageFont.load_default(size=16)
    for root in engine.RECIPES:
        selected=[r for r in rows if r['root_id']==root['id']]
        im=Image.new('RGB',(1800,2830),'#f4f1e7')
        d=ImageDraw.Draw(im)
        d.text((40,25),root['name']+' / 25 experimental styles',font=label,fill='#21332e')
        for i,r in enumerate(selected):
            y=82+i*108
            d.line((40,y,1760,y),fill='#c5c7b9')
            d.text((40,y+8),r['style'],font=small,fill='#a3452d')
            f=ImageFont.truetype(str(DEST/r['ttf']),35)
            d.text((40,y+34),'AVATAR  Hamburgefontsiv  0123456789  @ & !?',font=f,fill='#21332e')
        im.save(folder/(root['id']+'.png'))


def website(rows):
    # Inline data works directly from disk; the browser loads only the 25
    # styles in the selected family, rather than 250 webfonts at once.
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SSG / 250 font styles</title>
<style>*{box-sizing:border-box}body{background:#f4f1e7;color:#21332e;margin:0;font:16px/1.6 system-ui}main{max-width:1200px;margin:auto;padding:36px}h1{font:64px/1.1 Georgia,serif;letter-spacing:-2px}a{color:inherit;text-underline-offset:4px}.license{padding:20px;background:#dfe6d8}label{display:inline-block;margin:20px 16px 16px 0}input,select,button{font:inherit;padding:10px;background:transparent;border:1px solid #627263;color:inherit}input{width:min(500px,80vw)}article{border-top:1px solid #abb4a3;padding:20px 0}.sample{font-size:42px;line-height:1.5;overflow-wrap:anywhere;margin:16px 0}.lower{font-size:25px;overflow-wrap:anywhere}.meta{display:flex;gap:20px;justify-content:space-between;font-size:13px}#status{color:#a3452d}:focus-visible{outline:3px solid #ba482b;outline-offset:3px}@media(max-width:600px){main{padding:20px}h1{font-size:44px}.sample{font-size:30px}.meta{display:block}}</style>
<main><p>STEADY STATE GAMES / TYPE LAB</p><h1>250 styles.<br>A library taking shape.</h1><p>10 design roots × 5 widths × 5 weights. Experimental display styles, with original editable sources. TTF and WOFF2 are two formats of each style.</p>
<div class="license"><strong>All Steady State Games fonts in this library are licensed under the SIL Open Font License 1.1.</strong><p>Free for commercial and noncommercial use. If you use a font commercially, please consider an optional $20 USD contribution. But I won’t make you. Enjoy the free fonts!</p><a href="OFL.txt">Read the license</a></div>
<p><a href="downloads/SSG-250-Experimental.zip" download>Download all 250 styles</a> · <a href="downloads/SSG-250-Source.zip" download>Download editable sources</a> · <a href="REPORT.md">Release report</a></p>
<p>107 characters per font. Signal and Quarry are unicase. No accented Latin or additional scripts yet. These are generated, tested prototypes; individual optical refinement remains necessary.</p>
<label>Family<br><select id="family"></select></label><label>Preview text<br><input id="text" placeholder="Type your own supported text" maxlength="150"></label><p id="status" role="status"></p><div id="cards"></div><p>Optional contribution destination is not configured.</p></main>
<script>const data=DATA;const chars=new Set(CHARS);const sel=document.querySelector('#family'),input=document.querySelector('#text'),cards=document.querySelector('#cards'),status=document.querySelector('#status');let generation=0;const faces=[];for(const id of [...new Set(data.map(x=>x.root_id))]){const o=document.createElement('option');o.value=id;o.textContent=data.find(x=>x.root_id===id).name;sel.append(o)}
function textUpdate(){document.querySelectorAll('.sample').forEach(e=>e.textContent=input.value||e.dataset.default);const missing=[...new Set([...input.value].filter(c=>!chars.has(c.codePointAt(0))))];status.textContent=missing.length?'Unsupported characters may use a fallback font: '+missing.join(' '):''}
async function render(){const token=++generation;for(const face of faces)document.fonts.delete(face);faces.length=0;cards.replaceChildren();for(const r of data.filter(r=>r.root_id===sel.value)){const a=document.createElement('article'),meta=document.createElement('div'),label=document.createElement('strong'),link=document.createElement('a'),sample=document.createElement('p'),lower=document.createElement('p');meta.className='meta';label.textContent=r.name+' / '+r.style;link.textContent='Download font + license ↗';link.href=r.download;link.download='';meta.append(label,link);sample.className='sample';sample.dataset.default=r.sample;sample.style.fontFamily='"'+r.id+'"';lower.className='lower';lower.textContent='Aa Bb Cc Dd Ee Ff Gg Hh 0123456789';lower.style.fontFamily='"'+r.id+'"';a.append(meta,sample,lower);cards.append(a);const f=new FontFace(r.id,'url("'+r.woff2+'")');faces.push(f);document.fonts.add(f);f.load().catch(()=>{if(token===generation)status.textContent='A font could not load. Try serving this folder with python -m http.server.'})}textUpdate()};sel.addEventListener('change',render);input.addEventListener('input',textUpdate);render();</script></html>'''
    (DEST/'index.html').write_text(page.replace('DATA',json.dumps(rows)).replace('CHARS',json.dumps([ord(c) for c in engine.CHARS])),encoding='utf-8')


def main():
    DEST.mkdir(exist_ok=True)
    (DEST/'fonts').mkdir(exist_ok=True)
    (DEST/'downloads').mkdir(exist_ok=True)
    shutil.copy2(BASE/'OFL.txt',DEST/'OFL.txt')
    engine.ROOT=DEST
    engine.OUT=DEST/'fonts'
    rows=[]
    signatures=set()
    # Isolate native font/rendering libraries per style: long-lived batch
    # processes exhibited memory corruption in the local Windows runtime.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,row in enumerate(pool.map(run_worker,range(250)),1):
            digest=row['outline_sha256']
            assert digest not in signatures, ('Duplicate outlines and spacing',row['id'])
            signatures.add(digest)
            rows.append(row)
            if i%25==0: print(f'{i}/250 built, rendered, and validated',flush=True)
    assert len(rows)==250 and len(signatures)==250
    (DEST/'catalog.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    proofs(rows)
    website(rows)
    report={'styles':250,'design_roots':10,'widths_per_root':5,'weights_per_width':5,
            'unique_outline_and_metrics_hashes':len(signatures),
            'codepoints_per_style':len(engine.CHARS),'ttf_bytes':sum(r['ttf_bytes'] for r in rows),
            'woff2_bytes':sum(r['woff2_bytes'] for r in rows),
            'checks':['All TTF/WOFF2 tables decode','Embedded OFL and cmap match','Nonempty outlines and positive advances','Vertical metrics contain every glyph','FreeType renders every supported non-space character','250 unique outline/metrics hashes','Weight and width metadata match recipes'],
            'status':'experimental','limitations':['Procedural width and weight branches, not 250 independently drawn families','No accents or non-Latin scripts','Limited kerning','No manual hinting','No individual optical sign-off','No cross-platform or Godot audit']}
    (DEST/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (DEST/'REPORT.md').write_text(f'''# 250-style experimental milestone

The active collection contains **250 distinct styles** from 10 original roots,
with five widths and five weights per root. TTF and WOFF2 are not counted twice.
The initial ten-font release remains separate historical work.

Each style includes 107 code points, OFL.txt, and FONTLOG.txt. All 250 passed
font-table decoding, coverage, metadata, vertical bounds, and FreeType rendering
checks. All have unique outline/metrics hashes. See validation.json for the
machine-readable results and catalog.json for individual recipes and hashes.

TTFs total {report['ttf_bytes']:,} bytes; WOFF2s total {report['woff2_bytes']:,} bytes.

Widths are Condensed, SemiCondensed, normal, SemiExpanded, and Expanded.
Weights are Light, Book, Regular, Medium, and Bold. Width changes act on the
centerline before stroke construction for the eight stroke-based roots, so
condensation does not simply squash the final stroke. Hairlines, outline
thickness, stencil gaps, and spacing respond to weight; grid roots use explicit
cell-size steps. These are procedural experiments, not individually redrawn
optical masters. Signal and Quarry intentionally use capital forms for
lowercase input.

Open index.html for the family-filtered live specimen. If your browser blocks
font loading from disk, run `python -m http.server` in this directory and open
the localhost address it prints. The catalog requests only the selected
family's 25 webfonts. Each proof sheet shows all 25 styles of a root.

Install TTF files directly, or import them into your game. Keep the font license
with redistributed copies. The source archive contains build.py, build250.py,
the original source drawings and root recipes, and dependency requirements.
Extract it, install requirements.txt, and run `python build250.py` to rebuild.

The collection is experimental. It has no accented Latin, additional scripts,
manual hinting, or individual optical sign-off. Automated validity is not a
claim of finished typography. Further spacing, counter, language, browser,
platform, and Godot review should precede marking any style stable.

Nothing has been published or installed into the existing game.
''',encoding='utf-8')
    sources=[(BASE/n,n) for n in ['build.py','build250.py','requirements.txt','OFL.txt','COLLECTION-250.md','sources/glyphs.py','sources/roots.json']]
    engine.write_zip(DEST/'downloads/SSG-250-Source.zip',sources)
    files=[(p,p.relative_to(DEST).as_posix()) for p in sorted((DEST/'fonts').rglob('*')) if p.is_file()]
    files += [(DEST/n,n) for n in ['OFL.txt','REPORT.md','catalog.json','validation.json','index.html']]
    files += [(p,p.relative_to(DEST).as_posix()) for p in sorted((DEST/'proofs').glob('*.png'))]
    files += [(DEST/r['download'],r['download']) for r in rows]
    files += [(DEST/'downloads/SSG-250-Source.zip','downloads/SSG-250-Source.zip')]
    archive=DEST/'downloads/SSG-250-Experimental.zip'
    engine.write_zip(archive,files)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if n.endswith('.ttf')])==250
        assert len([n for n in z.namelist() if n.endswith('.woff2')])==250
    print(json.dumps(report,indent=2),flush=True)
    print(f'Bundle: {archive} ({archive.stat().st_size:,} bytes)',flush=True)


def run_worker(index):
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(index)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'Style {index} failed ({result.returncode}): {result.stderr}')
    return json.loads(result.stdout)


def worker(index):
    engine.ROOT=DEST
    engine.OUT=DEST/'fonts'
    r=recipes()[index]
    row=engine.build_font(r)
    with engine.TTFont(DEST/row['ttf']) as font:
        row['outline_sha256']=hashlib.sha256(font.getTableData('glyf')+font.getTableData('hmtx')).hexdigest()
        assert font['OS/2'].usWeightClass==r['weight_class']
        assert font['OS/2'].usWidthClass==r['width_class']
    print(json.dumps(row))


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker': worker(int(sys.argv[2]))
    else: main()
