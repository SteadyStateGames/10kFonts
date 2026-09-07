from pathlib import Path
import json
import build as e
BASE=Path(__file__).resolve().parent;DEST=BASE/'collection-balanced-2000'
rows=json.loads((DEST/'pilot.json').read_text('utf-8'))
(DEST/'proofs').mkdir(exist_ok=True)
for root in ['relay','bastion','vector','rivet','orbit','ember','signal','quarry','ribbon','spire']:
    chosen=[r for r in rows if r['design_root']==root]
    im=e.Image.new('RGB',(1450,1450),'#f4f1e7');d=e.ImageDraw.Draw(im)
    ui=e.ImageFont.load_default(size=20)
    d.text((35,25),root.upper()+' / BALANCED ALIGNMENT STUDY',font=e.ImageFont.load_default(size=32),fill='#21332e')
    for i,r in enumerate(chosen):
        x=35+(i%2)*700;y=95+(i//2)*330
        d.text((x,y),r['treatment'],font=ui,fill='#a7472a')
        p=DEST/r['ttf']
        d.text((x,y+35),'AVAW HO',font=e.ImageFont.truetype(str(p),58),fill='#21332e')
        d.text((x,y+115),'Ava waves. Wayward.',font=e.ImageFont.truetype(str(p),30),fill='#21332e')
        d.line((x,y+230,x+650,y+230),fill='#bdc7b6')
    im.save(DEST/'proofs'/(root+'-balanced.png'))
print('Three treatment contact sheets rendered.')

