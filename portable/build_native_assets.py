"""MinerU layout + original PDF characters and source crops, portable asset prototype."""
import argparse, collections, hashlib, html, json, re, shutil, sqlite3, sys, time
from pathlib import Path
import pymupdf as fitz
from native_text import page_characters,extract,render_characters,search_text,typography
from page_geometry import display_characters,display_words
from source_labels import label_above,equation_number
from caption_fragments import consolidate
from figure_regions import region as figure_region
from consumer_exports import export_document,build_search,classify_embedded_labels
from caption_links import parse_label,associate,continuation_candidates,union,horizontal

VERSION='native-assets-v0.11-boundary-annotations'
TEXT_TYPES={'text','title','abstract','list','ref_text'}

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values():yield from walk(v)
    elif isinstance(x,list):
        for v in x:yield from walk(v)

def raw_text(block):
    return ' '.join(str(s.get('content','')) for line in block.get('lines',[]) for s in line.get('spans',[])).strip()

def write(path,x):path.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def jsonl(path,rows):path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

def crop(page,box,dest,pad=4):
    rect=fitz.Rect(box)+(-pad,-pad,pad,pad)
    rect=rect & page.rect
    assert not rect.is_empty
    page.get_pixmap(matrix=fitz.Matrix(300/72,300/72),clip=rect,alpha=False).save(dest)
    return list(rect)

def build_document(paper,pilot,out):
    started=time.monotonic();ident=paper['id'];source=pilot/paper['staged']
    crop=globals()['crop']
    cache=None
    if paper.get('reuse_document'):
        from source_crop_cache import CropCache
        cache=CropCache(pilot/paper['reuse_document'],paper['sha256'],crop);crop=cache
    assert hashlib.sha256(source.read_bytes()).hexdigest()==paper['sha256']
    layout=pilot/paper['layout'] if paper.get('layout') else pilot/'outputs'/ident/'auto'/(ident+'_middle.json')
    middle=json.loads(layout.read_text())
    doc=fitz.open(source)
    assert sorted(p['page_idx'] for p in middle['pdf_info'])==list(range(len(doc))),'Missing or duplicate parsed pages'
    dest=out/'documents'/ident
    dest.mkdir(parents=True,exist_ok=False);(dest/'assets').mkdir()
    page_sizes={i+1:[p.rect.width,p.rect.height] for i,p in enumerate(doc)}
    glyph_review=None
    if paper.get('glyph_review'):
        from glyph_repairs import load_review
        glyph_review=load_review(pilot/paper['glyph_review'],paper['sha256'])
    if glyph_review and paper.get('glyph_library'):raise ValueError('Select reviewed document map or shared library, not both')
    chars={i+1:page_characters(p,glyph_review) for i,p in enumerate(doc)}
    if paper.get('glyph_library'):
        from glyph_library import apply_library
        entries=json.loads((pilot/paper['glyph_library']).read_text())
        apply_library(doc,chars,entries)
    chars={page:display_characters(doc[page-1],cc) for page,cc in chars.items()}
    repairs=[dict(page=page,**c) for page,cc in chars.items() for c in cc if 'original_c' in c]
    jsonl(dest/'character_repairs.jsonl',repairs)
    blocks=[];captions=[];visuals=[];tables=[];equations=[];assigned=collections.defaultdict(set)
    original_blocks={}
    for pdata in middle['pdf_info']:
        page=pdata['page_idx']+1
        assert all(abs(a-b)<1 for a,b in zip(page_sizes[page],pdata['page_size']))
        for ordinal,b in enumerate(pdata['para_blocks']):
            bid=f'{ident}:p{page}:b{ordinal}';original_blocks[bid]=b
            if b['type'] in TEXT_TYPES:
                text,flags,ids=extract(chars[page],b['bbox'])
                native=bool(text) and 'unmapped_native_glyph' not in flags
                if not text:text=raw_text(b)
                review_image=None
                if flags:
                    review_image=f'assets/text_review_{page}_{ordinal}.png'
                    crop(doc[page-1],b['bbox'],dest/review_image)
                assigned[page].update(ids)
                blocks.append(dict(block_id=bid,document_id=ident,page=page,bbox=b['bbox'],type=b['type'],
                    text=text,typography=typography(chars[page],b['bbox']),mineru_text=raw_text(b),text_source='pdf_native_geometry' if native else 'native_or_mineru_needs_review',
                    flags=flags,review_image=review_image,reading_order=len(blocks),section_path=[],source_regions=[dict(page_1based=page,bbox_points_top_left=b['bbox'])]))
            for sub in walk(b):
                if sub.get('type') not in ('image_caption','chart_caption','table_caption') or 'bbox' not in sub:continue
                txt,flags,ids=extract(chars[page],sub['bbox']);txt=txt or raw_text(sub)
                label=parse_label(search_text(txt))
                if not label:
                    printed=label_above(doc[page-1],sub['bbox'],'table' if sub['type']=='table_caption' else 'figure')
                    if printed:
                        txt=printed[0]+' '+txt;label=parse_label(txt);sub=dict(sub,bbox=union([sub['bbox'],printed[1]]))
                if not label:
                    label=('table' if sub['type']=='table_caption' else 'figure',None)
                    flags=sorted(set(flags+['caption_label_missing']))
                capid=f'{ident}:caption:{page}:{len(captions)}'
                captions.append(dict(caption_id=capid,page=page,bbox=sub['bbox'],text=txt,owner=bid,
                                     kind=label[0],number=label[1],typography=typography(chars[page],sub['bbox']),flags=flags,source='mineru_caption_native_text'))
                assigned[page].update(ids)
            if b['type'] in ('image','chart'):
                visuals.append(dict(visual_id=bid,owner=bid,page=page,bbox=b['bbox'],raw=b))
            elif b['type']=='table':tables.append(dict(owner=bid,page=page,bbox=b['bbox'],raw=b))
            elif b['type']=='interline_equation':equations.append(dict(owner=bid,page=page,bbox=b['bbox'],raw=b))
    captions=consolidate(captions)
    # Recover labels which MinerU represented as ordinary text, without inventing captions.
    known={(c['page'],c['kind'],c['number']) for c in captions}
    for b in blocks:
        label=parse_label(search_text(b['text']))
        if label and (b['page'],*label) not in known and len(b['text'])<3000:
            captions.append(dict(caption_id=b['block_id']+':caption',page=b['page'],bbox=b['bbox'],text=b['text'],owner=b['block_id'],
                                 kind=label[0],number=label[1],typography=b.get('typography'),flags=['caption_from_text_block'],source='native_text_block'))
            known.add((b['page'],*label))
    for c in captions:c['continuation_candidates']=continuation_candidates(c,blocks,page_sizes)
    groups,unassigned,adjacent=associate(visuals,captions,page_sizes)
    assets=[];owners={};displayed=set()
    for n,g in enumerate(groups,1):
        c=g['caption'];p=g['members'][0]['page']
        bbox,excluded=figure_region(g['members'],c,p);aid=f'{ident}:figure:{n}'
        flags=[]
        for b in blocks:
            if b['page']!=p or b['block_id']==c['owner'] or len(b['text'])<70:continue
            bb=b['bbox']
            if min(bb[2],bbox[2])-max(bb[0],bbox[0])>20 and min(bb[3],bbox[3])-max(bb[1],bbox[1])>10:flags.append('body_overlap_needs_review')
        path=f'assets/figure_{n:03}.png';box=crop(doc[p-1],bbox,dest/path)
        assets.append(dict(asset_id=aid,document_id=ident,kind=c['kind'],label=('Scheme ' if c['kind']=='scheme' else 'Fig. ')+c['number'],
            page=p,bbox=box,image_path=path,caption=c['text'],caption_regions=[dict(page=c['page'],bbox=c['bbox'])],
            caption_continuation_candidates=c['continuation_candidates'],linked_block_ids=[],recognition_status='source_image_preserved',
            visual_review='pending',flags=sorted(set(flags)),member_blocks=[m['owner'] for m in g['members']],excluded_region_candidates=excluded))
        for m in g['members']:owners[m['owner']]=aid
    for n,v in enumerate(unassigned,1):
        attached=next((c for c in captions if c['owner']==v['owner']),None)
        box=union([v['bbox'],attached['bbox']]) if attached else v['bbox'];aid=f'{ident}:unassigned_visual:{n}';path=f'assets/unassigned_{n:03}.png'
        box=crop(doc[v['page']-1],box,dest/path)
        candidates=[x for x in adjacent if x['visual_id']==v['visual_id']]
        assets.append(dict(asset_id=aid,document_id=ident,kind='unassigned_visual',label=None,page=v['page'],bbox=box,image_path=path,
                           caption=attached['text'] if attached else '',caption_regions=[dict(page=attached['page'],bbox=attached['bbox'])] if attached else [],caption_continuation_candidates=attached['continuation_candidates'] if attached else [],source_block_ids=[v['owner']],linked_block_ids=[],
                           recognition_status='unassigned',visual_review='pending',flags=['unassigned_visual'],caption_candidates=candidates))
        owners[v['owner']]=aid
    for kind,items in [('table',tables),('equation',equations)]:
        for n,item in enumerate(items,1):
            p=item['page'];b=item['raw'];aid=f'{ident}:{kind}:{n}';path=f'assets/{kind}_{n:03}.png'
            candidates=[c for c in captions if c['kind']=='table' and c['page']==p and
                        (c['owner']==item['owner'] or (0<=item['bbox'][1]-c['bbox'][3]<80 and horizontal(c['bbox'],item['bbox'])>.5))] if kind=='table' else []
            caption=next((c for c in candidates if c['owner']==item['owner']),candidates[-1] if len(candidates)==1 else None)
            boxes=[item['bbox']]+[v['bbox'] for v in b.get('blocks',[]) if v.get('bbox')]
            if caption:boxes.append(caption['bbox'])
            raw=raw_text(b);label=('Table '+caption['number']) if caption and caption['number'] else None
            if kind=='equation':
                printed_number=equation_number(doc[p-1],item['bbox'])
                if printed_number:
                    label='Eq. '+printed_number[0];boxes.append(printed_number[1])
                match=re.search(r'\\tag\s*\{([^}]+)\}',raw)
                if match:
                    label='Eq. '+match[1]
                    expected='('+match[1]+')'
                    for w in display_words(doc[p-1]):
                        if w[4]==expected and abs((w[1]+w[3]-item['bbox'][1]-item['bbox'][3])/2)<20 and 0<=w[0]-item['bbox'][2]<180:
                            boxes.append(list(w[:4]))
            box=crop(doc[p-1],union(boxes),dest/path,pad=4)
            text,flags,ids=extract(chars[p],union(boxes));assigned[p].update(ids)
            nearby=sorted([x for x in blocks if abs(x['page']-p)<=1 and x['type']!='ref_text'],key=lambda x:(abs(x['page']-p),abs(x['bbox'][1]-box[1])))[:3]
            htmls=[x['html'] for x in walk(b) if x.get('html')]
            html_path=None
            if htmls:
                html_path=f'assets/table_{n:03}.html';(dest/html_path).write_text('\n'.join(htmls))
            row=dict(asset_id=aid,document_id=ident,kind=kind,label=label,page=p,bbox=box,image_path=path,
                caption=caption['text'] if caption else '',caption_regions=[dict(page=p,bbox=caption['bbox'])] if caption else [],
                caption_continuation_candidates=caption['continuation_candidates'] if caption else [],
                native_text=text,recognized_html=html_path,mineru_transcription=raw if kind=='equation' else None,
                transcription_status='unverified_candidate',recognition_status='source_image_preserved',visual_review='pending',flags=flags,
                source_block_ids=[item['owner']],context_block_ids=[x['block_id'] for x in nearby],linked_block_ids=[])
            assets.append(row);owners[item['owner']]=aid
    classify_embedded_labels(blocks,assets)
    # Context follows the parser's reading order; vertical proximity alone
    # incorrectly attaches opposite-column paragraphs to bottom-page equations.
    order={bid:i for i,bid in enumerate(original_blocks)}
    for a in assets:
        source_ids=a.get('source_block_ids',a.get('member_blocks',[]))
        positions=[order[i] for i in source_ids if i in order]
        if positions:
            titles=[order[b['block_id']] for b in blocks if b['type']=='title']
            lower=max([i for i in titles if i<min(positions)],default=-1)
            upper=min([i for i in titles if i>max(positions)],default=len(order))
            eligible=[b for b in blocks if b['type'] not in ('ref_text','title') and abs(b['page']-a['page'])<=1 and lower<order[b['block_id']]<upper]
            before=[b for b in eligible if order[b['block_id']]<min(positions)]
            after=[b for b in eligible if order[b['block_id']]>max(positions)]
            a['context_block_ids']=[b['block_id'] for b in before[-2:]+after[:1]]
    asset_by_id={x['asset_id']:x for x in assets};relations=[]
    for b in blocks:
        for a in assets:
            if not a.get('label'):continue
            number=a['label'].split()[-1]
            prefix=r'(?:Fig(?:ure)?s?\.?)' if a['kind']=='figure' else (r'Scheme' if a['kind']=='scheme' else (r'Tables?' if a['kind']=='table' else r'(?:Eq(?:uation)?s?\.?)'))
            if re.search(prefix+r'\s*'+re.escape(number)+r'\b',search_text(b['text']),re.I):
                relations.append(dict(block_id=b['block_id'],asset_id=a['asset_id'],relation='explicit_reference_candidate'))
                a['linked_block_ids'].append(b['block_id'])
    section=[]
    for b in blocks:
        if b['type']=='title':section=[search_text(b['text'])]
        b['section_path']=list(section)
    by_id={b['block_id']:b for b in blocks}
    reading=['# '+ident+' 原文对齐版','\n正文来自原 PDF 字符及版面位置；图表与公式保留原图。自动重建内容仍需核对。\n']
    for pdata in middle['pdf_info']:
        p=pdata['page_idx']+1;reading.append(f'\n<!-- source page {p} -->\n')
        for ordinal,b in enumerate(pdata['para_blocks']):
            bid=f'{ident}:p{p}:b{ordinal}'
            if bid in by_id:
                item=by_id[bid]
                if item.get('role')=='embedded_visual_label':continue
                reading.append(f'<a id="{bid.replace(":","_")}"></a>\n')
                reading.append(('## ' if item['type']=='title' else '')+item['text']+'\n')
                if item.get('review_image'):reading.append(f"[文字解码待核对：查看原图]({item['review_image']})\n")
            elif bid in owners:
                aid=owners[bid]
                if aid in displayed:continue
                displayed.add(aid);a=asset_by_id[aid]
                reading.append(f'![{a.get("label") or a["kind"]}]({a["image_path"]})\n\n'+a['caption']+'\n')
    (dest/'reading.md').write_text('\n'.join(reading))
    for a in assets:
        linked=[by_id[x]['text'] for x in a['linked_block_ids'][:4]]
        nearby=[by_id[x]['text'] for x in a.get('context_block_ids',[]) if x in by_id]
        a['retrieval_text']=search_text(' '.join([a.get('label') or '',a['caption'],a.get('native_text',''),*linked,*nearby]))
        a['source_regions']=[dict(page_1based=a['page'],bbox_points_top_left=a['bbox'])]
        a['source_pdf_sha256']=paper['sha256'];a['parse_revision']=VERSION
    # Full native text is retained independently, so out-of-layout or continued
    # captions remain available even if no confident association was possible.
    pages=[]
    for p,c in chars.items():
        native=doc[p-1].get_text('text')
        pages.append(dict(page=p,native_text=native,unassigned_character_count=len(set(x['char_id'] for x in c)-assigned[p])))
    export_document(dest,doc,blocks,captions,assets,crop)
    jsonl(dest/'blocks.jsonl',blocks);jsonl(dest/'assets.jsonl',assets);jsonl(dest/'relations.jsonl',relations)
    jsonl(dest/'figures.jsonl',[x for x in assets if x['kind'] in ('figure','scheme','unassigned_visual')])
    jsonl(dest/'tables.jsonl',[x for x in assets if x['kind']=='table']);jsonl(dest/'equations.jsonl',[x for x in assets if x['kind']=='equation'])
    write(dest/'native_pages.json',pages);write(dest/'captions.json',captions);write(dest/'adjacent_caption_candidates.json',adjacent)
    write(dest/'document.json',dict(document_id=ident,source_pdf_sha256=paper['sha256'],source_pdf_local=str(source),
                                  source_pdf_remote=None,
                                  source_pdf_included=False,coordinate_space='PDF display points with original rotation applied',page_geometry=[dict(page=i+1,rotation=p.rotation,mediabox=list(p.mediabox),cropbox=list(p.cropbox),display_rect=list(p.rect),rotation_matrix=list(p.rotation_matrix)) for i,p in enumerate(doc)],parse_revision=VERSION,mineru_version=middle.get('_version_name')))
    counts=collections.Counter(x['kind'] for x in assets)
    quality=dict(document_id=ident,counts=dict(counts),text_blocks=len(blocks),native_blocks=sum(x['text_source']=='pdf_native_geometry' for x in blocks),
        flagged_text_blocks=sum(bool(x['flags']) for x in blocks),flagged_assets=sum(bool(x['flags']) for x in assets),
        adjacent_caption_candidates=len(adjacent),caption_continuation_candidates=sum(len(c['continuation_candidates']) for c in captions),
        reviewed_character_repairs=len(repairs),scientific_ready=False,elapsed_seconds=time.monotonic()-started)
    quality['source_crops_reused']=cache.reused if cache else 0
    quality['source_crops_rendered']=cache.rendered if cache else None
    write(dest/'quality.json',quality);doc.close()
    for a in assets:a['package_path']=str(dest.relative_to(out));a['image_path_in_collection']=str((dest/a['image_path']).relative_to(out))
    return assets,quality

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--ids',nargs='*');args=ap.parse_args()
    if args.out.exists():raise RuntimeError('Refusing to overwrite existing revision')
    args.out.mkdir(parents=True)
    papers=json.loads((args.pilot/'manifest.json').read_text())['papers'];all_assets=[];qualities=[]
    for paper in papers:
        if args.ids and paper['id'] not in args.ids:continue
        assets,q=build_document(paper,args.pilot,args.out);all_assets+=assets;qualities.append(q);print(json.dumps(q),flush=True)
    jsonl(args.out/'asset_catalog.jsonl',all_assets);write(args.out/'quality_summary.json',qualities)
    db=sqlite3.connect(args.out/'asset_search.sqlite')
    db.execute('CREATE VIRTUAL TABLE asset_search USING fts5(asset_id UNINDEXED,document_id UNINDEXED,kind UNINDEXED,image_path UNINDEXED,text, tokenize="unicode61")')
    for a in all_assets:db.execute('INSERT INTO asset_search VALUES (?,?,?,?,?)',(a['asset_id'],a['document_id'],a['kind'],a['image_path_in_collection'],a['retrieval_text']))
    db.commit();db.close()
    gallery=['# 图、表、公式索引','\n可检索文字包含图注、原始文字及相关段落；不代表已核查的科学数据。\n']
    for a in all_assets:
        if a['kind']=='unassigned_visual':continue
        gallery.append(f'- **{a["document_id"]} · {a.get("label") or a["kind"]}**（第 {a["page"]} 页）：[原图]({a["image_path_in_collection"]}) · [正文]({a["package_path"]}/reading.md)')
    (args.out/'ASSET_INDEX.md').write_text('\n'.join(gallery))
    build_search(args.out)
    print(json.dumps(dict(documents=len(qualities),assets=len(all_assets))),flush=True)
if __name__=='__main__':main()
