"""Publish the prepared library only with explicit --publish and local GitHub auth."""
from pathlib import Path
import json,subprocess,hashlib,argparse,time,datetime
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;HOST=ROOT/'hosting-refined'
def command(args,cwd=None,check=True):
    p=subprocess.run(args,cwd=cwd,capture_output=True,text=True,encoding='utf-8')
    if check and p.returncode:raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p
def gh(*args,check=True):
    return command(['gh',*args],check=check)
def api(path,check=True):
    p=gh('api',path,check=check)
    return json.loads(p.stdout) if p.returncode==0 else None
def publish(owner,repo):
    plan=json.loads((HOST/'deployment-plan.json').read_text('utf-8'))
    assert plan['owner']==owner and plan['repository']==repo
    login=gh('api','user','--jq','.login').stdout.strip()
    if login.casefold()!=owner.casefold():raise RuntimeError('Sign into the specified owner account before publishing.')
    fullname=owner+'/'+repo;source=HOST/'source';tag=plan['release']
    for r in plan['assets']:
        p=HOST/r['path']
        assert p.stat().st_size==r['size'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],r['name']
    existing=api('repos/'+fullname,check=False)
    initial_license_only=False
    if existing:
        marker=api('repos/'+fullname+'/contents/ssg-library.json',check=False)
        empty=gh('repo','view',fullname,'--json','isEmpty').stdout
        if marker is None and not json.loads(empty)['isEmpty']:
            tree=api('repos/'+fullname+'/git/trees/'+existing['default_branch']+'?recursive=1')
            initial_license_only=not tree.get('truncated') and [(r['path'],r['type']) for r in tree['tree']]==[('LICENSE','blob')]
            if not initial_license_only:raise RuntimeError('Refusing to write into an unrelated nonempty repository.')
        if marker:
            import base64
            identity=json.loads(base64.b64decode(marker['content']))
            if identity.get('project')!='steady-state-games-font-library':
                raise RuntimeError('Repository belongs to a different project.')
    else:
        gh('repo','create',fullname,'--public','--description','Original OFL font library: 500 refined core styles and thousands of display experiments.','--disable-wiki')
    remote=api('repos/'+fullname)['clone_url']
    if not (source/'.git').exists():command(['git','init','-b','main'],source)
    top=command(['git','rev-parse','--show-toplevel'],source).stdout.strip()
    assert Path(top).resolve()==source.resolve()
    original=command(['git','remote','get-url','origin'],source,check=False)
    if original.returncode:command(['git','remote','add','origin',remote],source)
    elif original.stdout.strip()!=remote:raise RuntimeError('Source repository remote does not match the requested destination.')
    if initial_license_only and command(['git','rev-parse','--verify','HEAD'],source,check=False).returncode:
        command(['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential','fetch','origin','main'],source)
        command(['git','checkout','-B','main','origin/main'],source)
    command(['git','add','--','.github','workbench','README.md','OFL.txt','ssg-library.json','.gitignore'],source)
    staged=command(['git','diff','--cached','--quiet'],source,check=False)
    if staged.returncode:
        profile=api('user');mail=str(profile['id'])+'+'+login+'@users.noreply.github.com'
        command(['git','-c','user.name='+login,'-c','user.email='+mail,'commit','-m','Publish original 10000-style OFL font library'],source)
    command(['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential','push','-u','origin','main'],source)
    commit=command(['git','rev-parse','--verify','HEAD'],source).stdout.strip()
    release=next((r for r in api('repos/'+fullname+'/releases?per_page=100') if r['tag_name']==tag),None)
    notes=HOST/'RELEASE-NOTES.md'
    notes.write_text('10,000 original OFL styles: 500 Core, 2,000 Balanced, 7,500 Experimental. Full, core, source and 25-style group downloads included. Core retains its prior checks; the new Balanced styles pass alignment and counter-preservation checks, with individual optical review pending. See the catalog for tags, coverage and review limits.','utf-8')
    if release is None:
        gh('release','create',tag,'--repo',fullname,'--draft','--target','main','--title','SSG Fonts: 10,000 styles','--notes-file',str(notes))
        release=next(r for r in api('repos/'+fullname+'/releases?per_page=100') if r['tag_name']==tag)
    assets={a['name']:a for a in release['assets']}
    records=list(plan['assets'])
    sums=HOST/'release-assets/SHA256SUMS.txt'
    records.append(dict(name=sums.name,path=str(sums.relative_to(HOST)),size=sums.stat().st_size,sha256=hashlib.sha256(sums.read_bytes()).hexdigest()))
    pending=[]
    for record in records:
        old=assets.get(record['name'])
        if old:
            digest=old.get('digest') or old.get('label')
            if old['size']!=record['size'] or digest!='sha256:'+record['sha256']:
                raise RuntimeError('Refusing to replace a different release asset: '+record['name'])
        else:pending.append(record)
    for start in range(0,len(pending),15):
        batch=pending[start:start+15]
        paths=[str(HOST/r['path'])+'#sha256:'+r['sha256'] for r in batch]
        gh('release','upload',tag,*paths,'--repo',fullname)
        print('Uploaded',min(start+15,len(pending)),'of',len(pending),'release assets',flush=True)
    gh('release','edit',tag,'--repo',fullname,'--draft=false')
    pages=api('repos/'+fullname+'/pages',check=False)
    if pages is None:gh('api','--method','POST','repos/'+fullname+'/pages','-f','build_type=workflow')
    elif pages.get('build_type')!='workflow':raise RuntimeError('Existing Pages configuration is not the prepared workflow.')
    previous=gh('run','list','--repo',fullname,'--workflow','pages.yml','--limit','10','--json','databaseId',check=False)
    known={r['databaseId'] for r in json.loads(previous.stdout)} if previous.returncode==0 else set()
    gh('workflow','run','pages.yml','--repo',fullname,'--ref','main','-f','release_tag='+tag)
    run=None
    for attempt in range(30):
        records=json.loads(gh('run','list','--repo',fullname,'--workflow','pages.yml','--limit','10','--json','databaseId,headSha,url').stdout)
        run=next((r for r in records if r['databaseId'] not in known and r['headSha']==commit),None)
        if run:break
        time.sleep(3)
    if not run:raise RuntimeError('Workflow was dispatched but its run is not visible yet.')
    print('Deployment workflow:',run['url'],flush=True)
    watch=gh('run','watch',str(run['databaseId']),'--repo',fullname,'--exit-status',check=False)
    if watch.returncode:raise RuntimeError('Pages deployment failed. Inspect '+run['url'])
    pages=api('repos/'+fullname+'/pages')
    result={'status':'published','url':pages['html_url'],'repository_url':'https://github.com/'+fullname,'release_url':'https://github.com/'+fullname+'/releases/tag/'+tag,'commit':commit,'workflow_url':run['url']}
    (HOST/'deployment-result.json').write_text(json.dumps(result,indent=2),'utf-8')
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--owner',default='SteadyStateGames');p.add_argument('--repo',default='10kFonts');p.add_argument('--publish',action='store_true')
    args=p.parse_args()
    if not args.publish:
        print('No remote changes. Add --publish only when ready to create/update the public repository, release and website.')
    else:publish(args.owner,args.repo)

