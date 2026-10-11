"""Build a source-linked review queue without upgrading scientific quality."""
import argparse,collections,json
from pathlib import Path

def rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def audit(root,out):
    docs=sorted(d for d in (root/'documents').iterdir() if (d/'publication.json').exists())
    issues=[];counts=collections.Counter();totals=collections.Counter(documents=len(docs));documents=[]
    def add(d,kind,ident,page,source,text):
        counts[kind]+=1;issues.append(dict(document_id=d.name,type=kind,record_id=ident,page=page,source_path=str((d/source).resolve()) if source else None,text=text))
    for d in docs:
        start=len(issues);blocks=rows(d/'blocks.jsonl');assets=rows(d/'assets.jsonl');captions=json.loads((d/'captions.json').read_text());totals.update(text_blocks=len(blocks),assets=len(assets),captions=len(captions))
        for b in blocks:
            for flag in b.get('flags',[]):add(d,flag,b['block_id'],b['page'],b.get('review_image'),b['text'])
        for a in assets:
            for flag in a.get('flags',[]):
                if flag!='unassigned_visual':add(d,'asset_'+flag,a['asset_id'],a['page'],a['image_path'],a.get('caption',''))
            if any(not (a['bbox'][0]<=e['bbox'][0] and a['bbox'][1]<=e['bbox'][1] and a['bbox'][2]>=e['bbox'][2] and a['bbox'][3]>=e['bbox'][3]) for e in a.get('excluded_region_candidates',[])):add(d,'excluded_region_candidates_needs_review',a['asset_id'],a['page'],a['image_path'],a.get('caption',''))
            if a['kind']=='unassigned_visual':add(d,'unassigned_visual',a['asset_id'],a['page'],a['image_path'],a.get('caption',''))
            if a['kind'] in ('figure','scheme','table') and not a.get('caption','').strip():add(d,'missing_asset_caption',a['asset_id'],a['page'],a['image_path'],'')
        for c in captions:
            for flag in c.get('flags',[]):
                if flag!='caption_from_text_block':add(d,'caption_'+flag,c['caption_id'],c['page'],c.get('image_path'),c['text'])
            for candidate in c.get('continuation_candidates',[]):add(d,'caption_continuation_candidate',c['caption_id'],candidate['page'],candidate.get('image_path'),candidate['text'])
        for g in rows(d/'asset_groups.jsonl'):
            status=g.get('state',g.get('status',g.get('link_status')))
            if status and status!='explicit_continuation':add(d,'asset_group_'+status,g.get('group_id',d.name),None,'reading.md',str(g))
        documents.append(dict(document_id=d.name,review_items=len(issues)-start,scientific_accuracy='not_certified'))
    missing=[i for i in issues if i['source_path'] and not Path(i['source_path']).is_file()]
    if missing:raise ValueError('Review queue contains missing source images')
    result=dict(collection=str(root.resolve()),snapshot_documents=[d.name for d in docs],totals=dict(totals),issue_counts=dict(counts),documents=documents,issues=issues,scientific_accuracy='not_certified',note='A review item is an automatic diagnostic, not proof of an error. Zero flags do not certify correctness.')
    out.mkdir(parents=True,exist_ok=True);(out/'review_queue.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    lines=['# 文献质量复核队列','',f'本次快照覆盖 {len(docs)} 篇。自动标记用于定位复核，不等于错误数量；没有标记也不代表科学内容已核验。','', '| 类型 | 数量 |','|---|---:|',*[f'| {k} | {v} |' for k,v in sorted(counts.items())],'','## 逐项来源','']
    for i in issues:
        link=f'[来源](<{i["source_path"]}>)' if i['source_path'] else '来源见逐篇正文记录'
        lines.append(f'- {i["document_id"]} · {i["type"]} · 第 {i["page"]} 页 · {link} · `{i["record_id"]}`')
    (out/'REVIEW_QUEUE.md').write_text('\n'.join(lines));return {k:result[k] for k in ['totals','issue_counts']}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--collection',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();print(json.dumps(audit(a.collection,a.out)))
