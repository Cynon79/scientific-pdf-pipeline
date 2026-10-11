"""Apply visually reviewed font decoding maps, scoped to an exact source PDF."""
import hashlib,json
from pathlib import Path

def load_review(path,source_sha):
    data=json.loads(Path(path).read_text())
    if data['source_pdf_sha256']!=source_sha:raise ValueError('Glyph review belongs to another PDF')
    if data['status']!='source_glyphs_visually_reviewed':raise ValueError('Unreviewed glyph map')
    return data

def page_font_hashes(page):
    result={}
    for font in page.get_fonts():
        name=font[3].split('+')[-1]
        digest=hashlib.sha256(page.parent.extract_font(font[0])[3]).hexdigest()
        result.setdefault(name,set()).add(digest)
    return result

def repair_characters(chars,page,review):
    hashes=page_font_hashes(page)
    for c in chars:
        entries=[e for e in review['mappings'] if e['font']==c['font'] and e['original']==c['c']]
        if not entries:continue
        if len(entries)!=1:raise ValueError('Ambiguous glyph review entries')
        entry=entries[0]
        if hashes.get(c['font'])!={entry['font_sha256']}:
            raise ValueError('Embedded font identity changed or is ambiguous')
        c['original_c']=c['c'];c['c']=entry['replacement'];c['glyph_review_id']=review['review_id']
    return chars
