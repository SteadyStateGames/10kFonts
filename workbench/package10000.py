"""Assemble the complete release and a lean static hosting payload."""
from pathlib import Path
import json,hashlib,shutil,csv,zipfile,sys,gzip
import build as engine
import package2000 as prior
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
BUILD=BASE/'collection-10000';DEST=ROOT/'collection-10000';HOST=ROOT/'hosting';SITE=HOST/'site';RELEASE=HOST/'release-assets'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def tags(row):
    prior.DEST=DEST
    r=prior.tag(row)
    r['release']='expansion' if 'form' in r else 'earlier'
    if 'form' in r:
        extras=[r['form'].lower(),r['finish'].lower(),'10k-expansion','stylized-proportions','large-display']
        if r['form'] in ('Arch','Bounce','Slope'):extras+=['shifted-baseline']
        r['tags']=sorted(set(r['tags']+extras))
        r['display_tags'] += [r['form'],r['finish']]
    return r
def assemble():
    for p in [DEST/'fonts',DEST/'webfonts',DEST/'downloads/groups',RELEASE/'groups',SITE]:
        p.mkdir(parents=True,exist_ok=True)
    items=[]
    for source,catalog in [(ROOT/'collection-2000','catalog.json'),(BUILD,'new-catalog.json')]:
        for row in json.loads((source/catalog).read_text('utf-8')):
            r=dict(row)
            assert sha(source/r['ttf'])==r['sha256'],('source',r['id'])
            with engine.TTFont(source/r['ttf']) as f:
                signature=hashlib.sha256(f.getTableData('glyf')+f.getTableData('hmtx')).hexdigest()
                assert signature==r['outline_sha256']
                r['postscript_name']=f['name'].getDebugName(6)
            r=tags(r)
            for key in ['ttf','woff2']:
                out=DEST/r[key];out.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source/r[key],out)
                assert sha(source/r[key])==sha(out)
            folder=(DEST/r['ttf']).parent
            for filename in ['OFL.txt','FONTLOG.txt']:
                shutil.copy2((source/r['ttf']).parent/filename,folder/filename)
            if source==BUILD:
                (folder/'FONTLOG.txt').write_text(f"{r['name']} {r['style']} 0.400\n2026-09-07: {r['description']}\n107 basic-Latin and punctuation codepoints. Experimental proportions; display use.\nOriginal SSG construction, OFL-1.1, no Reserved Font Names.\nSee METADATA.json for source recipe, hashes, coverage and tags.\n",'utf-8')
            r['group_download']='downloads/groups/'+r['root_id']+'.zip'
            r['preview_woff2']='webfonts/'+r['id']+'.woff2'
            shutil.copy2(DEST/r['woff2'],DEST/r['preview_woff2'])
            (folder/'METADATA.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),'utf-8')
            # Individual downloads remain available in the full local release.
            engine.write_zip(DEST/r['download'],[(folder/n,n) for n in [Path(r['ttf']).name,Path(r['woff2']).name,'OFL.txt','FONTLOG.txt','METADATA.json']])
            items.append(r)
            if len(items)%1000==0:print('Assembled',len(items),'styles',flush=True)
    assert len(items)==10000
    for key in ['id','postscript_name','outline_sha256']:
        assert len({r[key] for r in items})==10000,('duplicate',key)
    assert sum(r['collection_tier']=='Core' for r in items)==500
    rank={'Core':0,'Balanced':1,'Experimental':2};rootrank={n:i for i,n in enumerate(['relay','bastion','vector','ember','spire','rivet','orbit','signal','quarry','ribbon'])}
    items.sort(key=lambda r:(rank[r['collection_tier']],abs(r['width_class']-5),abs(r['weight_class']-400),abs(r.get('slant',0)),rootrank[r['design_root']],r['name'],r['style']))
    (DEST/'catalog.json').write_text(json.dumps(items,indent=2,ensure_ascii=False),'utf-8')
    write_catalog(items)
    groups={}
    for r in items:groups.setdefault(r['root_id'],[]).append(r)
    assert len(groups)==400 and all(len(rs)==25 for rs in groups.values())
    for group,rs in groups.items():
        files=[]
        for r in rs:
            for key in ['ttf','woff2']:files.append((DEST/r[key],r[key]))
            for n in ['OFL.txt','FONTLOG.txt','METADATA.json']:
                p=(DEST/r['ttf']).parent/n;files.append((p,p.relative_to(DEST).as_posix()))
        path=DEST/'downloads/groups'/(group+'.zip');engine.write_zip(path,files)
        with zipfile.ZipFile(path) as z:
            assert sum(n.endswith('.ttf') for n in z.namelist())==25
            assert z.testzip() is None
        shutil.copy2(path,RELEASE/'groups'/path.name)
    shutil.copy2(BASE/'OFL.txt',DEST/'OFL.txt')
    if (BUILD/'proofs').exists():shutil.copytree(BUILD/'proofs',DEST/'proofs',dirs_exist_ok=True)
    report=dict(styles=10000,design_roots=10,groups=400,styles_per_group=25,
        tiers={'Core':500,'Balanced':250,'Experimental':9250},
        preserved_previous_styles=2000,new_experimental_styles=8000,unique_outline_metric_hashes=10000,
        core_codepoints=184,experimental_codepoints=107,
        ttf_bytes=sum(r['ttf_bytes'] for r in items),woff2_bytes=sum(r['woff2_bytes'] for r in items),
        checks=['2,000 previous TTF/WOFF2 binaries copied and hash-verified','8,000 new styles decode in both formats, have complete coverage/license and valid vertical bounds, and render all supported characters in FreeType','10,000 unique IDs, PostScript names and glyph/metric hashes','400 group ZIPs each have 25 styles and pass CRC verification'],
        review_status='500 refined core styles retain their prior checks. The 8,000 additions are experimental display branches, not individually approved general-purpose fonts.')
    for prefix in ['browser','godot']:
        path=DEST/(prefix+'-validation.json')
        if path.exists():report[prefix+'_checks']=json.loads(path.read_text('utf-8'))
    (DEST/'validation.json').write_text(json.dumps(report,indent=2),'utf-8')
    (DEST/'REPORT.md').write_text("""# Steady State Games / 10,000 styles

500 Core, 250 Balanced, 9,250 Experimental styles. This is 400 groups of 25 styles from 10 shared drawing roots; formats are not counted twice and these are not 10,000 independently drawn families.

The previous 2,000 font binaries are preserved. The 8,000 additions combine eight geometric treatments (Surge, Zigzag, Wedge, Pinch, Arch, Bounce, Forward, Slope), four finishes (Solid, Edge, Scan, Offset), ten roots, five widths and five weights.

## Quality and coverage
The refined 500-style core retains its 184-character coverage and previous proportion/counter/spacing/raster checks. All new experiments contain 107 characters. Every new style must decode as TTF and WOFF2, render all its non-space glyphs, fit its vertical metrics and have unique outlines/metrics.

Browser and Godot results are recorded in validation.json and the accompanying browser-validation.json and godot-validation.json. These are loading, coverage, shaping and interface smoke checks; individual visual approval remains pending.

The new fonts intentionally bend, slant, cut or layer letterforms. They are tagged for large display use, not promoted into the core. Optical approval, broad languages, manual hinting and long-reading validation remain separate work.

## Files
catalog.json is the full recipe/metadata catalog; catalog.csv is the tag export. Each font folder has TTF, WOFF2, OFL.txt, FONTLOG.txt and METADATA.json. Individual ZIPs remain in downloads. The website offers downloads/groups: 400 archives, each holding 25 styles of a family/treatment/slant group.

webfonts contains the previews used by the browser. They are byte-identical to the WOFF2 counterparts in the font folders. The browser loads only 20 visible fonts at a time and normalizes preview accents to NFC. Unsupported characters are flagged.

## Hosting
The separate hosting/site folder contains the static website and WOFF2 previews. Big download bundles and the 400 group archives belong in GitHub Releases. Download links are controlled by config.json, so the same website can be previewed locally and deployed under a repository subpath.

The hosting/source folder contains editable build sources and a GitHub Pages deployment workflow. hosting/release-assets contains uploadable archives. See hosting/HOSTING.md for measured sizes, verification and publication instructions.

All font software is OFL 1.1. Previous releases remain available in their original folders.
""",'utf-8')
    shutil.copy2(ROOT/'collection-2000/TAGS.md',DEST/'TAGS.md')
    with (DEST/'TAGS.md').open('a',encoding='utf-8') as f:
        f.write('\n10K adds form, finish, release, stylized-proportions, large-display and shifted-baseline tags. Quality tiers are preserved; an experimental effect never becomes Core merely by passing file validation.\n')
    build_site(items)
    print(json.dumps(report,indent=2),flush=True)
    return items
def write_catalog(items):
    columns=['id','name','style','collection_tier','design_root','root_id','treatment','form','finish','release','weight_class','width_class','slant_tag','codepoints','review_status','tags','ttf','woff2','sha256']
    with (DEST/'catalog.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
        for r in items:w.writerow({k:'; '.join(r.get(k,[])) if isinstance(r.get(k),list) else r.get(k,'') for k in columns})
    fields=['id','name','style','collection_tier','design_root','root_id','treatment','weight_class','width_class','slant_tag','codepoints','release','tag_ids','display_ids','charset']
    taglist=sorted({t for r in items for t in r['tags']});tagmap={t:i for i,t in enumerate(taglist)}
    displaylist=sorted({t for r in items for t in r['display_tags']});displaymap={t:i for i,t in enumerate(displaylist)}
    charsets={str(r['codepoints']):r['codepoint_list'] for r in items}
    packed=[]
    for r in items:
        r=dict(r,tag_ids=[tagmap[t] for t in r['tags']],display_ids=[displaymap[t] for t in r['display_tags']],charset=str(r['codepoints']))
        packed.append([r[k] for k in fields])
    payload={'fields':fields,'tags':taglist,'display_tags':displaylist,'charsets':charsets,'rows':packed}
    content=json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    (DEST/'catalog-index.json').write_bytes(content)
    print('Browser catalog:',len(content),'bytes;',len(gzip.compress(content)),'bytes gzipped',flush=True)
def build_site(items):
    page=(BASE/'catalog10000-template.html').read_text('utf-8-sig')
    (DEST/'index.html').write_text(page,'utf-8')
    (DEST/'config.json').write_text(json.dumps({'group_base':'downloads/groups/','bulk_base':'downloads/','source_url':'downloads/SSG-10000-Source.zip','repository_url':None}),'utf-8')
    (SITE/'webfonts').mkdir(parents=True,exist_ok=True)
    for r in items:shutil.copy2(DEST/r['preview_woff2'],SITE/r['preview_woff2'])
    for n in ['index.html','catalog-index.json','OFL.txt','REPORT.md','TAGS.md','validation.json']:
        shutil.copy2(DEST/n,SITE/n)
    shutil.copy2(DEST/'catalog.csv',SITE/'catalog.csv')
    # Local hosting preview; publish10000.py substitutes remote release URLs.
    (SITE/'config.json').write_text(json.dumps({'group_base':'../../collection-10000/downloads/groups/','bulk_base':'../../collection-10000/downloads/','source_url':'../../collection-10000/downloads/SSG-10000-Source.zip','repository_url':None}),'utf-8')
    (SITE/'.nojekyll').write_text('','utf-8')
    total=sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file())
    assert total<1_000_000_000,('Pages payload exceeds 1 GB',total)
    print('Hosting payload:',total,'bytes',flush=True)
def package(items):
    # Reuse the already-verified core archive without rewriting the core fonts.
    shutil.copy2(ROOT/'collection-2000/downloads/SSG-Core-500.zip',DEST/'downloads/SSG-Core-500.zip')
    source_names=['build.py','build250.py','build1000.py','build_balanced.py','build2000.py','build10000.py','core_geometry.py','package2000.py','package10000.py','proofs10000.py','catalog10000-template.html','requirements.txt','OFL.txt','sources/glyphs.py','sources/roots.json']
    sources=[(BASE/n,'workbench/'+n) for n in source_names]
    for n in ['verify10000.cjs','prepare_hosting10000.py','publish10000.py']:
        if (BASE/n).exists():sources.append((BASE/n,'workbench/'+n))
    for n in ['project.godot','verify.gd']:sources.append((BASE/'qa-godot'/n,'workbench/qa-godot/'+n))
    # Baseline archive is the exact preserved input for a repeatable rebuild.
    sources.append((ROOT/'collection-2000/downloads/SSG-2000.zip','inputs/SSG-2000.zip'))
    sources.append((ROOT/'collection-2000/downloads/SSG-Core-500.zip','inputs/SSG-Core-500.zip'))
    readme=BUILD/'SOURCE-README.md'
    readme.write_text("""# Rebuild the SSG library

From the extracted archive root, run this Python bootstrap once:

```python
from pathlib import Path
import shutil, zipfile
baseline = Path('collection-2000')
with zipfile.ZipFile('inputs/SSG-2000.zip') as archive:
    archive.extractall(baseline)
(baseline / 'downloads').mkdir(exist_ok=True)
for name in ['SSG-2000.zip', 'SSG-Core-500.zip']:
    shutil.copy2(Path('inputs') / name, baseline / 'downloads' / name)
```

Install workbench/requirements.txt with Python 3.14. Then run:

    python workbench/build10000.py
    python workbench/package10000.py

Optional proof sheets before packaging:

    python workbench/build10000.py --pilot
    python workbench/proofs10000.py

The existing 2,000 inputs are preserved byte-for-byte. Checkpoints make the new build resumable. Browser and Godot validation require their respective local runtimes; see the verifier sources. Building font files does not certify individual optical quality.
""",'utf-8')
    sources.append((readme,'README.md'))
    engine.write_zip(DEST/'downloads/SSG-10000-Source.zip',sources)
    files=[(DEST/n,n) for n in ['index.html','catalog-index.json','catalog.json','catalog.csv','OFL.txt','REPORT.md','TAGS.md','validation.json']]
    offline=BUILD/'offline-config.json'
    offline.write_text(json.dumps({'group_base':'downloads/groups/','bulk_base':'downloads/','source_url':'downloads/SSG-10000-Source.zip','repository_url':None,'hide_full_download':True}),'utf-8')
    files.append((offline,'config.json'))
    for n in ['browser-validation.json','godot-validation.json']:
        if (DEST/n).exists():files.append((DEST/n,n))
    files += [(p,p.relative_to(DEST).as_posix()) for p in (DEST/'proofs').glob('*.png')]
    for r in items:
        for key in ['ttf','woff2','preview_woff2']:files.append((DEST/r[key],r[key]))
        for n in ['OFL.txt','FONTLOG.txt','METADATA.json']:
            p=(DEST/r['ttf']).parent/n;files.append((p,p.relative_to(DEST).as_posix()))
    files += [(p,p.relative_to(DEST).as_posix()) for p in (DEST/'downloads/groups').glob('*.zip')]
    # Full offline bundle has working bulk/source links as well.
    files += [(DEST/'downloads'/n,'downloads/'+n) for n in ['SSG-Core-500.zip','SSG-10000-Source.zip']]
    archive=DEST/'downloads/SSG-10000.zip';engine.write_zip(archive,files)
    assert archive.stat().st_size<2*1024**3,('Release asset too large',archive.stat().st_size)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(set(z.namelist()))
        assert sum(n.endswith('.ttf') for n in z.namelist())==10000
        assert sum(n.startswith('fonts/') and n.endswith('.woff2') for n in z.namelist())==10000
        assert sum(n.endswith('METADATA.json') for n in z.namelist())==10000
    for n in ['SSG-Core-500.zip','SSG-10000-Source.zip','SSG-10000.zip']:shutil.copy2(DEST/'downloads'/n,RELEASE/n)
    (DEST/'downloads/SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.name for p in sorted(RELEASE.glob('*.zip')))+'\n','utf-8')
    shutil.copy2(DEST/'downloads/SHA256SUMS.txt',RELEASE/'SHA256SUMS.txt')
    p=ROOT/'README.md';s=p.read_text('utf-8').replace('Latest release: open collection-2000/index.html. The installable TTF files are inside collection-2000/fonts, organized by style.','Latest release: open collection-10000/index.html. The installable TTF files are inside collection-10000/fonts, organized by style.')
    if '## 10,000-style' not in s:s+='\n## 10,000-style milestone\n\ncollection-10000/ contains 500 Core, 250 Balanced and 9,250 Experimental styles. Hosting assets and deployment preparation are in hosting/. The core and previous 2,000 font binaries are preserved. Source: workbench/build10000.py. See collection-10000/REPORT.md for scope and quality limits.\n'
    p.write_text(s,'utf-8')
    print('Full ZIP verified:',archive.stat().st_size,'bytes',flush=True)
if __name__=='__main__':
    if '--site-only' in sys.argv:build_site(json.loads((DEST/'catalog.json').read_text('utf-8')))
    elif '--package-only' in sys.argv:package(json.loads((DEST/'catalog.json').read_text('utf-8')))
    elif '--assemble-only' in sys.argv:assemble()
    else:package(assemble())

