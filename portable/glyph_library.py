"""Cross-PDF reuse by font family + exact glyph outline, never character code.
Initial supported representation: embedded CFF fonts. Other formats are reported
as unsupported and retained for local OCR/review, rather than guessed.
"""
import hashlib,io,json
from collections import defaultdict
from fontTools.cffLib import CFFFontSet
from fontTools.pens.recordingPen import RecordingPen

def outline_table(doc,xref):
    name,ext,kind,data=doc.extract_font(xref)
    if ext!='cff':return {}
    cff=CFFFontSet();cff.decompile(io.BytesIO(data),None);top=cff[cff.fontNames[0]];result={}
    if not hasattr(top,'charset'):return {}
    for gid,name in enumerate(top.charset):
        if name=='.notdef':continue
        pen=RecordingPen();top.CharStrings[name].draw(pen)
        # Numeric normalization allows integer/float representation differences;
        # geometric scaling/approximate matching is deliberately not attempted.
        commands=[(op,[[round(float(v),6) for v in point] for point in points]) for op,points in pen.value]
        digest=hashlib.sha256(json.dumps(commands,separators=(',',':')).encode()).hexdigest()
        result[gid]=dict(glyph_name=name,outline_sha256=digest)
    return result

def glyph_observations(doc, diagnostics=None):
    from native_text import page_characters
    tables={};result=[]
    for page in doc:
        bad=[c for c in page_characters(page) if any(ord(v)<32 or v in '\ufffd\ufffe\uffff' for v in c['c'])]
        if not bad:continue
        needed={c['font'] for c in bad}
        font_tables=defaultdict(list)
        for row in page.get_fonts():
            if row[3].split('+')[-1] not in needed:continue
            if row[0] not in tables:
                try:tables[row[0]]=outline_table(doc,row[0])
                except Exception as error:
                    tables[row[0]]={}
                    if diagnostics is not None:diagnostics.append(dict(page=page.number+1,font=row[3],reason=type(error).__name__))
            font_tables[row[3].split('+')[-1]].append(tables[row[0]])
        traces=defaultdict(set)
        for span in page.get_texttrace():
            for unicode,gid,origin,box in span['chars']:
                traces[(span['font'],round(origin[0],3),round(origin[1],3))].add(gid)
        for c in bad:
            gids=traces.get((c['font'],round(c['origin'][0],3),round(c['origin'][1],3)),set())
            if len(gids)!=1:continue
            gid=next(iter(gids));matches=[t[gid] for t in font_tables[c['font']] if gid in t]
            if not matches or len({m['outline_sha256'] for m in matches})!=1:continue
            result.append(dict(page=page.number+1,char_id=c['char_id'],font=c['font'],original=c['c'],bbox=c['bbox'],**matches[0]))
    return result

def build_library(doc,review):
    known={(e['font'],e['original']):e['replacement'] for e in review['mappings']};entries={}
    for o in glyph_observations(doc):
        value=known.get((o['font'],o['original']))
        if value is None:continue
        key=(o['font'],o['outline_sha256'])
        if key in entries and entries[key]['replacement']!=value:raise ValueError('Ambiguous outline semantics')
        entries[key]=dict(font=o['font'],outline_sha256=o['outline_sha256'],glyph_name=o['glyph_name'],replacement=value,review_id=review['review_id'],evidence_pdf_sha256=review['source_pdf_sha256'])
    return list(entries.values())

def propose_from_library(doc,entries):
    lookup=defaultdict(set)
    for e in entries:lookup[(e['font'],e['outline_sha256'])].add(e['replacement'])
    proposals=[]
    for o in glyph_observations(doc):
        values=lookup.get((o['font'],o['outline_sha256']),set())
        if len(values)==1:proposals.append(dict(**o,replacement=next(iter(values)),method='exact_outline_in_same_font_family'))
    return proposals

def apply_library(doc,characters,entries):
    """Apply exact outline matches to the observed source characters only."""
    proposals=propose_from_library(doc,entries)
    for p in proposals:
        c=characters[p['page']][p['char_id']]
        if c['c']!=p['original'] or c['font']!=p['font']:raise ValueError('Character observation changed')
        c['original_c']=c['c'];c['c']=p['replacement']
        c['glyph_outline_sha256']=p['outline_sha256']
        c['glyph_review_id']=sorted({e['review_id'] for e in entries if e['font']==p['font'] and e['outline_sha256']==p['outline_sha256']})
    return proposals
