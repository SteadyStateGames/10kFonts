"""Assemble, tag and package a self-contained 2,000-style release."""
from pathlib import Path
import json,hashlib,shutil,csv,zipfile,sys
import build as engine
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
BUILD=BASE/'collection-2000';DEST=ROOT/'collection-2000'
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def tag(row):
    r=dict(row);tier=r['collection_tier'];mode=r['mode'];base=r['design_root']
    category={'round':'rounded-sans','slab':'slab-serif','angular':'angular-sans','stencil':'stencil','rail':'double-line','nib':'broad-nib','dots':'dot-matrix','pixel':'pixel','outline':'outline','serif':'serif'}[mode]
    mood={'relay':['friendly','geometric'],'bastion':['fantasy','sturdy'],'vector':['sci-fi','technical'],'rivet':['industrial','military'],'orbit':['arcade','neon'],'ember':['energetic','handwritten-inspired'],'signal':['retro','scoreboard'],'quarry':['retro','8-bit'],'ribbon':['poster','outline'],'spire':['storybook','editorial']}[base]
    width={3:'condensed',4:'semi-condensed',5:'normal-width',6:'semi-expanded',7:'expanded'}[r['width_class']]
    angle=r.get('slant',0);slant='oblique' if angle>0 else 'reverse-oblique' if angle<0 else 'upright'
    coverage='western-latin-accents' if tier=='Core' else 'basic-latin'
    case='unicase' if mode in ('dots','pixel') else 'mixed-case'
    uses=['headings','ui-candidate','short-text-candidate'] if tier=='Core' else ['titles','posters','game-display']
    if tier=='Core' and r['optical']=='Text':uses.append('body-text-candidate')
    review='core-automated-qa' if tier=='Core' else 'balanced-alignment-qa' if tier=='Balanced' else 'experimental-technical-qa'
    r.update(category=category,slant_tag=slant,license='OFL-1.1',review_status='optical-review-pending',use_cases=uses,
        tags=sorted(set([tier.lower(),category,base,r['treatment'].lower(),width,slant,coverage,case,review,'proportional','ofl-1.1']+mood+uses+([r['optical'].lower(),'no-manual-hinting','precomposed-accents'] if tier=='Core' else []))),
        display_tags=[category.replace('-',' '),width.replace('-',' '),slant.replace('-',' '),('Accented Latin' if tier=='Core' else case.replace('-',' '))]+(['Larger x-height'] if r.get('optical')=='Text' else []))
    if tier=='Core':
        r['qa_label']='Core geometry, counter, spacing and 16/24/48 px raster checks passed.'
        r['limitations']=['Individual optical and long-reading review pending.','No combining-mark shaping or additional scripts.','No manual hinting or Godot/print certification.']
    elif tier=='Balanced':
        r['qa_label']='Proportion correction checks passed.'
        r['limitations']=['Descender bowls and spacing still need refinement.','Display prototype; basic Latin only.']
    else:
        r['qa_label']='Font decoding and rendering checks passed.'
        r['limitations']=['Experimental display style.','Proportions and small text are not core-qualified.']
    if (DEST/'godot-validation.json').exists():
        r['tags'].append('godot-load-tested')
        r['godot_check']='FontFile loading, catalog coverage and text shaping at 16/24/48 px passed; in-game visual review pending.'
    if (DEST/'browser-validation.json').exists():
        r['tags'].append('browser-load-tested')
    return r
def assemble():
    DEST.mkdir(exist_ok=True);(DEST/'fonts').mkdir(exist_ok=True);(DEST/'downloads').mkdir(exist_ok=True)
    items=[]
    for folder,tier in [(ROOT/'collection-1000','Experimental'),(ROOT/'collection-balanced','Balanced'),(BUILD,None)]:
        catalog='new-catalog.json' if folder==BUILD else 'catalog.json'
        for original in json.loads((folder/catalog).read_text('utf-8')):
            r=dict(original)
            if tier:
                r['collection_tier']=tier
                r['treatment']='Balanced' if tier=='Balanced' else r.get('treatment','Original')
                r['design_root']=r.get('design_root',r['root_id'])
            assert SHA(folder/r['ttf'])==r['sha256'],('source hash',r['id'])
            with engine.TTFont(folder/r['ttf']) as f:
                r['codepoint_list']=sorted(f.getBestCmap())
                actual=hashlib.sha256(f.getTableData('glyf')+f.getTableData('hmtx')).hexdigest()
                assert actual==r['outline_sha256'],('source outline hash',r['id'])
                r['postscript_name']=f['name'].getDebugName(6)
            r=tag(r);items.append(r)
            target=DEST/'fonts'/r['id'];target.mkdir(exist_ok=True)
            # Manifest-selected files prevent old pilot filenames entering this release.
            for key in ['ttf','woff2']:
                source=folder/r[key];destination=DEST/r[key]
                shutil.copy2(source,destination)
                assert SHA(source)==SHA(destination)
            sourcefont=(folder/r['ttf']).parent
            for filename in ['OFL.txt','FONTLOG.txt']:shutil.copy2(sourcefont/filename,target/filename)
            if tier is None:
                (target/'FONTLOG.txt').write_text(f"{r['name']} {r['style']} 0.300\n2026-09-06: {r['description']}\n{r['codepoints']} supported codepoints. See METADATA.json for exact coverage, tags and QA scope.\nOriginal SSG procedural outlines. No third-party fonts or Reserved Font Names.\n", 'utf-8')
            (target/'METADATA.json').write_text(json.dumps(r,indent=2,ensure_ascii=False),'utf-8')
            engine.write_zip(DEST/r['download'],[(target/n,n) for n in [Path(r['ttf']).name,Path(r['woff2']).name,'OFL.txt','FONTLOG.txt','METADATA.json']])
    assert len(items)==2000
    for key in ['id','postscript_name','outline_sha256']:
        assert len({r[key] for r in items})==2000,('duplicate',key)
    counts={tier:sum(r['collection_tier']==tier for r in items) for tier in ['Core','Balanced','Experimental']}
    assert counts=={'Core':500,'Balanced':250,'Experimental':1250}
    rank={'Core':0,'Balanced':1,'Experimental':2}
    items.sort(key=lambda r:(rank[r['collection_tier']],abs(r['width_class']-5),abs(r['weight_class']-400),abs(r.get('slant',0)),r['design_root'],r['name'],r['style']))
    (DEST/'catalog.json').write_text(json.dumps(items,indent=2,ensure_ascii=False),'utf-8')
    with (DEST/'catalog.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['id','name','style','collection_tier','design_root','treatment','category','weight_class','width_class','slant_tag','codepoints','review_status','tags','ttf','woff2','download','sha256']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in items:writer.writerow({k:'; '.join(r[k]) if isinstance(r[k],list) else r[k] for k in fields})
    (DEST/'index.html').write_text((BASE/'catalog2000-template.html').read_text('utf-8-sig').replace('FONTDATA',json.dumps(items,ensure_ascii=False)),'utf-8')
    shutil.copy2(BASE/'OFL.txt',DEST/'OFL.txt')
    shutil.copytree(BUILD/'proofs',DEST/'proofs',dirs_exist_ok=True)
    report=dict(styles=2000,design_roots=10,family_treatment_slant_groups=len({r['root_id'] for r in items}),tiers=counts,
        preserved_font_binaries=1250,new_styles=750,unique_outline_and_metrics_hashes=2000,
        core_codepoints=sorted({r['codepoints'] for r in items if r['collection_tier']=='Core'}),
        core_maximum_alignment_error_units=max(r['core_checks']['alignment_error_units'] for r in items if r['collection_tier']=='Core'),
        core_minimum_kerned_bbox_gap_units=min(r['core_checks']['minimum_kerned_bbox_gap'] for r in items if r['collection_tier']=='Core'),
        ttf_bytes=sum(r['ttf_bytes'] for r in items),woff2_bytes=sum(r['woff2_bytes'] for r in items),
        checks=['2,000 unique IDs, PostScript names and outline/metric hashes','1,250 previous TTF/WOFF2 binaries copied without changes','750 new styles decoded, coverage/license/bounds checked, and FreeType rendered','500 core styles have fitted capitals, coherent body bowls and descenders, separate i/j dots, vector counters, conservative pair clearances, and raster checks at 16/24/48 px','OoBDP0 counter topology tested at 25% ink coverage threshold','All styles have metadata sidecars and search tags'],
        review_status='Automated QA passed. Individual optical review, long-reading, print and in-game visual checks pending.')
    for key in ['godot','browser']:
        proof=DEST/(key+'-validation.json')
        if proof.exists():report[key+'_checks']=json.loads(proof.read_text('utf-8'))
    (DEST/'validation.json').write_text(json.dumps(report,indent=2),'utf-8')
    (DEST/'REPORT.md').write_text("""# Steady State Games: 2,000 styles

## Count and scope
2,000 distinct styles, from 10 shared drawing roots and 80 family/treatment/slant groups. TTF and WOFF2 are two formats of each style, not separate fonts. These are procedural branches, not 2,000 independently drawn families.

- Core: 500 new styles. Five roots (Relay, Bastion, Vector, Ember, Spire), two x-height designs (Standard 500 units; Text 540), five widths, five weights, upright and oblique.
- Balanced: 250 previous proportion-corrected alternatives.
- Experimental: 1,250 styles, comprising the earlier 1,000 plus 250 new Ripple, Inline, Fracture, Backslant and Stack variants.

The original 1,250 font binaries remain unchanged. New collection ZIPs add metadata; the previous release folders are preserved.

## Core improvements
Fit centerline drawings before applying their strokes. Align capitals against a 700-unit cap height, with small point/curve allowances. Harmonize body bowls and ascenders/descenders separately. Rebuild Q tails and i/j dots. Strengthen nib strokes for small-size rendering. Add selected precomposed Western Latin accents, ligature characters, and currency/symbol glyphs.

The width range is restrained (88–112% centerline width), and stroke weights are less extreme than the experiments. The Text branch has larger lowercase and slightly wider spacing. Per-character sidebearings and accented counterparts of kerning pairs have at least 24 units of bounding-box clearance.

## What passed
See validation.json and each METADATA.json. All 750 new styles pass TTF/WOFF2 decoding, character/license, nonempty outline, vertical metrics, weight/width/slant metadata and FreeType checks. All 500 core styles additionally pass vector counter/dot/descender checks, alignment tests and raster checks at 16, 24 and 48 px. Raster counter topology uses a 25% ink-coverage threshold to retain antialiased thin edges.

All 2,000 fonts also passed installed Godot 4.7.2 FontFile loading, exact catalog character checks and text shaping at 16/24/48 px. This is a headless compatibility smoke test, not an in-game visual test. All 2,000 WOFF2 files loaded in Edge; catalog filters, coverage warnings and review controls passed browser checks. See godot-validation.json and browser-validation.json.\n\n## What Core does and does not mean
Core identifies the refined general-use branch and its additional checks. It is not universal certification or an individual optical sign-off. Five hundred fonts have not been manually approved for every reading context. These fonts still need human review for long-form reading, very small sizes, print, accessibility and Godot integration.

Coverage is basic Latin plus selected Western Latin accents/symbols. It is not all Unicode or complete Latin-1. Combining-mark shaping and other scripts are absent. Use precomposed accents; the browser normalizes preview input to NFC and flags unsupported characters. Manual hinting, advanced shaping and broad language/platform support remain future work.

## Browse and download
Open index.html. It starts with the core and loads only 20 visible webfonts at a time. Filter by collection, root, treatment, weight, width, slant, coverage or tags. Individual ZIPs include TTF, WOFF2, OFL.txt, FONTLOG.txt and METADATA.json.

Downloads: SSG-Core-500.zip; SSG-2000.zip; SSG-2000-Source.zip. The core ZIP has its own browser. Full tags are in catalog.json and catalog.csv. Review flags are stored locally in your browser and can be exported as JSON.

## Rebuild
The source archive includes scripts and the 1,250 baseline TTF/WOFF2 inputs needed to reproduce the combined catalog. See SOURCE-README.md inside it. Native work runs in one isolated Python process per style. All outlines are original SSG drawings; no outside font outlines enter the build.

All font software is licensed under OFL 1.1. See OFL.txt. Nothing was published to a remote site or added back to the game project.
""",'utf-8')
    (DEST/'TAGS.md').write_text("""# Font tags
Tags describe the files, not universal suitability.

collection_tier: Core, Balanced, Experimental.
design_root: one of the 10 original drawing roots.
category: rounded-sans, angular-sans, slab-serif, serif, broad-nib, stencil, double-line, outline, dot-matrix, pixel.
treatment: Original, Slant, Cut, Echo, Balanced, Core, Ripple, Inline, Fracture, Backslant, Stack.
weight_class / width_class: OpenType numeric values; the actual recipe scale is also retained.
slant_tag: upright, oblique, reverse-oblique. Generated slants are not independently drawn true italics.
coverage: exact codepoint_list is authoritative. western-latin-accents applies only to Core.
use_cases: suggestions such as headings, ui-candidate, body-text-candidate, posters, game-display.
review_status: optical-review-pending. Technical success does not imply universal readability.
Mood tags (friendly, fantasy, sci-fi, retro, etc.) are subjective browsing aids.

Metadata is in catalog.json, catalog.csv and each font's METADATA.json. Original font binaries were not rewritten to embed tags. The individual ZIP travels with its sidecar and license.
""",'utf-8')
    print(json.dumps(report,indent=2),flush=True)
    return items
def package(items):
    readme="""# Build the SSG 2,000-style collection
Use Python 3.14 with the pinned requirements (the original build used Pillow 12.3.0).
From this archive root:
python -m pip install -r workbench/requirements.txt
python workbench/build2000.py
python workbench/package2000.py

The archive includes preserved collection-1000 and collection-balanced inputs. The package step reads them without changing their font binaries.
Optional: python workbench/build2000.py --pilot, then python workbench/proofs2000.py to refresh representative proofs.
Browser verification uses the local Edge/Playwright setup in verify2000.cjs; update its runtime path for another machine.
"""
    (BASE/'SOURCE-README-2000.md').write_text(readme,'utf-8')
    sources=[(BASE/n,'workbench/'+n) for n in ['build.py','build250.py','build1000.py','core_geometry.py','build2000.py','package2000.py','proofs2000.py','catalog2000-template.html','requirements.txt','OFL.txt','sources/glyphs.py','sources/roots.json']]
    sources.append((BASE/'SOURCE-README-2000.md','SOURCE-README.md'))
    sources += [(BASE/'qa-godot'/n,'workbench/qa-godot/'+n) for n in ['project.godot','verify.gd']]
    for n in ['verify2000.cjs','verify2000-smoke.cjs']:
        if (BASE/n).exists():sources.append((BASE/n,'workbench/'+n))
    # Include existing proofs so a full rebuild can package without a separate pilot run.
    sources += [(p,'workbench/collection-2000/proofs/'+p.name) for p in (DEST/'proofs').glob('*.png')]
    for name in ['collection-1000','collection-balanced']:
        folder=ROOT/name;sources.append((folder/'catalog.json',name+'/catalog.json'))
        for r in json.loads((folder/'catalog.json').read_text('utf-8')):
            for key in ['ttf','woff2']:sources.append((folder/r[key],name+'/'+r[key]))
            for file in ['OFL.txt','FONTLOG.txt']:
                p=(folder/r['ttf']).parent/file;sources.append((p,name+'/'+p.relative_to(folder).as_posix()))
    engine.write_zip(DEST/'downloads/SSG-2000-Source.zip',sources)
    shared=[(DEST/n,n) for n in ['index.html','catalog.json','catalog.csv','OFL.txt','REPORT.md','TAGS.md','validation.json','godot-validation.json']]
    shared += [(p,p.relative_to(DEST).as_posix()) for p in (DEST/'proofs').glob('*.png')]
    for n in ['browser-validation.json','browser-preview.png','browser-overview.png','bundle-validation.json']:
        if (DEST/n).exists():shared.append((DEST/n,n))
    files=list(shared)
    for r in items:
        for key in ['ttf','woff2','download']:files.append((DEST/r[key],r[key]))
        for name in ['OFL.txt','FONTLOG.txt','METADATA.json']:
            p=(DEST/r['ttf']).parent/name;files.append((p,p.relative_to(DEST).as_posix()))
    engine.write_zip(DEST/'downloads/SSG-2000.zip',files)
    core=[r for r in items if r['collection_tier']=='Core']
    core_index=BUILD/'core-index.html'
    template=(BASE/'catalog2000-template.html').read_text('utf-8-sig')
    import re
    page=template.replace('FONTDATA',json.dumps(core,ensure_ascii=False))
    page=page.replace('Styles branch from 10 original drawing roots.','This bundle uses 5 original drawing roots.')
    page=page.replace('Steady State Games · 2,000 fonts','Steady State Games · 500 core fonts').replace('2,000 ways<br>to say something.','500 core styles.<br>Ready to explore.')
    page=page.replace('<strong>250</strong><span>BALANCED ALTERNATIVES</span>','<strong>10</strong><span>CORE DESIGNS</span>').replace('<strong>1,250</strong><span>EXPERIMENTAL STYLES</span>','<strong>2</strong><span>SLANTS PER DESIGN</span>')
    page=page.replace('<option value="">Everything / 2,000</option>','<option value="">All included styles / 500</option>').replace('<option value="Balanced">Balanced / 250</option>','').replace('<option value="Experimental">Experimental / 1,250</option>','')
    page=re.sub(r'<div class="links">.*?</div>','<div class="links"><a href="catalog.json">Core catalog + tags</a><a href="REPORT.md">Checks and limitations</a><a href="TAGS.md">Tag definitions</a></div>',page,flags=re.S)
    core_index.write_text(page,'utf-8')
    core_catalog=BUILD/'core-catalog.json'
    core_catalog.write_text(json.dumps(core,indent=2,ensure_ascii=False),'utf-8')
    corefiles=[(DEST/'OFL.txt','OFL.txt'),(DEST/'REPORT.md','REPORT.md'),(DEST/'TAGS.md','TAGS.md'),(core_index,'index.html'),(core_catalog,'catalog.json')]
    for r in core:
        for key in ['ttf','woff2','download']:corefiles.append((DEST/r[key],r[key]))
        for name in ['OFL.txt','FONTLOG.txt','METADATA.json']:
            p=(DEST/r['ttf']).parent/name;corefiles.append((p,p.relative_to(DEST).as_posix()))
    engine.write_zip(DEST/'downloads/SSG-Core-500.zip',corefiles)
    for name,count in [('SSG-2000.zip',2000),('SSG-Core-500.zip',500)]:
        with zipfile.ZipFile(DEST/'downloads'/name) as z:
            assert z.testzip() is None
            assert len(z.namelist())==len(set(z.namelist()))
            assert sum(n.endswith('.ttf') for n in z.namelist())==count
            assert sum(n.endswith('.woff2') for n in z.namelist())==count
            assert sum(n.endswith('METADATA.json') for n in z.namelist())==count
        print(name,(DEST/'downloads'/name).stat().st_size,'bytes; verified',flush=True)
    # This is build staging; earlier binaries stay in their preserved input releases.
    shutil.copy2(BUILD/'new-catalog.json',BUILD/'catalog.json')
    (BUILD/'README.md').write_text('Build staging for the 750 new styles. catalog.json and new-catalog.json index those new fonts. The complete tagged 2,000-style release is ../../collection-2000/. Earlier font inputs remain in the preserved collection-1000 and collection-balanced folders. Pilot artifacts are development files, not extra counted styles.\n','utf-8')
    shutil.copy2(DEST/'validation.json',BUILD/'validation.json')
    p=ROOT/'README.md';s=p.read_text('utf-8')
    s=s.replace('Latest release: open collection-1000/index.html. The installable TTF files are inside collection-1000/fonts, organized by style.','Latest release: open collection-2000/index.html. The installable TTF files are inside collection-2000/fonts, organized by style.')
    if '## 2,000-style' not in s:s+='\n## 2,000-style release\n\ncollection-2000/ contains 500 refined Core, 250 Balanced and 1,250 Experimental styles. The searchable browser includes tags, coverage warnings, and exportable review flags. Core is an automated-QA branch; individual optical and general-context review remains pending. See REPORT.md and TAGS.md in the collection. Sources: workbench/build2000.py and core_geometry.py.\n'
    p.write_text(s,'utf-8')
if __name__=='__main__':
    if '--package-only' in sys.argv:package(json.loads((DEST/'catalog.json').read_text('utf-8')))
    else:package(assemble())

