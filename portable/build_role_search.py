"""Build a versioned consumer index without changing source document packages.

Place the output within the collection so relative source links remain portable.
Only atomically published documents at startup enter this snapshot.
"""
import argparse,hashlib,json,os,sqlite3
from collections import Counter
from pathlib import Path
from caption_roles import classify
from asset_quality import review_reasons
from native_text import search_text

def jsonl(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def build(root,out,supplements=None):
    if out.exists():raise ValueError('Use a new index revision directory')
    if not out.resolve().is_relative_to(root.resolve()):raise ValueError('Keep index within collection for portable source links')
    documents=sorted(d for d in (root/'documents').iterdir() if (d/'publication.json').exists())
    out.mkdir(parents=True);db=sqlite3.connect(out/'search.sqlite');counts=Counter();roles=[];sources={}
    db.execute('CREATE VIRTUAL TABLE entries USING fts5(record_id UNINDEXED,document_id UNINDEXED,kind UNINDEXED,page UNINDEXED,quality UNINDEXED,image_path UNINDEXED,payload UNINDEXED,text,tokenize="unicode61")')
    def insert(ident,doc,kind,page,quality,image,payload,text):
        db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)',(ident,doc,kind,page,quality,image,json.dumps(payload,ensure_ascii=False),search_text(text)));counts[kind]+=1
    for d in documents:
        sources[d.name]=hashlib.sha256((d/'publication.json').read_bytes()).hexdigest();rel=Path(os.path.relpath(d,out))
        for b in jsonl(d/'llm_blocks.jsonl'):
            insert(b['block_id'],d.name,'body',b['page'],b['quality_status'],str(rel/b['review_image']) if b.get('review_image') else '',b,b['text'])
        assets=jsonl(d/'assets.jsonl')
        for a in assets:
            reasons=review_reasons(a)
            payload={k:v for k,v in a.items() if k not in ('native_text','recognized_html','mineru_transcription')};payload['review_reasons']=reasons
            insert(a['asset_id'],d.name,a['kind'],a['page'],'needs_review' if reasons else 'unreviewed',str(rel/a['image_path']),payload,a['retrieval_text'])
        for c in json.loads((d/'captions.json').read_text()):
            role=classify(c,assets);payload=dict(c,**role);roles.append(dict(document_id=d.name,caption_id=c['caption_id'],**role))
            insert(c['caption_id'],d.name,role['role'],c['page'],'needs_review' if c['flags'] else 'unreviewed',str(rel/c['image_path']),payload,c['text'])
            if role['role']=='caption':
                for i,v in enumerate(c.get('continuation_candidates',[])):insert(c['caption_id']+f':candidate:{i}',d.name,'caption_candidate',v['page'],'needs_review',str(rel/v['image_path']),v,v['text'])
    supplemental_count=0
    for supplement in supplements or []:
        for record in jsonl(supplement):
            if not record['indexed']:continue
            if record['document_id'] not in sources:raise ValueError('Supplement document absent from index snapshot')
            metadata=json.loads((root/'documents'/record['document_id']/'document.json').read_text())
            if metadata['source_pdf_sha256']!=record['source_pdf_sha256']:raise ValueError('Supplement source differs')
            image=(root/record['image_path']).resolve()
            if not image.is_relative_to(root.resolve()) or hashlib.sha256(image.read_bytes()).hexdigest()!=record['image_sha256']:raise ValueError('Supplement image changed')
            payload=dict(record)
            if record.get('page_context_image'):
                full=(root/record['page_context_image']).resolve()
                if not full.is_relative_to(root.resolve()) or hashlib.sha256(full.read_bytes()).hexdigest()!=record['page_context_sha256']:raise ValueError('Supplement page image changed')
                payload['page_context_image']=os.path.relpath(full,out)
            kind='source_caption_candidate' if record['kind']=='caption_candidate' else record['kind']
            insert(record['record_id'],record['document_id'],kind,record['page'],'needs_review',os.path.relpath(image,out),payload,record['text']);supplemental_count+=1
    db.commit()
    for image, in db.execute("select image_path from entries where image_path!=''"):
        if not (out/image).is_file():raise ValueError('Missing source image: '+image)
    db.close();(out/'search_counts.json').write_text(json.dumps(dict(counts),indent=2))
    manifest=dict(documents=sources,counts=dict(counts),classifier_sha256=hashlib.sha256((Path(__file__).parent/'caption_roles.py').read_bytes()).hexdigest(),quality_policy_sha256=hashlib.sha256((Path(__file__).parent/'asset_quality.py').read_bytes()).hexdigest(),source_packages_modified=False,supplemental_records=supplemental_count,supplement_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in supplements or []},scientific_accuracy='not_certified',roles=roles)
    (out/'index_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (out/'README.md').write_text('# 分类检索索引\n\ncaption 为正式图注及尚无法分类的图注候选；visual_annotation 为同一完整组图内部的注记。后者只改变检索类别，原记录、原图及候选来源均保留，没有识别或核验视觉内容。\n\n正文使用原 llm_blocks.jsonl，不改变文字。原始逐篇包没有修改。将索引与整个文献集合一起迁移，图片相对路径仍有效。具体快照文献和规则版本见 index_manifest.json。\n')
    return dict(documents=len(documents),counts=dict(counts))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--collection',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--supplement',type=Path,action='append',default=[]);a=ap.parse_args();print(json.dumps(build(a.collection,a.out,a.supplement)))
