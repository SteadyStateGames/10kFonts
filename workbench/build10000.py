"""8,000 experimental branches + 2,000 preserved styles = 10,000.
Resume-safe: each validated style has a source-fingerprinted checkpoint.
"""
from pathlib import Path
import sys,json,hashlib,math,subprocess,os
from concurrent.futures import ThreadPoolExecutor,as_completed
import build250 as stage
from shapely.geometry import box
from shapely.ops import unary_union,transform
from shapely import affinity,segmentize
engine=stage.engine;RAW=engine.make_geometry
BASE=Path(__file__).resolve().parent;DEST=BASE/'collection-10000'
FORMS=['Surge','Zigzag','Wedge','Pinch','Arch','Bounce','Forward','Slope']
FINISHES=['Solid','Edge','Scan','Offset']
BUILDER_SHA=hashlib.sha256(b''.join((BASE/n).read_bytes() for n in ['build10000.py','build.py','build250.py','sources/glyphs.py','sources/roots.json'])).hexdigest()
def recipes():
    rows=[]
    for form in FORMS:
        for finish in FINISHES:
            for source in stage.recipes():
                r=dict(source);group=source['root_id']+'-'+form.lower()+'-'+finish.lower()
                style=source['style']
                slant=source.get('slant',0)
                if form=='Forward':
                    slant+=.28
                    if 'Italic' not in style:style+=' Oblique'
                r.update(id=group+'-'+style.lower().replace(' ','-'),root_id=group,
                    design_root=source['root_id'],name=source['name']+' '+form+' '+finish,
                    style=style,treatment=form+' '+finish,form=form,finish=finish,
                    source_slant=source.get('slant',0),slant=slant,
                    collection_tier='Experimental',version='0.400',descent=500,auto_vertical_metrics=True,
                    repair_affine_contacts=True,description=source['description']+' '+form+' geometry with '+finish.lower()+' finish. Experimental display branch.')
                rows.append(r)
    assert len(rows)==8000
    return rows
def geometry(ch,r):
    shape=RAW(ch,dict(r,slant=r['source_slant']))
    finish=r['finish']
    if finish=='Edge':
        # Always expands the outer contour, even for already-hollow roots.
        shape=shape.buffer(7,join_style=1).difference(shape.buffer(-8,join_style=1))
    elif finish=='Scan' and ch.isalnum():
        shape=shape.difference(unary_union([box(-700,y-7,2300,y+7) for y in [140,300,460,620]]))
    elif finish=='Offset':
        shadow=affinity.translate(shape,xoff=55,yoff=-35).difference(shape.buffer(10,join_style=1))
        shape=unary_union([shape,shadow])
    form=r['form']
    if form in ['Surge','Zigzag','Wedge','Pinch','Arch','Bounce']:
        shape=segmentize(shape,22)
    def warp(x,y,z=None):
        if form=='Surge':return x+42*math.sin(y/120),y
        if form=='Zigzag':return x+38*(2/math.pi)*math.asin(math.sin(y/105)),y
        if form=='Wedge':return x*(.76+.48*max(0,min(700,y))/700),y
        if form=='Pinch':return x*(.78+.36*((y-350)/350)**2),y
        if form=='Arch':return x,y+58*math.sin(math.pi*x/700)
        if form=='Bounce':return x,y+37*math.sin(x/90)
        if form=='Forward':return x+.28*y,y
        return x,y+.065*x
    shape=transform(warp,shape).simplify(.4,preserve_topology=True)
    if not shape.is_valid:shape=shape.buffer(0)
    assert shape.is_valid and not shape.is_empty,(r['id'],ch)
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
        transient=p.returncode!=1 or "'tuple' object is not an iterator" in p.stderr
        if not transient or attempt==2:raise RuntimeError(f'Style {index}: {p.stderr[-5000:]} (exit {p.returncode})')
    raise RuntimeError(index)
def main(pilot=False):
    (DEST/'checkpoints').mkdir(parents=True,exist_ok=True)
    allrecipes=recipes()
    indices=[i for i,r in enumerate(allrecipes) if not pilot or (r['weight_class']==400 and r['width_class']==5)]
    signatures={r['outline_sha256'] for r in json.loads((BASE.parent/'collection-2000/catalog.json').read_text('utf-8'))}
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

