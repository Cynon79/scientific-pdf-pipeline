"""Preservation-only exports. No image recognition or external model calls."""
import json, sqlite3, re
from pathlib import Path
from native_text import search_text

def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

def load_jsonl(path):
    return [json.loads(s) for s in path.read_text().splitlines()]


def classify_embedded_labels(blocks,assets):
    for b in blocks:
        if b['type']!='text' or not re.fullmatch(r'\(?[A-Za-z]\)?',b['text'].strip()):continue
        x=b['bbox']
        parents=[a['asset_id'] for a in assets if a['kind'] in ('figure','scheme') and a['page']==b['page'] and a['bbox'][0]<=x[0] and a['bbox'][1]<=x[1] and a['bbox'][2]>=x[2] and a['bbox'][3]>=x[3]]
        if parents:b['role']='embedded_visual_label';b['parent_asset_ids']=parents

def export_document(dest, doc, blocks, captions, assets, crop):
    """Keep caption regions even when no figure association is confident."""
    from continued_assets import group_assets
    write_jsonl(dest/'asset_groups.jsonl',group_assets(assets))
    by_id={b['block_id']:b for b in blocks}
    for n,c in enumerate(captions,1):
        c['image_path']=f'assets/caption_{n:03}.png'
        c['crop_bbox']=crop(doc[c['page']-1],c['bbox'],dest/c['image_path'])
        c['completeness_status']='not_reviewed'
        for j,v in enumerate(c.get('continuation_candidates',[]),1):
            v['image_path']=f'assets/caption_{n:03}_candidate_{j:02}.png'
            v['crop_bbox']=crop(doc[v['page']-1],v['bbox'],dest/v['image_path'])
    for a in assets:
        # HTML / formula recognition is archived by MinerU, not promoted to
        # search or scientific data in preservation-only mode.
        a['index_mode']='image_caption_context_only'
        a['caption_ids']=[c['caption_id'] for c in captions if any(
            c['page']==r['page'] and c['bbox']==r['bbox'] for r in a['caption_regions'])]
        a['caption_status']='not_reviewed' if a['caption_ids'] else ('not_applicable_or_missing' if a['kind']=='equation' else 'missing_or_unassigned')
        a['caption_flags']=sorted({f for c in captions if c['caption_id'] in a['caption_ids'] for f in c['flags']})
        context=[by_id[i]['text'] for i in dict.fromkeys(a['linked_block_ids']+a.get('context_block_ids',[])) if i in by_id]
        a['retrieval_text']=search_text(' '.join([a.get('label') or '',a['caption'],a.get('group_caption',''),*context]))
        if a['kind']=='equation':
            a['parent_figure_candidates']=[]
            for f in assets:
                if f['kind'] not in ('figure','scheme') or f['page']!=a['page']:continue
                x=a['bbox'];y=f['bbox']
                area=max(0,min(x[2],y[2])-max(x[0],y[0]))*max(0,min(x[3],y[3])-max(x[1],y[1]))
                if area/max(1,(x[2]-x[0])*(x[3]-x[1]))>.9:a['parent_figure_candidates'].append(f['asset_id'])
    rows=[];md=['# LLM 正文输入','\n正文按源页和版面顺序排列；未完成全文人工校对。待复核块不能作为无误的事实依据。图表公式仅提供资产引用，不提供视觉内容识别。\n']
    for b in blocks:
        # References remain in the source reading; omit only the explicit
        # reference block class from the default scientific-body view.
        if b['type']=='ref_text' or b.get('role')=='embedded_visual_label':continue
        row=dict(block_id=b['block_id'],document_id=b['document_id'],type=b['type'],
                 text=b['text'],page=b['page'],source_regions=b['source_regions'],section_path=b['section_path'],
                 quality_status='needs_review' if b['flags'] else 'automatic_unreviewed',flags=b['flags'],
                 review_image=b.get('review_image'),asset_ids=[a['asset_id'] for a in assets if b['block_id'] in a['linked_block_ids']])
        rows.append(row)
        md.append(f'\n<!-- {b["block_id"]}; page={b["page"]}; quality={row["quality_status"]} -->\n'+b['text']+'\n')
    md.append('\n## 图表公式引用\n')
    for a in assets:
        md.append(f'- {a["asset_id"]} | page {a["page"]} | {a.get("label") or a["kind"]} | [原图]({a["image_path"]})\n  '+a['caption'])
    write_jsonl(dest/'llm_blocks.jsonl',rows)
    (dest/'llm.md').write_text('\n'.join(md))

def build_search(root):
    path=root/'search.sqlite'
    if path.exists():raise RuntimeError('Refusing to overwrite search revision')
    db=sqlite3.connect(path)
    db.execute('CREATE VIRTUAL TABLE entries USING fts5(record_id UNINDEXED,document_id UNINDEXED,kind UNINDEXED,page UNINDEXED,quality UNINDEXED,image_path UNINDEXED,payload UNINDEXED,text,tokenize="unicode61")')
    counts={}
    def insert(record,ident,kind,page,quality,image,payload,text):
        db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)',(record,ident,kind,page,quality,image,json.dumps(payload,ensure_ascii=False),search_text(text)))
        counts[kind]=counts.get(kind,0)+1
    for d in sorted((root/'documents').iterdir()):
        ident=d.name;rel=d.relative_to(root)
        for b in load_jsonl(d/'llm_blocks.jsonl'):
            insert(b['block_id'],ident,'body',b['page'],b['quality_status'],str(rel/b['review_image']) if b['review_image'] else '',b,b['text'])
        for a in load_jsonl(d/'assets.jsonl'):
            insert(a['asset_id'],ident,a['kind'],a['page'],'unreviewed',str(rel/a['image_path']),{k:v for k,v in a.items() if k not in ('native_text','recognized_html','mineru_transcription')},a['retrieval_text'])
        for c in json.loads((d/'captions.json').read_text()):
            insert(c['caption_id'],ident,'caption',c['page'],'needs_review' if c['flags'] else 'unreviewed',str(rel/c['image_path']),c,c['text'])
            for i,v in enumerate(c['continuation_candidates']):
                insert(c['caption_id']+f':candidate:{i}',ident,'caption_candidate',v['page'],'needs_review',str(rel/v['image_path']),v,v['text'])
    db.commit();db.close()
    (root/'search_counts.json').write_text(json.dumps(counts,indent=2))
    return counts
