"""Incremental local postprocessing with atomic publication and explicit failures."""
import argparse,hashlib,json,os,shutil,sqlite3,time,traceback
from pathlib import Path
from build_native_assets import build_document
from consumer_exports import build_search,load_jsonl,write_jsonl

MODULES=['build_native_assets.py','native_text.py','page_geometry.py','glyph_repairs.py','glyph_library.py','caption_links.py','consumer_exports.py','source_labels.py','continued_assets.py','caption_fragments.py','figure_regions.py','source_crop_cache.py']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def signature(paper,pilot):
    source=pilot/paper['staged'];layout=pilot/paper['layout'];lib=pilot/paper['glyph_library']
    return dict(source_pdf_sha256=paper['sha256'],layout_sha256=digest(layout),library_sha256=digest(lib),processor_sha256=hashlib.sha256(b''.join((Path(__file__).parent/f).read_bytes() for f in MODULES)).hexdigest())

def publish_index(root):
    stage=root/('index-'+str(time.time_ns()));stage.mkdir();(stage/'documents').symlink_to((root/'documents').resolve(),target_is_directory=True)
    try:
        build_search(stage);assets=[];qualities=[]
        for d in sorted((root/'documents').iterdir()):
            if not (d/'publication.json').exists():raise ValueError('Uncommitted document in index')
            for a in load_jsonl(d/'assets.jsonl'):
                a['package_path']='documents/'+d.name;a['image_path_in_collection']=a['package_path']+'/'+a['image_path'];assets.append(a)
            qualities.append(json.loads((d/'quality.json').read_text()))
        write_jsonl(stage/'asset_catalog.jsonl',assets)
        (stage/'quality_summary.json').write_text(json.dumps(qualities,indent=2))
        db=sqlite3.connect(stage/'asset_search.sqlite');db.execute('CREATE VIRTUAL TABLE asset_search USING fts5(asset_id UNINDEXED,document_id UNINDEXED,kind UNINDEXED,image_path UNINDEXED,text)')
        db.executemany('INSERT INTO asset_search VALUES (?,?,?,?,?)',[(a['asset_id'],a['document_id'],a['kind'],a['image_path_in_collection'],a['retrieval_text']) for a in assets]);db.commit();db.close()
        lines=['# 文献原图索引','\n自动生成；质量标记与待复核项保留在逐篇记录中。\n']
        for a in assets:lines.append(f'- {a["document_id"]} · {a.get("label") or a["kind"]} · 第 {a["page"]} 页：[原图]({a["image_path_in_collection"]}) · [正文]({a["package_path"]}/reading.md)')
        (stage/'ASSET_INDEX.md').write_text('\n'.join(lines))
        for p in stage.iterdir():
            if p.is_file():p.replace(root/p.name)
    finally:
        (stage/'documents').unlink()
        if not any(stage.iterdir()):stage.rmdir()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--limit',type=int,default=30);ap.add_argument('--retry-failed',action='store_true');a=ap.parse_args()
    pilot=a.manifest.parent;papers=json.loads(a.manifest.read_text())['papers'];root=a.out
    for name in ['documents','attempts','failures']:(root/name).mkdir(exist_ok=True,parents=True)
    states=[];processed=0
    for paper in papers:
        ident=paper['id'];target=root/'documents'/ident;failure=root/'failures'/(ident+'.json')
        if not (pilot/paper['layout']).exists():states.append(dict(id=ident,state='waiting_for_parse'));continue
        sig=signature(paper,pilot)
        if target.exists():
            receipt=json.loads((target/'publication.json').read_text())
            if receipt['signature']!=sig:raise ValueError('Published revision changed; create a new output revision: '+ident)
            for p,h in receipt['artifacts'].items():
                if digest(target/p)!=h:raise ValueError('Published artifact changed: '+ident)
            states.append(dict(id=ident,state='published'));continue
        if failure.exists() and not a.retry_failed:states.append(dict(id=ident,state='failed'));continue
        if processed>=a.limit:states.append(dict(id=ident,state='ready_to_process'));continue
        attempt=root/'attempts'/(ident+'-'+str(time.time_ns()));attempt.mkdir();processed+=1
        try:
            _,quality=build_document(paper,pilot,attempt);doc=attempt/'documents'/ident
            hashes={str(p.relative_to(doc)):digest(p) for p in doc.rglob('*') if p.is_file()}
            receipt=dict(signature=sig,artifacts=hashes,scientific_ready=False)
            (doc/'publication.json').write_text(json.dumps(receipt,indent=2));doc.rename(target)
            (attempt/'documents').rmdir();attempt.rmdir()
            states.append(dict(id=ident,state='published',quality=quality));failure.unlink(missing_ok=True)
        except Exception:
            row=dict(id=ident,state='failed',signature=sig,error=traceback.format_exc(),attempt=str(attempt));failure.write_text(json.dumps(row,indent=2));states.append(row)
        print(json.dumps(dict(id=ident,state=states[-1]['state'])),flush=True)
        (root/'progress.json').write_text(json.dumps(dict(total=len(papers),processed_this_run=processed,states=states),indent=2))
    publish_index(root)
    from collections import Counter
    summary=dict(total=len(papers),counts=dict(Counter(s['state'] for s in states)),processed_this_run=processed,states=states)
    (root/'progress.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='states'}),flush=True)
if __name__=='__main__':main()
