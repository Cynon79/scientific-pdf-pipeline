"""Create a positive-allowlist return archive: structured data and MD, no PDFs.
Original images are recreated from the user's local PDFs by the postprocessor.
"""
import argparse,hashlib,json,tarfile
from pathlib import Path

def collect(root,out):
    if out.exists():raise ValueError('Refusing to overwrite an existing return archive')
    papers=json.loads((root/'manifest.json').read_text())['papers'];files=[];done=[];pending=[]
    for p in papers:
        ident=p['id'];target=root/'outputs'/ident;receipt=target/'parse_receipt.json'
        if not receipt.exists():pending.append(ident);continue
        r=json.loads(receipt.read_text())
        if r['state']!='parsed_structure_checked' or r['source_sha256']!=p['sha256']:raise ValueError('Invalid committed output')
        for relative,digest in r['artifact_sha256'].items():
            path=(target/relative).resolve()
            if not path.is_relative_to(target.resolve()):raise ValueError('Invalid artifact path')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Committed artifact changed')
        selected=[target/'auto'/(ident+'_middle.json'),target/'auto'/(ident+'.md'),receipt]
        result=root/'results'/(ident+'.json')
        if result.exists():selected.append(result)
        for path in selected:
            if path.suffix not in ('.json','.md'):raise ValueError('Disallowed return file type')
            files.append(dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
        done.append(ident)
    metadata=dict(completed=done,pending=pending,files=files,pdfs_included=False)
    with tarfile.open(out,'w:gz') as tar:
        for entry in files:tar.add(root/entry['path'],arcname=entry['path'],recursive=False)
        import io
        data=json.dumps(metadata,indent=2).encode();info=tarfile.TarInfo('return_manifest.json');info.size=len(data);tar.addfile(info,io.BytesIO(data))
    print(json.dumps(dict(completed=len(done),pending=len(pending),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();collect(a.root,a.out)
