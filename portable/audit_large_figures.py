"""Flag oversized figure regions containing paragraph-like native text.

This is a review diagnostic, never an automatic crop or body rewrite.
"""
import argparse,json,sys
from pathlib import Path
import pymupdf as fitz
from page_geometry import display_box

def audit(collection,manifest,out):
    papers={p['id']:p for p in json.loads(manifest.read_text())['papers']};records=[]
    for directory in sorted((collection/'documents').iterdir()):
        if not (directory/'publication.json').exists():continue
        assets=[json.loads(s) for s in (directory/'assets.jsonl').read_text().splitlines()]
        candidates=[a for a in assets if a['kind'] in ('figure','scheme')]
        if not candidates:continue
        source=manifest.parent/papers[directory.name]['staged']
        with fitz.open(source) as doc:
            for a in candidates:
                page=doc[a['page']-1];box=fitz.Rect(a['bbox']);fraction=box.get_area()/page.rect.get_area()
                if fraction<.6:continue
                paragraphs=[]
                for b in page.get_text('blocks'):
                    if b[6]!=0 or len(b[4].split())<40 or len(b[4])<250:continue
                    r=fitz.Rect(display_box(page,b[:4]))
                    if (r & box).get_area()<r.get_area()*.95:continue
                    if any((r & fitz.Rect(c['bbox'])).get_area()>r.get_area()*.2 for c in a['caption_regions']):continue
                    paragraphs.append(dict(bbox=list(r),text=b[4]))
                if paragraphs:
                    records.append(dict(document_id=directory.name,asset_id=a['asset_id'],page=a['page'],page_area_fraction=fraction,image_path=str((directory/a['image_path']).resolve()),paragraphs=paragraphs,status='possible_body_or_table_inside_figure_needs_review'))
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(records,ensure_ascii=False,indent=2));return dict(assets_flagged=len(records),documents_flagged=len({r['document_id'] for r in records}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--collection',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();print(json.dumps(audit(a.collection,a.manifest,a.out)))
