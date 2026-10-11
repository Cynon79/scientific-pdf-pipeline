"""Preserve native text coverage exceptions without rewriting published bodies."""
import argparse,hashlib,json,re,sys
from pathlib import Path
import pymupdf as fitz
from native_text import page_characters,extract
from page_geometry import display_characters
from glyph_library import apply_library

def category(text,page):
    t=text.strip()
    if re.match(r'^(Fig(?:ure)?\.?|Table|Scheme)\s*S?\d+',t,re.I):return 'caption_candidate',True
    if re.search(r'\babbreviations?\s*:',t,re.I):return 'definitions_candidate',True
    if t.count('.')>len(t)*.15:return 'contents',False
    if re.search(r'corresponding author|correspondence to|e-mail address',t,re.I):return 'contact_information',False
    if page==1 and len(re.findall(r'\b(?:university|institute|school|laboratory|college)\b',t,re.I))>=3:return 'affiliation_information',False
    return 'source_text_candidate',True

def preserve(root,manifest,coverage,out):
    if out.exists():raise ValueError('Use a new supplement revision')
    if not out.resolve().is_relative_to(root.resolve()):raise ValueError('Keep supplements inside collection')
    papers={p['id']:p for p in json.loads(manifest.read_text())['papers']};groups={}
    for c in json.loads(coverage.read_text())['candidates']:groups.setdefault(c['document_id'],[]).append(c)
    out.mkdir(parents=True);(out/'images').mkdir();records=[]
    for ident,candidates in sorted(groups.items()):
        paper=papers[ident];source=manifest.parent/paper['staged']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=paper['sha256']:raise ValueError('PDF identity changed')
        with fitz.open(source) as doc:
            chars={n+1:page_characters(page) for n,page in enumerate(doc)}
            apply_library(doc,chars,json.loads((manifest.parent/paper['glyph_library']).read_text()))
            chars={n:display_characters(doc[n-1],cc) for n,cc in chars.items()}
            for c in candidates:
                kind,indexed=category(c['text'],c['page']);token=hashlib.sha256(json.dumps([paper['sha256'],c['page'],c['bbox']]).encode()).hexdigest()[:16]
                image=out/'images'/(ident+'-'+token+'.png');page=doc[c['page']-1];rect=(fitz.Rect(c['bbox'])+(-4,-4,4,4)) & page.rect
                page.get_pixmap(matrix=fitz.Matrix(200/72,200/72),clip=rect,alpha=False).save(image)
                text,flags,_=extract(chars[c['page']],c['bbox'])
                row=dict(record_id=ident+':supplement:'+token,document_id=ident,kind=kind,indexed=indexed,page=c['page'],text=text,raw_native_text=c['text'],flags=flags,quality_status='needs_review',source_pdf_sha256=paper['sha256'],source_regions=[dict(page_1based=c['page'],bbox_points_top_left=c['bbox'])],image_path=str(image.relative_to(root)),image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),reason='long_native_block_not_accounted_for_by_existing_regions')
                if kind=='caption_candidate':
                    full=out/'images'/(ident+'-page-'+str(c['page'])+'.png')
                    if not full.exists():page.get_pixmap(matrix=fitz.Matrix(150/72,150/72),alpha=False).save(full)
                    row['page_context_image']=str(full.relative_to(root));row['page_context_sha256']=hashlib.sha256(full.read_bytes()).hexdigest();row['asset_association']='unresolved_full_page_context_preserved'
                records.append(row)
    (out/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    summary=dict(records=len(records),indexed_records=sum(r['indexed'] for r in records),source_pdf_included=False,source_packages_modified=False,scientific_accuracy='not_certified')
    (out/'manifest.json').write_text(json.dumps(summary,indent=2));return summary
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--collection',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--coverage',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();print(json.dumps(preserve(a.collection,a.manifest,a.coverage,a.out)))
