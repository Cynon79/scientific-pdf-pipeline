"""Preservation contract checks; does not certify visual/scientific accuracy."""
import json,sqlite3,sys
from pathlib import Path
from consumer_exports import load_jsonl
from search_assets import query
p=Path(sys.argv[1]);counts=json.loads((p/'search_counts.json').read_text());ncap=0;ncand=0;nbody=0
for d in (p/'documents').iterdir():
    caps=json.loads((d/'captions.json').read_text());ids={c['caption_id'] for c in caps}
    for c in caps:
        assert (d/c['image_path']).is_file();ncap+=1
        for v in c['continuation_candidates']:
            assert v['page']==c['page']+1
            assert (d/v['image_path']).is_file();ncand+=1
    for a in load_jsonl(d/'assets.jsonl'):
        assert a['index_mode']=='image_caption_context_only'
        assert set(a['caption_ids'])<=ids
    body=load_jsonl(d/'llm_blocks.jsonl');nbody+=len(body)
    assert (d/'llm.md').stat().st_size>100
    for b in body:
        assert b['source_regions']
        assert b['quality_status'] in ('needs_review','automatic_unreviewed')
        if b['flags']:assert b['quality_status']=='needs_review'
assert counts['caption']==ncap and counts.get('caption_candidate',0)==ncand and counts['body']==nbody
hits=query(p,'ozone',kind='equation',limit=100)
assert hits
assert all('mineru_transcription' not in h['payload'] and 'native_text' not in h['payload'] for h in hits)
db=sqlite3.connect(p/'search.sqlite')
assert db.execute('select count(*) from entries').fetchone()[0]==sum(counts.values())
result=dict(preservation_contract='PASS',scientific_accuracy='NOT_YET_VALIDATED',captions=ncap,caption_candidates=ncand,llm_blocks=nbody,search_records=sum(counts.values()),api_calls=0)
(p/'preservation_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
