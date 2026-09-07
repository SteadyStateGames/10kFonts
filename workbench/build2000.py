"""Build the 2,000-style release, retaining the earlier 1,250 font binaries."""
from pathlib import Path
import json,hashlib,subprocess,sys,shutil,math
from concurrent.futures import ThreadPoolExecutor
import build250 as stage
import core_geometry as core
from shapely.geometry import LineString,box
from shapely.ops import unary_union,transform
from shapely import affinity,segmentize
engine=stage.engine;RAW=engine.make_geometry
BASE=Path(__file__).resolve().parent;DEST=BASE/'collection-2000'
def recipes():
    result=[]
    widths=[('Condensed',.88,3),('SemiCondensed',.94,4),('',1.,5),('SemiExpanded',1.06,6),('Expanded',1.12,7)]
    weights=[('Book',.78,350),('Regular',.9,400),('Medium',1.02,500),('SemiBold',1.14,600),('Bold',1.26,700)]
    for root in engine.RECIPES:
        if root['id'] not in {'relay','bastion','vector','ember','spire'}:continue
        for optical in ['Standard','Text']:
            for slant in [0,.14]:
                for width,scale,wclass in widths:
                    for weight,factor,wgtclass in weights:
                        style=' '.join(s for s in [width,weight,'Oblique' if slant else ''] if s)
                        group=root['id']+'-core-'+optical.lower()+('-oblique' if slant else '')
                        name=root['name']+' Core'+(' Text' if optical=='Text' else '')
                        r=dict(root)
                        r.update(id=group+'-'+style.lower().replace(' ','-'),root_id=group,name=name,design_root=root['id'],
                            style=style,optical=optical,collection_tier='Core',treatment='Core',version='0.300',
                            weight=round((80 if root['id'] in ('relay','vector') else 84)*factor),
                            path_width=scale,width=.96 if root['id']=='spire' else 1.,
                            weight_class=wgtclass,width_class=wclass,slant=slant,x_height=540 if optical=='Text' else 500,
                            tracking=52 if optical=='Text' else 47,nib_height_scale=1.45,hairline=(23 if optical=='Text' else 19)*factor,
                            miter_limit=1.8,optical_symbols=True,repair_affine_contacts=True,
                            description='Refined '+root['id']+' core with '+optical.lower()+' x-height, matched bowls and descenders, accented Latin, and conservative spacing.')
                        result.append(r)
    effects={'relay':'Ripple','ember':'Ripple','bastion':'Inline','rivet':'Inline','vector':'Fracture','quarry':'Fracture','orbit':'Backslant','signal':'Backslant','spire':'Stack','ribbon':'Stack'}
    for source in stage.recipes():
        effect=effects[source['root_id']]
        r=dict(source)
        r.update(id=source['id']+'-'+effect.lower(),root_id=source['root_id']+'-'+effect.lower(),design_root=source['root_id'],
            name=source['name']+' '+effect,treatment=effect,collection_tier='Experimental',version='0.300',
            descent=440,repair_affine_contacts=True,description=source['description']+' '+effect+' experimental effect.')
        if effect=='Backslant':
            r['slant']=-.24
            r['style']+=' Reverse Oblique'
        result.append(r)
    assert len(result)==750
    return result
def effect_geometry(ch,r):
    if r['treatment']=='Backslant':return RAW(ch,dict(r,slant=-.24))
    shape=RAW(ch,r)
    if not ch.isalnum():return shape
    effect=r['treatment']
    if effect=='Ripple':
        shape=segmentize(shape,18)
        shape=transform(lambda x,y,z=None:(x+28*math.sin(y/95),y),shape)
    elif effect=='Inline':
        # Hollow slab/stencil silhouettes, distinct from the round Ribbon root.
        shape=shape.difference(shape.buffer(-max(13,r['weight']*.23),join_style=2))
    elif effect=='Fracture':
        cuts=unary_union([LineString([(-300,y),(1600,y+90)]).buffer(12,cap_style=2) for y in (160,380,600)])
        shape=shape.difference(cuts)
    elif effect=='Stack':
        layers=[shape]
        for dx,dy in [(38,-38),(76,-76)]:
            layers.append(affinity.translate(shape,xoff=dx,yoff=dy).difference(shape.buffer(10)))
        shape=unary_union(layers)
    shape=shape.simplify(.35,preserve_topology=True)
    if not shape.is_valid:shape=shape.buffer(0)
    assert shape.is_valid and not shape.is_empty,(r['id'],ch)
    return shape
def raster_holes(mask):
    w,h=mask.size;raw=list(mask)
    white={(x,y) for y in range(h) for x in range(w) if raw[y*w+x]<64}
    holes=0
    while white:
        start=white.pop();stack=[start];edge=False;area=0
        while stack:
            x,y=stack.pop();area+=1
            if x in (0,w-1) or y in (0,h-1):edge=True
            for pt in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
                if pt in white:white.remove(pt);stack.append(pt)
        if not edge and area>=1:holes+=1
    return holes
def validate_core(r,ttf):
    with engine.TTFont(ttf) as f:
        cmap=f.getBestCmap()
        errors=[]
        for ch in engine.CHARS:
            bounds=core.simple_target(ch,r)
            if bounds:
                glyph=f['glyf'][cmap[ord(ch)]]
                error=max(abs(glyph.yMin-bounds[0]),abs(glyph.yMax-bounds[1]))
                assert error<=2,(r['id'],ch,error)
                errors.append(error)
        # Descenders must exist; i/j dots must remain separate in vector outlines.
        for ch in 'gjpqy':
            assert f['glyf'][cmap[ord(ch)]].yMin<=-200,(r['id'],ch,'missing descender')
        for ch in 'ij':
            s=core.geometry(ch,r)
            assert s.geom_type=='MultiPolygon' and len(s.geoms)>=2,(r['id'],ch,'dot merged')
        for ch in 'abdegopqBOPR0689':
            s=core.geometry(ch,r)
            ps=[s] if s.geom_type=='Polygon' else list(s.geoms)
            assert sum(len(p.interiors) for p in ps)>=1,(r['id'],ch,'closed counter')
        min_gap=min(r['sidebearings'][pair[0]][1]+r['sidebearings'][pair[1]][0]+value for pair,value in r['kerning_pairs'].items())
        assert min_gap>=24
        checks={}
        for size in [16,24,48]:
            face=engine.ImageFont.truetype(str(ttf),size)
            for ch in engine.CHARS:
                if not ch.isspace():assert face.getmask(ch).getbbox(),(r['id'],ch,size,'blank')
            for ch in 'OoBDP0':
                assert raster_holes(face.getmask(ch,mode='L'))>=1,(r['id'],ch,size,'raster counter lost at 25% ink coverage')
            checks[str(size)]='rendered all nonspace glyphs; OoBDP0 counters open'
        return dict(alignment_error_units=max(errors),alignment_glyphs=len(errors),minimum_kerned_bbox_gap=min_gap,raster_checks=checks)
def worker(index):
    r=recipes()[index]
    DEST.mkdir(exist_ok=True);(DEST/'fonts').mkdir(exist_ok=True);(DEST/'downloads').mkdir(exist_ok=True)
    engine.ROOT=DEST;engine.OUT=DEST/'fonts'
    if r['collection_tier']=='Core':core.configure(r)
    else:engine.make_geometry=effect_geometry
    row=engine.build_font(r)
    with engine.TTFont(DEST/row['ttf']) as f:
        row['outline_sha256']=hashlib.sha256(f.getTableData('glyf')+f.getTableData('hmtx')).hexdigest()
        assert f['OS/2'].usWeightClass==r['weight_class']
        assert f['OS/2'].usWidthClass==r['width_class']
        assert abs(f['post'].italicAngle+math.degrees(math.atan(r.get('slant',0))))<.001
    if r['collection_tier']=='Core':
        row['core_checks']=validate_core(r,DEST/row['ttf'])
        row['kerning_pair_count']=len(r['kerning_pairs'])
        row.pop('sidebearings');row.pop('kerning_pairs')
    row['codepoint_list']=[ord(c) for c in engine.CHARS]
    print(json.dumps(row))
def run_worker(index):
    p=subprocess.run([sys.executable,__file__,'--worker',str(index)],capture_output=True,text=True,encoding='utf-8')
    if p.returncode:raise RuntimeError(f'{index}: {p.stderr}')
    return json.loads(p.stdout)
def main(pilot=False):
    DEST.mkdir(exist_ok=True);(DEST/'fonts').mkdir(exist_ok=True);(DEST/'downloads').mkdir(exist_ok=True)
    chosen=[i for i,r in enumerate(recipes()) if not pilot or (r['style'] in ('Regular','Regular Italic') and (r.get('slant',0)==0 or r['collection_tier']!='Core'))]
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(run_worker,chosen):
            rows.append(row)
            if pilot or len(rows)%25==0:print(f'{len(rows)}/{len(chosen)} new styles validated: {row["id"]}',flush=True)
    (DEST/('pilot.json' if pilot else 'new-catalog.json')).write_text(json.dumps(rows,indent=2),'utf-8')
if __name__=='__main__':
    if '--worker' in sys.argv:worker(int(sys.argv[2]))
    else:main('--pilot' in sys.argv)

