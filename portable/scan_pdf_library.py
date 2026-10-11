"""Resumable CPU preflight of a PDF corpus. No OCR, inference or API calls."""
import argparse,concurrent.futures,hashlib,json,sys,time
from pathlib import Path
import pymupdf as fitz
from native_text import page_characters
from glyph_library import glyph_observations

def scan(task):
    paper,root,entries,config_hash=task
    started=time.monotonic();record=dict(document_id=paper['document_id'],source_sha256=paper['sha256'],config_hash=config_hash)
    try:
        path=Path(root)/paper['remote_relative']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=paper['sha256']:raise ValueError('Source integrity mismatch')
        doc=fitz.open(path)
        if doc.needs_pass:raise ValueError('Encrypted PDF requires password')
        bad=[];low_text=[];rotated=[];total_chars=0
        for p in doc:
            chars=page_characters(p);total_chars+=len(chars)
            if len(chars)<30:low_text.append(p.number+1)
            if p.rotation:rotated.append(p.number+1)
            for c in chars:
                if any(ord(v)<32 or v in '\ufffd\ufffe\uffff' for v in c['c']):bad.append(dict(page=p.number+1,char_id=c['char_id'],font=c['font'],original=c['c'],bbox=c['bbox']))
        lookup={}
        for e in entries:lookup.setdefault((e['font'],e['outline_sha256']),set()).add(e['replacement'])
        diagnostics=[];observations=glyph_observations(doc,diagnostics);known=[];unknown=[]
        for o in observations:
            values=lookup.get((o['font'],o['outline_sha256']),set())
            if len(values)==1:known.append(dict(**o,replacement=next(iter(values))))
            else:unknown.append(o)
        observed={(o['page'],o['char_id']) for o in observations}
        unlocated=[b for b in bad if (b['page'],b['char_id']) not in observed]
        record.update(state='scanned',pages=len(doc),native_characters=total_chars,low_text_pages=low_text,rotated_pages=rotated,
                      anomalous_characters=len(bad),reusable_characters=len(known),unresolved_characters=len(unknown)+len(unlocated),
                      reuse_candidates=known,unknown_glyphs=unknown,unlocated_characters=unlocated,font_diagnostics=diagnostics)
        doc.close()
    except Exception as error:record.update(state='failed',error=type(error).__name__+': '+str(error))
    record['elapsed_seconds']=round(time.monotonic()-started,3)
    return record

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--library',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,default=2);ap.add_argument('--resume',action='store_true');a=ap.parse_args()
    if not 1<=a.workers<=4:ap.error('workers must be 1..4')
    if a.out.exists() and not a.resume:ap.error('Output exists; use --resume for exact-input continuation')
    a.out.mkdir(exist_ok=True,parents=True);papers=json.loads(a.manifest.read_text())['files'];entries=json.loads(a.library.read_text())
    fingerprint=hashlib.sha256(a.library.read_bytes()+Path(__file__).read_bytes()+Path(__file__).with_name('glyph_library.py').read_bytes()+Path(__file__).with_name('native_text.py').read_bytes()).hexdigest()
    pending=[];records=[]
    for p in papers:
        target=a.out/(p['document_id']+'.json')
        if target.exists():
            r=json.loads(target.read_text())
            if r['config_hash']!=fingerprint or r['source_sha256']!=p['sha256']:raise ValueError('Resume input/code changed')
            if r['state']=='scanned':records.append(r);continue
        pending.append((p,str(a.manifest.parent),entries,fingerprint))
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for r in pool.map(scan,pending):
            path=a.out/(r['document_id']+'.json');temp=path.with_suffix('.tmp');temp.write_text(json.dumps(r,ensure_ascii=False));temp.replace(path);records.append(r)
            print(json.dumps({k:r[k] for k in ('document_id','state','elapsed_seconds')}),flush=True)
    summary=dict(documents=len(records),scanned=sum(r['state']=='scanned' for r in records),failed=sum(r['state']=='failed' for r in records),
                 pages=sum(r.get('pages',0) for r in records),documents_with_anomalies=sum(bool(r.get('anomalous_characters',0)) for r in records),
                 reusable_characters=sum(r.get('reusable_characters',0) for r in records),unresolved_characters=sum(r.get('unresolved_characters',0) for r in records),
                 documents_with_low_text_pages=sum(bool(r.get('low_text_pages')) for r in records),processed_this_run=len(pending),config_hash=fingerprint)
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
