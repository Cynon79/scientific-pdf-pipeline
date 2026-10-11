"""Read-only lexical search over body, captions and preserved assets."""
import argparse,json,sqlite3
from pathlib import Path

def query(root,text,kind=None,limit=10):
    # Treat user terms as literal FTS tokens, not SQL or FTS operators.
    from native_text import search_text
    words=search_text(text).split()
    if not words:return []
    expression=' AND '.join('"'+w.replace('"','""')+'"' for w in words)
    db=sqlite3.connect((root/'search.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    sql='SELECT record_id,document_id,kind,page,quality,image_path,payload,snippet(entries,7,"[", "]", " … ",32) AS excerpt FROM entries WHERE entries MATCH ?'
    params=[expression]
    if kind:sql+=' AND kind=?';params.append(kind)
    sql+=' ORDER BY rank LIMIT ?';params.append(limit)
    try:
        rows=[dict(r) for r in db.execute(sql,params)]
        for r in rows:r['payload']=json.loads(r['payload'])
        return rows
    finally:db.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('text');ap.add_argument('--kind',choices=['body','figure','scheme','table','equation','caption','caption_candidate','visual_annotation','unassigned_visual','source_caption_candidate','source_text_candidate','definitions_candidate']);ap.add_argument('--limit',type=int,default=10)
    a=ap.parse_args()
    if not 1<=a.limit<=100:ap.error('--limit must be 1..100')
    print(json.dumps(query(a.root,a.text,a.kind,a.limit),ensure_ascii=False,indent=2))
