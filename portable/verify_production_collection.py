"""Verify source identity, immutable receipts and source-linked body/assets.

Supports a collection containing reused and newly processed document packages.
This verifies provenance and integrity, never scientific accuracy.
"""
import argparse,ast,collections,hashlib,json
from pathlib import Path


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s]


def processor_signature(root):
    module=ast.parse((root/'process_library.py').read_text())
    node=next(n for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODULES' for t in n.targets))
    files=ast.literal_eval(node.value)
    return hashlib.sha256(b''.join((root/name).read_bytes() for name in files)).hexdigest()


def verify(manifest,collection,processor_roots):
    papers=json.loads(manifest.read_text())['papers']
    expected={p['id']:p for p in papers}
    assert len(expected)==len(papers),'Duplicate manifest IDs'
    actual={d.name:d for d in (collection/'documents').iterdir()}
    assert actual.keys()==expected.keys(),'Missing or unexpected document packages'
    allowed={processor_signature(p) for p in processor_roots}
    signatures=collections.Counter();counts=collections.Counter();artifacts=0
    for ident,paper in expected.items():
        d=actual[ident];receipt=json.loads((d/'publication.json').read_text());sig=receipt['signature']
        assert sig['source_pdf_sha256']==paper['sha256']==digest(manifest.parent/paper['staged'])
        assert sig['layout_sha256']==digest(manifest.parent/paper['layout'])
        assert sig['library_sha256']==digest(manifest.parent/paper['glyph_library'])
        assert sig['processor_sha256'] in allowed,'Unrecognized processor revision'
        signatures[sig['processor_sha256']]+=1
        for name,h in receipt['artifacts'].items():
            path=(d/name).resolve();assert path.is_relative_to(d.resolve())
            assert digest(path)==h,(ident,name);artifacts+=1
        metadata=json.loads((d/'document.json').read_text())
        assert metadata['source_pdf_sha256']==paper['sha256']
        assets=rows(d/'assets.jsonl');body=rows(d/'llm_blocks.jsonl')
        assert len({a['asset_id'] for a in assets})==len(assets)
        assert len({b['block_id'] for b in body})==len(body)
        for a in assets:
            assert a['source_pdf_sha256']==paper['sha256']
            assert (d/a['image_path']).is_file() and a['source_regions']
            assert 1<=a['page']<=paper['pages'];counts[a['kind']]+=1
        for b in body:
            assert b['source_regions'] and 1<=b['page']<=paper['pages']
            assert b['quality_status'] in ('needs_review','automatic_unreviewed')
            if b['flags']:assert b['quality_status']=='needs_review'
        counts['body_blocks']+=len(body)
        counts['body_needs_review']+=sum(b['quality_status']=='needs_review' for b in body)
        counts['glyph_repairs']+=len(rows(d/'character_repairs.jsonl'))
    assert not list(collection.rglob('*.pdf')),'PDFs should not be included in returned/derived collection'
    result=dict(documents=len(papers),pages=sum(p['pages'] for p in papers),artifacts_verified=artifacts,
                all_source_and_publication_hashes_verified=True,processor_signatures=dict(signatures),
                counts=dict(counts),scientific_accuracy='not_certified')
    (collection/'integrity_verification.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--collection',type=Path,required=True)
    p.add_argument('--processor-root',type=Path,action='append',required=True);a=p.parse_args()
    print(json.dumps(verify(a.manifest,a.collection,a.processor_root)))
