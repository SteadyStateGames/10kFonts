"""Prepare (but do not publish) GitHub Pages and release assets."""
from pathlib import Path
import json,shutil,hashlib,argparse,zipfile
import build as engine
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;HOST=ROOT/'hosting-refined'
def prepare(owner='SteadyStateGames',repo='10kFonts',tag='v0.5.0'):
    assert all(c.isalnum() or c in '-_.' for c in owner+repo)
    assert all(c.isalnum() or c in '-_.' for c in tag)
    site=HOST/'site';deploy=HOST/'deploy-site';source=HOST/'source';release=HOST/'release-assets'
    assert (site/'index.html').is_file()
    deploy.mkdir(parents=True,exist_ok=True);source.mkdir(exist_ok=True);release.mkdir(exist_ok=True)
    shutil.copytree(site,deploy,dirs_exist_ok=True)
    repo_url=f'https://github.com/{owner}/{repo}'
    base=repo_url+'/releases/download/'+tag+'/'
    (deploy/'config.json').write_text(json.dumps({'group_base':base,'bulk_base':base,'source_url':base+'SSG-10000-Source.zip','repository_url':repo_url}),'utf-8')
    engine.write_zip(release/'SSG-10000-Site.zip',[(p,p.relative_to(deploy).as_posix()) for p in sorted(deploy.rglob('*')) if p.is_file()])
    with zipfile.ZipFile(release/'SSG-10000-Site.zip') as z:
        assert z.testzip() is None
        assert sum(n.endswith('.woff2') for n in z.namelist())==10000
        assert not any(n.endswith('.ttf') for n in z.namelist())
    shutil.copy2(ROOT/'collection-2000/downloads/SSG-2000.zip',release/'SSG-2000.zip')
    names=['build.py','build250.py','build1000.py','build_balanced.py','build2000.py','build10000.py','build_balanced2000.py','proofs_balanced2000.py','package_refined10000.py','prepare_hosting_refined.py','core_geometry.py','package2000.py','package10000.py','proofs10000.py','catalog10000-template.html','catalog10000-refined-template.html','requirements.txt','OFL.txt','sources/glyphs.py','sources/roots.json','prepare_hosting10000.py','publish10000.py','publish_refined10000.py','verify10000.cjs','verify-refinement.cjs','verify_refined_release.cjs']
    for n in names:
        out=source/'workbench'/n;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/n,out)
    shutil.copy2(BASE/'catalog10000-refined-template.html',source/'workbench/catalog10000-template.html')
    for n in ['project.godot','verify.gd']:
        out=source/'workbench/qa-godot'/n;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/'qa-godot'/n,out)
    shutil.copy2(BASE/'OFL.txt',source/'OFL.txt')
    marker={'project':'steady-state-games-font-library','owner':owner,'repository':repo,'release':tag,'styles':10000,'tiers':{'Core':500,'Balanced':2000,'Experimental':7500}}
    (source/'ssg-library.json').write_text(json.dumps(marker,indent=2),'utf-8')
    (source/'.gitignore').write_text('__pycache__/\n*.pyc\n*.zip\n*.ttf\n*.woff2\n.font-build-deps*/\ncollection-*/\nworkbench/collection-*/\nhosting/\n.godot/\n','utf-8')
    (source/'README.md').write_text(f"""# Steady State Games / 10,000 font styles

500 refined Core, 2,000 Balanced and 7,500 Experimental styles. These branch from ten original drawing roots. All font software uses OFL 1.1. Commercial and noncommercial font use are free under the license.

The core has 184 supported characters and additional proportion/counter/spacing/raster checks. Experimental fonts have 107 characters and intentional display effects. Individual optical sign-off, broad language coverage and long-reading validation remain pending.

## Browse and download
The GitHub Pages catalog previews only 20 visible fonts at a time. Releases hold the installable fonts, source archive, and 400 family/treatment groups of 25 styles each.

Release: {repo_url}/releases/tag/{tag}

The initial repository LICENSE is preserved. Font files and drawing sources are distributed under OFL.txt; each font download includes that license.

## Rebuild
Download SSG-10000-Source.zip from the release; it includes the exact previous 2,000-style baseline input. Follow its README. Python 3.14 and workbench/requirements.txt reproduce the pipeline; no third-party font outlines are used.

The Pages workflow consumes the validated SSG-10000-Site.zip release asset, verifies its SHA-256, and deploys that static payload. Font generation is separate from publishing. Download binaries stay in Releases; the Git repository stays focused on editable source.

## Review
Use the catalog's review flags and export them as JSON when reporting problem glyphs. Include font name, text, size, platform, and a screenshot if possible.
""",'utf-8')
    workflow="""name: Publish font catalog
on:
  workflow_dispatch:
    inputs:
      release_tag:
        description: Validated font release tag
        required: true
        default: v0.5.0
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: font-pages
  cancel-in-progress: false
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: @{{ steps.deployment.outputs.page_url }}
    steps:
      - name: Check out current catalog interface
        uses: actions/checkout@v6
      - name: Configure Pages
        uses: actions/configure-pages@v5
      - name: Download and verify the prepared website
        env:
          GH_TOKEN: @{{ github.token }}
          RELEASE_TAG: @{{ inputs.release_tag }}
        run: |
          mkdir -p "$RUNNER_TEMP/ssg-site"
          gh release download "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --pattern SSG-10000-Site.zip --pattern SHA256SUMS.txt --dir "$RUNNER_TEMP/ssg-site"
          cd "$RUNNER_TEMP/ssg-site"
          sha256sum --ignore-missing -c SHA256SUMS.txt
          python - <<'PY'
          from pathlib import Path
          import zipfile
          target=Path('public').resolve()
          target.mkdir(exist_ok=True)
          with zipfile.ZipFile('SSG-10000-Site.zip') as z:
              for name in z.namelist():
                  assert (target/name).resolve().is_relative_to(target)
              z.extractall(target)
          PY
      - name: Apply current catalog interface
        run: cp workbench/catalog10000-template.html "$RUNNER_TEMP/ssg-site/public/index.html"
      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v4
        with:
          path: @{{ runner.temp }}/ssg-site/public
      - name: Deploy Pages
        id: deployment
        uses: actions/deploy-pages@v4
"""
    workflow=workflow.replace('@{{','$'+'{{')
    (source/'.github/workflows').mkdir(parents=True,exist_ok=True)
    (source/'.github/workflows/pages.yml').write_text(workflow,'utf-8')
    assets=sorted(release.glob('*.zip'))+sorted((release/'groups').glob('*.zip'))
    assert len(assets)<1000 and len({p.name for p in assets})==len(assets)
    records=[{'path':str(p.relative_to(HOST)),'name':p.name,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in assets]
    assert all(r['size']<2*1024**3 for r in records)
    (release/'SHA256SUMS.txt').write_text('\n'.join(r['sha256']+'  '+r['name'] for r in records)+'\n','utf-8')
    total=sum(p.stat().st_size for p in deploy.rglob('*') if p.is_file())
    manifest=dict(marker,status='prepared-not-published',site_bytes=total,site_files=sum(p.is_file() for p in deploy.rglob('*')),assets=records,source_directory=str(source),repository_url=repo_url)
    (HOST/'deployment-plan.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    (HOST/'HOSTING.md').write_text(f"""# Hosting preparation

Status: prepared locally; not published. Proposed repository: {repo_url}.

Static site: {total:,} bytes in {manifest['site_files']:,} files. The catalog and WOFF2 previews live on Pages; {len(assets)} binary download assets live in Releases. No payment system or paid service is required by this setup.

## Publish
Sign in locally, without sharing a token in chat:
gh auth login --web --git-protocol https --scopes workflow

Then, from the font project root:
python workbench/publish_refined10000.py --owner {owner} --repo {repo} --publish

The publisher verifies artifacts and the authenticated owner, creates a public repository only if absent, refuses to overwrite unrelated repositories or mismatched release assets, uploads a draft release, publishes it, enables Pages, and dispatches the workflow. It writes the deployment result only after GitHub reports completion.

Preview locally at /hosting-refined/site/index.html on the existing local server. /collection-refined-10000/index.html is the full usable library. deploy-site has the release URLs that will work after publication.

## Current platform documentation
- Pages published-site limit: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- Release asset limits: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- Pages workflow: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

Measured site size is below 1 GB. Each release asset is below 2 GiB. The workflow uses the currently documented Pages actions. GitHub availability, authentication and repository permissions are still required for deployment.
""",'utf-8')
    print(json.dumps({k:manifest[k] for k in ['status','site_bytes','site_files','repository_url']}),flush=True)
    print('Release assets:',len(records),flush=True)
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--owner',default='SteadyStateGames');p.add_argument('--repo',default='10kFonts');p.add_argument('--tag',default='v0.5.0')
    args=p.parse_args();prepare(args.owner,args.repo,args.tag)

