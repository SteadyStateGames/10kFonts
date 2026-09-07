"""1,750 alignment-checked Balanced additions for a 500 / 2,000 / 7,500 collection.
Resume-safe: each validated style has a source-fingerprinted checkpoint.
"""
from pathlib import Path
import sys,json,hashlib,math,subprocess,os
from concurrent.futures import ThreadPoolExecutor,as_completed
import build250 as stage
import build_balanced as balanced
from shapely.geometry import box
from shapely.ops import unary_union,transform
from shapely import affinity,segmentize
engine=stage.engine;RAW=engine.make_geometry
BASE=Path(__file__).resolve().parent;DEST=BASE/'collection-balanced-2000'
FORMS=['Flow','Facet','Flare','Taper','Waist','Forward','Backlean']
FINISHES=['Solid','Edge','Scan','Offset']
BUILDER_SHA=hashlib.sha256(b''.join((BASE/n).read_bytes() for n in ['build_balanced2000.py','build_balanced.py','build.py','build250.py','sources/glyphs.py','sources/roots.json'])).hexdigest()
def recipes():
    rows=[]
    for form in FORMS:
        for source in stage.recipes():
            r=dict(source);group=source['root_id']+'-balanced-'+form.lower()
            slant=source.get('slant',0)+({'Forward':.12,'Backlean':-.12}.get(form,0))
            style=source['style'].replace(' Italic','')
            if abs(slant)>.001:style+=' Oblique' if slant>0 else ' Reverse'
            r.update(id=group+'-'+style.lower().replace(' ','-'),root_id=group,
                design_root=source['root_id'],name=source['name']+' Balanced '+form,
                style=style,treatment='Balanced '+form,balanced_form=form,
                source_slant=source.get('slant',0),slant=slant,
                collection_tier='Balanced',version='0.500',descent=500,auto_vertical_metrics=True,
                repair_affine_contacts=True,description=source['description']+' Conservative '+form.lower()+' shaping with checked cap, baseline and x-height alignment. Display use; individual optical review pending.')
            rows.append(r)
    assert len(rows)==1750
    return rows

GEOMETRY_CACHE={}
def geometry(ch,r):
    key=(r['id'],ch)
    if key in GEOMETRY_CACHE:return GEOMETRY_CACHE[key]
    source=dict(r,slant=r['source_slant'])
    if r['mode'] in ('dots','pixel'):
        shape=RAW(ch,source)
        target=balanced.targets(ch.upper() if ch.isalpha() else ch,source)
        if target:
            lo,hi=shape.bounds[1],shape.bounds[3]
            shape=affinity.translate(affinity.scale(shape,yfact=(target[1]-target[0])/(hi-lo),origin=(0,lo)),yoff=target[0]-lo)
    else:shape=balanced.geometry(ch,source)
    original=shape
    form=r['balanced_form'];shape=segmentize(shape,25)
    def warp(x,y,z=None):
        t=max(0,min(1,y/700))
        if form=='Flow':return x+16*math.sin(y/150),y
        if form=='Facet':return x+14*(2/math.pi)*math.asin(math.sin(y/125)),y
        if form=='Flare':return x*(.92+.16*t),y
        if form=='Taper':return x*(1.08-.16*t),y
        if form=='Waist':return x*(.93+.14*((y-350)/350)**2),y
        if form=='Forward':return x+.12*y,y
        return x-.12*y,y
    shape=transform(warp,shape).simplify(.25,preserve_topology=True)
    if not shape.is_valid:shape=shape.buffer(0)
    assert shape.is_valid and not shape.is_empty,(r['id'],ch)
    def holes(g):return sum(len(p.interiors) for p in ([g] if g.geom_type=='Polygon' else g.geoms) if p.geom_type=='Polygon')
    assert holes(shape)>=holes(original),('Lost counter',r['id'],ch)
    assert max(abs(shape.bounds[i]-original.bounds[i]) for i in [1,3])<.7,('Vertical drift',r['id'],ch)
    GEOMETRY_CACHE[key]=shape
    return shape

def worker(index):
    r=recipes()[index]
    (DEST/'fonts').mkdir(parents=True,exist_ok=True)
    (DEST/'downloads').mkdir(exist_ok=True)
    engine.ROOT=DEST;engine.OUT=DEST/'fonts';engine.make_geometry=geometry
    row=engine.build_font(r)
    with engine.TTFont(DEST/row['ttf']) as f:
        row['outline_sha256']=hashlib.sha256(f.getTableData('glyf')+f.getTableData('hmtx')).hexdigest()
        row['postscript_name']=f['name'].getDebugName(6)
        assert len(row['postscript_name'])<=63
        assert f['OS/2'].usWeightClass==r['weight_class']
        assert f['OS/2'].usWidthClass==r['width_class']
        assert abs(f['post'].italicAngle+math.degrees(math.atan(r['slant'])))<.001
        row['codepoint_list']=sorted(f.getBestCmap())
        row['vertical_ascent']=f['OS/2'].usWinAscent
    row['alignment_checked_glyphs']=0
    row['max_alignment_error_units']=0
    source=dict(r,slant=r['source_slant'])
    with engine.TTFont(DEST/row['ttf']) as f:
        cmap=f.getBestCmap()
        for ch in engine.CHARS:
            target=balanced.targets(ch.upper() if r['mode'] in ('dots','pixel') and ch.isalpha() else ch,source)
            if not target:continue
            g=f['glyf'][cmap[ord(ch)]];error=max(abs(g.yMin-target[0]),abs(g.yMax-target[1]))
            assert error<=2,(r['id'],ch,error)
            row['alignment_checked_glyphs']+=1
            row['max_alignment_error_units']=max(row['max_alignment_error_units'],error)
    row['woff2_sha256']=hashlib.sha256((DEST/row['woff2']).read_bytes()).hexdigest()
    row['builder_sha']=BUILDER_SHA
    checkpoint=DEST/'checkpoints'/f'{index:04d}.json';checkpoint.parent.mkdir(exist_ok=True)
    checkpoint.write_text(json.dumps(row),'utf-8')
    print(json.dumps({'id':row['id'],'checkpoint':str(checkpoint)}))
def run_worker(index):
    checkpoint=DEST/'checkpoints'/f'{index:04d}.json'
    if checkpoint.exists():
        row=json.loads(checkpoint.read_text('utf-8'))
        if row.get('builder_sha')==BUILDER_SHA and all((DEST/row[k]).is_file() for k in ['ttf','woff2','download']):
            if hashlib.sha256((DEST/row['ttf']).read_bytes()).hexdigest()==row['sha256'] and hashlib.sha256((DEST/row['woff2']).read_bytes()).hexdigest()==row['woff2_sha256']:
                return row
    for attempt in range(3):
        p=subprocess.run([sys.executable,__file__,'--worker',str(index)],capture_output=True,text=True,encoding='utf-8')
        if p.returncode==0:return json.loads(checkpoint.read_text('utf-8'))
        transient=p.returncode!=1 or "'tuple' object is not an iterator" in p.stderr or 'can only append array (not "int") to array' in p.stderr
        if not transient or attempt==2:raise RuntimeError(f'Style {index}: {p.stderr[-5000:]} (exit {p.returncode})')
    raise RuntimeError(index)
def main(pilot=False):
    (DEST/'checkpoints').mkdir(parents=True,exist_ok=True)
    allrecipes=recipes()
    indices=[i for i,r in enumerate(allrecipes) if not pilot or (r['weight_class']==400 and r['width_class']==5)]
    signatures={r['outline_sha256'] for r in json.loads((BASE.parent/'collection-10000/catalog.json').read_text('utf-8'))}
    rows={}
    pool=ThreadPoolExecutor(max_workers=int(os.environ.get('SSG_FONT_WORKERS','10')))
    tasks={pool.submit(run_worker,i):i for i in indices}
    try:
        for task in as_completed(tasks):
            row=task.result()
            assert row['outline_sha256'] not in signatures,('Duplicate outline/metrics',row['id'])
            signatures.add(row['outline_sha256']);rows[tasks[task]]=row
            if len(rows)%100==0 or len(rows)==len(indices):
                print(f'{len(rows)}/{len(indices)} new styles built and validated',flush=True)
                (DEST/'progress.json').write_text(json.dumps({'completed':len(rows),'target':len(indices),'pilot':pilot}),'utf-8')
    except BaseException:
        pool.shutdown(wait=True,cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    result=[rows[i] for i in sorted(rows)]
    (DEST/('pilot.json' if pilot else 'new-catalog.json')).write_text(json.dumps(result,indent=2),'utf-8')
    print('DONE',len(result),flush=True)
if __name__=='__main__':
    if '--worker' in sys.argv:worker(int(sys.argv[2]))
    else:main('--pilot' in sys.argv)

