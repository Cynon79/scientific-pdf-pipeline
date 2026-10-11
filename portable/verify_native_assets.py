"""Verify packaging and retrieval, without asserting scientific accuracy."""
import json,sqlite3,sys
from pathlib import Path
from collections import Counter
p=Path(sys.argv[1]);assets=[json.loads(x) for x in (p/'asset_catalog.jsonl').read_text().splitlines()]
assert not list(p.rglob('*.pdf')), 'PDF must not be copied to return package'
assert len({a['asset_id'] for a in assets})==len(assets)
for a in assets:
 assert (p/a['image_path_in_collection']).is_file()
 d=p/a['package_path'];blocks=[json.loads(x) for x in (d/'blocks.jsonl').read_text().splitlines()]
 ids={b['block_id'] for b in blocks}
 assert all(x in ids for x in a['linked_block_ids'])
 for b in blocks:
  assert not any(ord(c)<32 and c not in '\n\r\t' for c in b['text'])
  if b.get('review_image'):assert (d/b['review_image']).is_file()
 if a.get('recognized_html'):assert (d/a['recognized_html']).is_file()
db=sqlite3.connect(p/'asset_search.sqlite')
assert db.execute('select count(*) from asset_search').fetchone()[0]==len(assets)
hits=db.execute("select count(*) from asset_search where asset_search match 'ozone'").fetchone()[0]
assert hits>0
result=dict(package_checks='PASS',scientific_accuracy='NOT_YET_VALIDATED',assets=len(assets),counts=dict(Counter(a['kind'] for a in assets)),ozone_search_hits=hits,pdfs_in_return_package=0)
(p/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
