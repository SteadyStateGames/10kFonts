"""Proportion correction branch; originals remain unchanged."""
from pathlib import Path
import json,sys,subprocess,hashlib,shutil
from concurrent.futures import ThreadPoolExecutor
import build250 as stage
import build1000 as thousand
engine=stage.engine
RAW=engine.make_geometry
BASE=Path(__file__).resolve().parent
DEST=BASE/'collection-balanced'
ROOTS={'bastion','vector','rivet','ember','spire'}
def recipes():
    sources=stage.recipes()+[r for r in thousand.recipes() if r['treatment']=='Slant']
    result=[]
    for source in sources:
        base=source.get('design_root',source['root_id'])
        if base not in ROOTS: continue
        r=dict(source)
        r.update(source_id=source['id'],design_root=base,id=source['id']+'-balanced',name=source['name']+' Balanced',
                 root_id=source['root_id']+'-balanced',version='0.200',repair_affine_contacts=True,
                 description=source['description']+' Balanced centerline proportions; optical review prototype.')
        result.append(r)
    return result
def targets(ch,r):
    hb=RAW('H',r).bounds
    lo,hi=hb[1],hb[3]
    if ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' and ch!='Q':
        over=8 if ch in 'CGOSU' else 6 if ch in 'AVW' else 0
        return lo-over,hi+over
    if ch in '0123456789':
        over=8 if ch in '0235689' else 0
        return lo-over,hi+over
    if ch in 'acemnorsuvwxz':
        over=8 if ch in 'acemosu' else 6 if ch in 'vw' else 0
        return lo-over,480+(hi-700)+over
    if ch in 'bdhkl':
        return lo,hi
    return None
CACHE={}
def geometry(ch,r):
    key=(r['id'],ch)
    if key in CACHE: return CACHE[key]
    bounds=targets(ch,r)
    shape=RAW(ch,r)
    if bounds:
        targetlo,targethi=bounds
        a,b=1.,0.
        for iteration in range(12):
            lo,hi=shape.bounds[1],shape.bounds[3]
            if max(abs(lo-targetlo),abs(hi-targethi))<.65: break
            ratio=(targethi-targetlo)/(hi-lo)
            a*=ratio
            b=(b-lo)*ratio+targetlo
            shape=RAW(ch,dict(r,centerline_y=(a,b)))
        assert max(abs(shape.bounds[1]-targetlo),abs(shape.bounds[3]-targethi))<1.5,(r['id'],ch,shape.bounds,bounds)
    CACHE[key]=shape
    return shape
def worker(index):
    DEST.mkdir(exist_ok=True)
    (DEST/'fonts').mkdir(exist_ok=True);(DEST/'downloads').mkdir(exist_ok=True)
    engine.ROOT=DEST;engine.OUT=DEST/'fonts';engine.make_geometry=geometry
    r=recipes()[index]
    row=engine.build_font(r)
    with engine.TTFont(DEST/row['ttf']) as f:
        row['outline_sha256']=hashlib.sha256(f.getTableData('glyf')+f.getTableData('hmtx')).hexdigest()
        cmap=f.getBestCmap()
        errors=[]
        for ch in engine.CHARS:
            target=targets(ch,r)
            if target:
                g=f['glyf'][cmap[ord(ch)]]
                error=max(abs(g.yMin-target[0]),abs(g.yMax-target[1]))
                assert error<=2,(r['id'],ch,error)
                errors.append(error)
        row['max_alignment_error_units']=max(errors)
        row['checked_glyphs']=len(errors)
    print(json.dumps(row))
def run_worker(index):
    p=subprocess.run([sys.executable,__file__,'--worker',str(index)],capture_output=True,text=True,encoding='utf-8')
    if p.returncode: raise RuntimeError(f'{index}: {p.stderr}')
    return json.loads(p.stdout)
def main(pilot=False):
    indices=[i for i,r in enumerate(recipes()) if not pilot or (r['style'] in ('Regular','Regular Italic') and 'treatment' not in r)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=[]
        for row in pool.map(run_worker,indices):
            rows.append(row)
            if len(rows)%25==0 or pilot: print(f'{len(rows)}/{len(indices)} built: {row["id"]}',flush=True)
    assert len({r['outline_sha256'] for r in rows})==len(rows)
    (DEST/('pilot.json' if pilot else 'catalog.json')).write_text(json.dumps(rows,indent=2),'utf-8')
    shutil.copy2(BASE/'OFL.txt',DEST/'OFL.txt')
    print('Finished',len(rows),flush=True)
if __name__=='__main__':
    if '--worker' in sys.argv: worker(int(sys.argv[2]))
    else: main('--pilot' in sys.argv)

