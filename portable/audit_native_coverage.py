"""Locate long native PDF blocks lacking a corresponding output region.

Geometric accounting only: not an OCR accuracy or semantic completeness score.
"""
import argparse,collections,json,sys
from pathlib import Path
import pymupdf as fitz
from page_geometry import display_box

def coverage(box,regions):
    clips=[]
    for r in regions:
        c=[max(box[0],r[0]),max(box[1],r[1]),min(box[2],r[2]),min(box[3],r[3])]
        if c[0]<c[2] and c[1]<c[3]:clips.append(c)
    xs=sorted({c[i] for c in clips for i in (0,2)});area=0
    for x0,x1 in zip(xs,xs[1:]):
        ys=sorted((c[1],c[3]) for c in clips if c[0]<x1 and c[2]>x0);height=0;end=None
        for y0,y1 in ys:
            if end is None or y0>end:height+=y1-y0;end=y1
            elif y1>end:height+=y1-end;end=y1
        area+=(x1-x0)*height
    return area/max(1,(box[2]-box[0])*(box[3]-box[1]))

def rows(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def audit(root,manifest,out):
    papers={p['id']:p for p in json.loads(manifest.read_text())['papers']};docs=sorted(d for d in (root/'documents').iterdir() if (d/'publication.json').exists());counts=collections.Counter();candidates=[]
    for d in docs:
        body=collections.defaultdict(list);other=collections.defaultdict(list)
        for b in rows(d/'llm_blocks.jsonl'):
            for r in b['source_regions']:body[r['page_1based']].append(r['bbox_points_top_left'])
        for b in rows(d/'blocks.jsonl'):
            if b['type']=='ref_text':other[b['page']].append(b['bbox'])
        for a in rows(d/'assets.jsonl'):other[a['page']].append(a['bbox'])
        for c in json.loads((d/'captions.json').read_text()):other[c['page']].append(c['bbox'])
        source=manifest.parent/papers[d.name]['staged']
        with fitz.open(source) as pdf:
            for page in pdf:
                for block in page.get_text('blocks'):
                    if block[6]!=0 or len(block[4].split())<50 or len(block[4])<300:continue
                    box=display_box(page,block[:4]);p=page.number+1;bc=coverage(box,body[p]);oc=coverage(box,other[p]);combined=coverage(box,body[p]+other[p])
                    if bc>=.7:state='body_region'
                    elif oc>=.7:state='nonbody_region'
                    elif combined>=.7:state='mixed_regions'
                    else:state='unaccounted_candidate';candidates.append(dict(document_id=d.name,page=p,bbox=list(box),body_coverage=bc,nonbody_coverage=oc,combined_coverage=combined,text=block[4],status='needs_source_review'))
                    counts[state]+=1
    result=dict(documents=len(docs),snapshot_document_ids=[d.name for d in docs],long_native_blocks=sum(counts.values()),counts=dict(counts),candidates=candidates,scope='Native text blocks with >=50 words and >=300 characters; geometric accounting threshold 0.7. Short text, scanned text and recognition accuracy are not certified.')
    out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2));return {k:v for k,v in result.items() if k not in ('candidates','snapshot_document_ids')}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--collection',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();print(json.dumps(audit(a.collection,a.manifest,a.out)))
