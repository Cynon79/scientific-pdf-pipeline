"""Propose only missing-glyph substitutions supported by local traditional OCR.
Never overwrite the preserved native text. No model or network calls.
"""
import argparse,difflib,html,json,re,unicodedata
from pathlib import Path

def normalized(value):
    chars=[];positions=[]
    for m in re.finditer(r'<[^>]*>|&(?:#\d+|#x[0-9a-fA-F]+|\w+);|.',value,re.S):
        token=m[0]
        if token.startswith('<'):continue
        for c in unicodedata.normalize('NFKC',html.unescape(token)):
            if c.isspace() or c in '-\xad':continue
            chars.append(c);positions.append(m.start())
    return ''.join(chars),positions

def propose(native,ocr,min_context=6):
    a,positions=normalized(native);b,_=normalized(ocr)
    sm=difflib.SequenceMatcher(None,a,b,autojunk=False)
    if sm.ratio()<.90:return []
    result=[]
    for op,i,j,k,l in sm.get_opcodes():
        if op!='replace' or a[i:j]!='�' or l-k!=1:continue
        replacement=b[k:l]
        if not replacement.isprintable() or replacement=='�':continue
        left=min(min_context,i,k);right=min(min_context,len(a)-j,len(b)-l)
        if left<min_context or right<min_context:continue
        if a[i-left:i]!=b[k-left:k] or a[j:j+right]!=b[l:l+right]:continue
        result.append(dict(offset=positions[i],original='�',replacement=replacement,
                           left_context=a[i-left:i],right_context=a[j:j+right],alignment_ratio=round(sm.ratio(),5)))
    return result

def overlap(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return intersection/max(1,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)

def run(document,ocr_path,out):
    if out.exists():raise RuntimeError('Refusing to overwrite repair proposal revision')
    source=json.loads(ocr_path.read_text());ocr=[]
    for page in source['pdf_info']:
        for n,b in enumerate(page['para_blocks']):
            if b['type'] not in ('text','abstract','list','title','ref_text'):continue
            text=' '.join(str(s.get('content','')) for line in b.get('lines',[]) for s in line.get('spans',[]))
            ocr.append(dict(page=page['page_idx']+1,bbox=b['bbox'],text=text,block_id=f"ocr:p{page['page_idx']+1}:b{n}"))
    results=[]
    for line in (document/'blocks.jsonl').read_text().splitlines():
        b=json.loads(line)
        if '�' not in b['text']:continue
        candidates=sorted([(overlap(b['bbox'],o['bbox']),o) for o in ocr if o['page']==b['page']],key=lambda x:x[0],reverse=True)
        if not candidates or candidates[0][0]<.65:continue
        if len(candidates)>1 and candidates[1][0]>.5:continue
        score,o=candidates[0];repairs=propose(b['text'],o['text'])
        proposed=b['text']
        for r in reversed(repairs):
            assert proposed[r['offset']]=='�'
            proposed=proposed[:r['offset']]+r['replacement']+proposed[r['offset']+1:]
        results.append(dict(block_id=b['block_id'],page=b['page'],bbox=b['bbox'],original=b['text'],proposed=proposed,
                            substitutions=repairs,remaining_unknowns=proposed.count('�'),ocr_text=o['text'],ocr_block_id=o['block_id'],
                            geometry_iou=round(score,5),review_image=b.get('review_image'),status='proposal_needs_review'))
    out.mkdir(parents=True)
    (out/'proposals.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in results))
    summary=dict(blocks_matched=len(results),blocks_with_proposals=sum(bool(x['substitutions']) for x in results),
                 glyph_proposals=sum(len(x['substitutions']) for x in results),remaining_unknowns_in_matched_blocks=sum(x['remaining_unknowns'] for x in results),applied_to_production=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--document',type=Path,required=True);ap.add_argument('--ocr',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();run(a.document,a.ocr,a.out)
