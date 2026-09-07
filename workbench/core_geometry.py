"""Original core refinements. No third-party outlines. Geometry units: 1000 UPM."""
import math,unicodedata
from functools import lru_cache
import build as engine
from shapely.geometry import LineString,Point,box
from shapely.ops import unary_union
from shapely import affinity
RAW=engine.make_geometry
PATHS=engine.paths_for
BASE_CHARS=list(engine.CHARS)
ACCENTS={}
for cp in list(range(0xC0,0x100))+[0x178]:
    ch=chr(cp);parts=unicodedata.normalize('NFD',ch)
    if len(parts)==2 and parts[0].isascii() and parts[1] in '\u0300\u0301\u0302\u0303\u0308\u030a\u0327':
        ACCENTS[ch]=parts
EXTRAS='ÆæØøÐðÞþßŒœ£€¥©®°×÷¡¿«»'
CORE_CHARS=sorted(set(BASE_CHARS+list(ACCENTS)+list(EXTRAS)),key=ord)
CACHE={}
def paths(ch,r):
    return PATHS(ch,r['mode'])
def fit(paths_,r,bounds=None):
    previous=engine.paths_for
    engine.paths_for=lambda ch,mode:paths_
    try:
        a,b=1.,0.
        for i in range(16):
            result=RAW('H',dict(r,centerline_y=(a,b)))
            if bounds is None:break
            lo,hi=result.bounds[1],result.bounds[3]
            if max(abs(lo-bounds[0]),abs(hi-bounds[1]))<.6:break
            ratio=(bounds[1]-bounds[0])/(hi-lo)
            a*=ratio;b=(b-lo)*ratio+bounds[0]
        if bounds:
            assert max(abs(result.bounds[1]-bounds[0]),abs(result.bounds[3]-bounds[1]))<1.2,('fit',r['id'],bounds,result.bounds)
        return result
    finally:engine.paths_for=previous
def drawing(svg):
    pen=engine.FlattenPen()
    for s in svg:engine.parse_path(s,pen)
    return pen.paths
def translated_center(shape,x,y):
    a,b,c,d=shape.bounds
    return affinity.translate(shape,xoff=x-(a+c)/2,yoff=y-b)
def accent(mark,r):
    w=max(20,min(34,r['weight']*.32))
    if mark=='\u030a':
        return Point(0,50).buffer(52,quad_segs=12).difference(Point(0,50).buffer(52-w,quad_segs=12))
    if mark=='\u0308':
        return unary_union([Point(-55,30).buffer(w*.72,quad_segs=8),Point(55,30).buffer(w*.72,quad_segs=8)])
    points={'\u0300':[(50,0),(-35,90)],'\u0301':[(-50,0),(35,90)],
      '\u0302':[(-95,0),(0,80),(95,0)],'\u0303':[(-95,25),(-50,60),(50,5),(95,40)],
      '\u0327':[(15,10),(-15,-45),(40,-65),(35,-100),(-35,-110)]}[mark]
    return LineString(points).buffer(w/2,cap_style=1,join_style=1)
def simple_target(ch,r):
    x=r['x_height']
    if ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' and ch!='Q':
        o=8 if ch in 'CGOSU' else 6 if ch in 'AVW' else 0
        return -o,700+o
    if ch.isascii() and ch.isdigit():
        o=8 if ch in '0235689' else 0
        return -o,700+o
    if ch in 'cemnorsuvwxz':
        o=8 if ch in 'cemosu' else 6 if ch in 'vw' else 0
        return -o,x+o
    return None
def geometry(ch,r):
    key=(r['id'],ch)
    if key in CACHE:return CACHE[key]
    x=r['x_height'];slant=r.get('slant',0)
    target=simple_target(ch,r)
    if target:shape=fit(paths(ch,r),r,target)
    elif ch in 'abdg pq'.replace(' ',''):
        pp=paths(ch,r)
        stembounds=(0,x) if ch=='a' else (0,700) if ch in 'bd' else (-210,x)
        shape=unary_union([fit([pp[0]],r,stembounds),fit(pp[1:],r,(-8,x+8))])
    elif ch=='h':
        pp=paths(ch,r)
        shape=unary_union([fit(pp[:1],r,(0,700)),fit(pp[1:],r,(0,x))])
    elif ch=='k':
        pp=paths(ch,r)
        shape=unary_union([fit(pp[:1],r,(0,700)),fit(pp[1:],r,(0,x))])
    elif ch=='l':shape=fit(paths(ch,r),r,(0,700))
    elif ch in 'ij':
        pp=paths(ch,r)
        stem=fit(pp[:1],r,(-210 if ch=='j' else 0,x))
        dot_y=x+95
        dot_x=pp[-1][0][0]*r.get('path_width',1)*r['width']+slant*dot_y
        dot=Point(dot_x,dot_y).buffer(max(24,min(34,r['weight']*.42)),quad_segs=12)
        shape=unary_union([stem,dot])
    elif ch=='y':shape=fit(paths(ch,r),r,(-210,x+6))
    elif ch in 'ft':
        pp=paths(ch,r)
        stem=fit(pp[:1],r,(0,700 if ch=='f' else 640))
        bar=fit(pp[1:],r)
        # Move the crossbar with the body height; do not thin it.
        offset=x-35-(bar.bounds[1]+bar.bounds[3])/2
        bar=affinity.translate(bar,xoff=offset*slant,yoff=offset)
        shape=unary_union([stem,bar])
    elif ch=='Q':
        shape=unary_union([geometry('O',r),fit(paths('Q',r)[1:],r,(-120,190))])
    elif ch in ACCENTS:
        base,mark=ACCENTS[ch]
        if base=='i':base_shape=fit(paths('i',r)[:1],r,(0,x))
        else:base_shape=geometry(base,r)
        a,b,c,d=base_shape.bounds
        deco=accent(mark,r)
        if mark=='\u0327':deco=translated_center(deco,(a+c)/2,b-110)
        else:deco=translated_center(deco,(a+c)/2+slant*75,d+42)
        shape=unary_union([base_shape,deco])
    elif ch in 'Øø':
        base=geometry('O' if ch=='Ø' else 'o',r);a,b,c,d=base.bounds
        slash=LineString([(a+30,b+20),(c-30,d-20)]).buffer(max(18,r['weight']*.28),cap_style=2)
        shape=unary_union([base,slash])
    elif ch in 'ÆæŒœ':
        left=geometry(('A' if ch=='Æ' else 'a') if ch in 'Ææ' else ('O' if ch=='Œ' else 'o'),r)
        right=geometry('E' if ch.isupper() else 'e',r)
        left=affinity.scale(left,xfact=.78,yfact=1,origin=(0,0))
        right=affinity.scale(right,xfact=.78,yfact=1,origin=(0,0))
        right=affinity.translate(right,xoff=left.bounds[2]-right.bounds[0]-r['weight']*.3)
        shape=unary_union([left,right])
    elif ch in 'Ðð':
        base=geometry('D' if ch=='Ð' else 'd',r);a,b,c,d=base.bounds
        bar=LineString([(a-35,360 if ch=='Ð' else 610),(a+(c-a)*.55,360 if ch=='Ð' else 610)]).buffer(r['weight']*.23,cap_style=2)
        shape=unary_union([base,bar])
    elif ch in 'Þþ':
        stem=drawing(['M0 -200 L0 700'])
        bowl=drawing(['M0 0 L240 0 C550 0 550 480 240 480 L0 480'])
        shape=unary_union([fit(stem,r,(0,700) if ch=='Þ' else (-210,700)),fit(bowl,r,(170,550) if ch=='Þ' else (-8,x+8))])
    elif ch=='ß':
        pp=drawing(['M0 0 L0 510 C0 760 330 755 330 540 C330 410 170 410 190 340 C220 280 400 315 400 155 C400 -30 200 -15 155 30'])
        shape=fit(pp,r,(-8,708))
    elif ch in '¡¿':
        shape=affinity.rotate(geometry('!' if ch=='¡' else '?',r),180,origin='center')
    elif ch in '«»':
        one=affinity.scale(geometry('<' if ch=='«' else '>',r),xfact=.5,yfact=.65,origin=(0,300))
        shape=unary_union([one,affinity.translate(one,xoff=230*r['path_width'])])
    elif ch in '×÷':
        if ch=='×':shape=affinity.rotate(geometry('+',r),45,origin='center')
        else:
            base=geometry('-',r);a,b,c,d=base.bounds;mid=(a+c)/2
            shape=unary_union([base,Point(mid,100).buffer(r['weight']*.36),Point(mid,430).buffer(r['weight']*.36)])
    elif ch=='°':
        shape=Point(110,615).buffer(90,quad_segs=16).difference(Point(110,615).buffer(90-max(24,r['weight']*.4),quad_segs=16))
    elif ch in '©®':
        ring=Point(300,350).buffer(325,quad_segs=20).difference(Point(300,350).buffer(300,quad_segs=20))
        inside=affinity.scale(geometry('C' if ch=='©' else 'R',r),xfact=.5,yfact=.6,origin=(0,0))
        shape=unary_union([ring,translated_center(inside,300,140)])
    elif ch in '£€¥':
        if ch=='£':
            pp=drawing(['M480 625 C200 800 100 645 130 430 L130 90 Q110 0 0 0 L470 0','M10 320 L345 320'])
        elif ch=='€':
            pp=drawing(['M500 600 C400 765 0 765 0 350 C0 -65 400 -65 500 100','M-40 440 L360 440','M-40 265 L340 265'])
        else:
            pp=paths('Y',r)+drawing(['M30 300 L490 300','M30 160 L490 160'])
        shape=fit(pp,r,(0,700))
    else:shape=RAW(ch,r)
    shape=shape.simplify(.35,preserve_topology=True)
    if not shape.is_valid:shape=shape.buffer(0)
    assert shape.is_valid and not shape.is_empty,(r['id'],ch)
    CACHE[key]=shape
    return shape
def configure(r):
    engine.CHARS=CORE_CHARS
    engine.make_geometry=geometry
    sidebearings={}
    for ch in CORE_CHARS:
        base=ACCENTS.get(ch,ch)[0]
        factor=.8 if base in 'AVWTYvwy' else .82 if base in 'il' else .92 if base in 'COGSaceos' else 1.
        side=round(r['tracking']*factor)
        sidebearings[ch]=(side,side)
    r['sidebearings']=sidebearings
    basepairs={}
    for pair in ['AV','AW','AY','AT','FA','LT','LV','LY','PA','TA','TO','Ta','Te','To','Tr','Tu','VA','Va','Ve','Vo','WA','Wa','We','Wo','YA','Ya','Ye','Yo','Ty','Tw','Va','Vy','Wa','Wo','Yo','LA','FA','Fo','Fe','Fi','F.','P.','T.','V.','W.','Y.','r.','v.','w.','y.']:
        basepairs[pair]=-38 if r['optical']=='Text' else -45
    kern={}
    for pair,value in basepairs.items():
        for a in [c for c in CORE_CHARS if ACCENTS.get(c,c)[0]==pair[0]]:
            for b in [c for c in CORE_CHARS if ACCENTS.get(c,c)[0]==pair[1]]:
                # Conservative positive bounding-box clearance even after kerning.
                kern[a+b]=max(value,24-sidebearings[a][1]-sidebearings[b][0])
    r['kerning_pairs']=kern

