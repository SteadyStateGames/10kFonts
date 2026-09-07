"""Build 1,000 experimental styles, preserving the previous 250."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, zipfile
from concurrent.futures import ThreadPoolExecutor
import build250 as stage
engine=stage.engine
from shapely.geometry import LineString
from shapely import affinity
from shapely.ops import unary_union

BASE=Path(__file__).resolve().parent
DEST=BASE/'collection-1000'
PREVIOUS=BASE/'collection-250'
ORIGINAL_GEOMETRY=engine.make_geometry

def geometry(ch,r):
    shape=ORIGINAL_GEOMETRY(ch,r)
    if r.get('treatment')=='Cut' and ch.isalnum():
        xmin,ymin,xmax,ymax=shape.bounds
        shape=shape.difference(LineString([(xmin-50,280),(xmax+50,410)]).buffer(12,cap_style=2))
    elif r.get('treatment')=='Echo':
        shadow=affinity.translate(shape,xoff=48,yoff=-42).difference(shape.buffer(14,join_style=1))
        shape=unary_union([shape,shadow])
    shape=shape.simplify(.35,preserve_topology=True)
    assert shape.is_valid and not shape.is_empty,(r['id'],ch)
    return shape

def recipes():
    rows=[]
    for treatment in ['Slant','Cut','Echo']:
        for source in stage.recipes():
            r=dict(source)
            root=source['root_id']
            label=treatment
            if treatment=='Slant':
                if root=='ember':
                    label='Upright'
                    r['slant']=0
                    r['style']=r['style'].replace('Italic','').strip()
                else:
                    r['slant']=.18
                    r['style']+=' Italic'
            r.update(name=source['name']+' '+label,root_id=root+'-'+treatment.lower(),
                     design_root=root,treatment=treatment,
                     descent=420 if treatment=='Echo' else 350,repair_affine_contacts=True,
                     description=source['description']+' '+label+' display treatment.')
            r['id']=r['root_id']+'-'+r['style'].lower().replace(' ','-')
            rows.append(r)
    return rows

def worker(index):
    engine.ROOT=DEST
    engine.OUT=DEST/'fonts'
    engine.make_geometry=geometry
    r=recipes()[index]
    row=engine.build_font(r)
    with engine.TTFont(DEST/row['ttf']) as font:
        row['outline_sha256']=hashlib.sha256(font.getTableData('glyf')+font.getTableData('hmtx')).hexdigest()
        assert font['OS/2'].usWeightClass==r['weight_class']
        assert font['OS/2'].usWidthClass==r['width_class']
    print(json.dumps(row))

def run_worker(index):
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(index)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'Style {index} failed ({result.returncode}): {result.stderr}')
    return json.loads(result.stdout)

def preserve_originals():
    rows=json.loads((PREVIOUS/'catalog.json').read_text('utf-8'))
    assert len(rows)==250
    for row in rows:
        row.update(design_root=row['root_id'],treatment='Original')
        src=PREVIOUS/'fonts'/row['id']
        dst=DEST/'fonts'/row['id']
        shutil.copytree(src,dst,dirs_exist_ok=True)
        shutil.copy2(PREVIOUS/row['download'],DEST/row['download'])
        assert hashlib.sha256((DEST/row['ttf']).read_bytes()).hexdigest()==row['sha256']
        for p in src.iterdir():
            if p.is_file():
                assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((dst/p.name).read_bytes()).digest()
    return rows

def artifacts(rows):
    groups=[]
    for group in dict.fromkeys(r['root_id'] for r in rows):
        first=next(r for r in rows if r['root_id']==group)
        groups.append({'id':group,'name':first['name']})
    stage.DEST=DEST
    engine.RECIPES=groups
    stage.proofs(rows)
    stage.website(rows)
    p=DEST/'index.html'
    page=p.read_text('utf-8').replace('250 font styles','1,000 font styles').replace('250 styles.','1,000 styles.').replace('SSG-250-','SSG-1000-').replace('Download all 250 styles','Download all 1,000 styles')
    page=page.replace('10 design roots × 5 widths × 5 weights.','10 design roots × 4 treatments × 5 widths × 5 weights.')
    page=page.replace('Signal and Quarry are unicase.','Signal and Quarry and their treatments are unicase.')
    page=page.replace('Family<br>','Family / treatment<br>')
    page=page.replace('<p>Optional contribution destination','<p>Original, alternate slant (upright for Ember), diagonal Cut, and offset Echo treatments. Each group contains 25 styles.</p><p>Optional contribution destination')
    p.write_text(page,encoding='utf-8')

def package():
    rows=json.loads((DEST/'catalog.json').read_text('utf-8'))
    sources=[(BASE/n,n) for n in ['build.py','build250.py','build1000.py','requirements.txt','OFL.txt','COLLECTION-250.md','COLLECTION-1000.md','verify-browser.cjs','sources/glyphs.py','sources/roots.json']]
    for row in rows:
        if row['treatment']=='Original':
            folder=PREVIOUS/'fonts'/row['id']
            sources += [(p,'collection-250/'+p.relative_to(PREVIOUS).as_posix()) for p in sorted(folder.iterdir()) if p.is_file() and p.suffix in ('.ttf','.woff2','.txt')]
            sources.append((PREVIOUS/row['download'],'collection-250/'+row['download']))
    sources.append((PREVIOUS/'catalog.json','collection-250/catalog.json'))
    engine.write_zip(DEST/'downloads/SSG-1000-Source.zip',sources)
    files=[(p,p.relative_to(DEST).as_posix()) for p in sorted((DEST/'fonts').rglob('*')) if p.is_file() and p.suffix in ('.ttf','.woff2','.txt')]
    for n in ['OFL.txt','REPORT.md','catalog.json','validation.json','index.html','browser-validation.json','browser-preview.png','REVIEW.md']:
        if (DEST/n).is_file(): files.append((DEST/n,n))
    files += [(p,p.relative_to(DEST).as_posix()) for p in sorted((DEST/'proofs').glob('*.png'))]
    files += [(DEST/r['download'],r['download']) for r in rows]
    files += [(DEST/'downloads/SSG-1000-Source.zip','downloads/SSG-1000-Source.zip')]
    archive=DEST/'downloads/SSG-1000-Experimental.zip'
    engine.write_zip(archive,files)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if n.endswith('.ttf')])==1000
        assert len([n for n in z.namelist() if n.endswith('.woff2')])==1000
        assert len(z.namelist())==len(set(z.namelist()))
        assert all(r['download'] in z.namelist() for r in rows)
    print(f'Package verified: {archive.stat().st_size:,} bytes',flush=True)

def main():
    DEST.mkdir(exist_ok=True)
    (DEST/'fonts').mkdir(exist_ok=True)
    (DEST/'downloads').mkdir(exist_ok=True)
    shutil.copy2(BASE/'OFL.txt',DEST/'OFL.txt')
    rows=preserve_originals()
    signatures={r['outline_sha256'] for r in rows}
    print('250 original styles preserved byte-for-byte',flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,row in enumerate(pool.map(run_worker,range(750)),251):
            assert row['outline_sha256'] not in signatures,('Duplicate style',row['id'])
            signatures.add(row['outline_sha256'])
            rows.append(row)
            if i%50==0: print(f'{i}/1000 styles available and validated',flush=True)
    assert len(rows)==1000 and len(signatures)==1000
    (DEST/'catalog.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    artifacts(rows)
    report={'styles':1000,'design_roots':10,'treatments':4,'widths':5,'weights':5,
            'original_styles_preserved_byte_for_byte':250,'new_styles':750,
            'unique_outline_and_metrics_hashes':1000,'codepoints_per_style':107,
            'ttf_bytes':sum(r['ttf_bytes'] for r in rows),'woff2_bytes':sum(r['woff2_bytes'] for r in rows),
            'checks':['250 baseline styles copied and hash verified','750 new styles decoded as TTF and WOFF2','Embedded license and coverage verified','Every supported non-space character of each new style rendered by FreeType','Glyphs fit vertical metrics','1000 unique outline/metrics hashes','Weight and width metadata checked'],
            'status':'experimental','limitations':['10 shared drawing roots with procedural treatments; not 1000 independently drawn families','No accents or non-Latin scripts','Limited kerning and no manual hinting','No individual optical approval','No cross-platform or Godot integration audit']}
    (DEST/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (DEST/'REPORT.md').write_text(f'''# 1,000-style experimental collection

**1,000 distinct font styles**, from 10 design roots, four treatments, five
widths, and five weights. Formats are not counted as additional styles.

The original 250 styles are preserved byte-for-byte. The 750 new styles add:
- Alternate slant: oblique construction, or upright construction for Ember.
- Cut: a diagonal opening across alphanumeric glyphs.
- Echo: a separated offset shadow derived from the original outline.

Every style has TTF, WOFF2, OFL.txt and a font log, with 107 supported code
points. Signal and Quarry and their treatments are unicase. Accented letters
and non-Latin scripts are not included. All font software uses OFL 1.1.

TTFs total {report['ttf_bytes']:,} bytes; WOFF2s total {report['woff2_bytes']:,} bytes.

The 750 new styles passed font decoding, cmap/license validation, bounds,
metadata and per-character FreeType rendering checks. The baseline 250 retain
the validated previous release. All 1,000 outline/metrics hashes are distinct.
See validation.json for machine-readable results.

Open index.html to preview each 25-style group. Only the selected group loads.
If local font loading is blocked, run python -m http.server in this directory
and open the localhost address it prints.

The source archive includes editable geometry, build scripts, requirements,
and preserved baseline assets. Install requirements.txt and run
python build1000.py. Worker isolation avoids native-library batch crashes
encountered on Windows. Run python build1000.py --package to rebuild ZIPs
without regenerating fonts.

These are experimental procedural display styles. Automated validity and
collection-level proofs do not replace individual optical review. Spacing,
kerning, small-size performance, languages and platform testing need further
work before styles can be called stable.

The project now lives entirely in the requested 10kFonts directory.
Nothing has been published or changed in bomb-the-meeples.
''',encoding='utf-8')
    package()
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker': worker(int(sys.argv[2]))
    elif len(sys.argv)==2 and sys.argv[1]=='--package': package()
    else: main()

