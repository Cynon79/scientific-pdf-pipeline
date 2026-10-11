"""Position-based PDF text reconstruction; does not rewrite scientific content."""
from collections import Counter
import html
import re
import unicodedata

SUB = str.maketrans('0123456789+-=()', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎')
SUP = str.maketrans('0123456789+-−=()', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾')

def page_characters(page, glyph_review=None):
    import pymupdf as fitz
    raw = page.get_text('rawdict', flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)
    result = []
    for block in raw['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for c in span['chars']:
                    result.append(dict(c=c['c'], bbox=list(c['bbox']), origin=list(c['origin']),
                                       font=span['font'], size=span['size'], direction=list(line['dir']), char_id=len(result)))
    if glyph_review:
        from glyph_repairs import repair_characters
        result=repair_characters(result,page,glyph_review)
    return result

def select_characters(chars, box, padding=1.2):
    x0,y0,x1,y1=box
    return [c for c in chars if x0-padding <= (c['bbox'][0]+c['bbox'][2])/2 <= x1+padding
            and y0 <= c['origin'][1] <= y1+padding]

def render_characters(chars):
    """Retain scripts using measured baseline offsets, not chemical-name rules."""
    if not chars:return '', ['no_native_characters']
    chars=[c for c in chars if c['c'] not in ('\r','\n')]
    sizes=Counter(round(c['size'],1) for c in chars if c['c'].strip())
    if not sizes:return '', ['no_native_characters']
    base_size=sizes.most_common(1)[0][0]
    primary=[c for c in chars if c['size']>=base_size*.9 and c['c'].strip()]
    rows=[]
    for c in sorted(primary,key=lambda c:c['origin'][1]):
        y=c['origin'][1]
        nearest=min(rows,key=lambda r:abs(r['y']-y)) if rows else None
        if nearest is None or abs(nearest['y']-y)>base_size*.13:rows.append(dict(y=y,chars=[]))
    for c in chars:
        row=min(rows,key=lambda r:abs(r['y']-c['origin'][1]))
        row['chars'].append(c)
    lines=[];flags=[]
    for row in sorted(rows,key=lambda r:r['y']):
        # Subscripts and superscripts sometimes share the same horizontal origin.
        def key(c):
            x=c['origin'][0]
            if c['c'].isspace():
                overlaps=[v for v in row['chars'] if v['c'].strip() and x<=v['origin'][0]<c['bbox'][2]-.01]
                if overlaps and all(v['size']<base_size*.91 and abs(v['origin'][1]-row['y'])>base_size*.1 for v in overlaps):
                    x=max(v['bbox'][2] for v in overlaps)+.01
            return (round(x,2), -c['origin'][1])
        parts=[];previous=None;seen=set()
        for c in sorted(row['chars'],key=key):
            identity=(c['c'],round(c['origin'][0],2),round(c['origin'][1],2))
            if identity in seen:continue
            seen.add(identity)
            dy=c['origin'][1]-row['y']
            script='sub' if c['size']<base_size*.91 and dy>base_size*.10 else (
                'sup' if c['size']<base_size*.91 and dy<-base_size*.10 else None)
            value=c['c']
            if any(unicodedata.category(v)=='Cc' or v in '\ufffd\ufffe\uffff' for v in value):
                flags.append('unmapped_native_glyph')
                value='�'
            if previous is not None and value.strip() and not script:
                gap=c['bbox'][0]-previous['bbox'][2]
                if gap>base_size*.20 and parts and not parts[-1].endswith(' '):parts.append(' ')
            if script and value.strip():
                trans=SUB if script=='sub' else SUP
                if ord(value) in trans:value=value.translate(trans)
                elif value not in '⋅·•−◦°':value=f'<{script}>{html.escape(value)}</{script}>'
            else:value=html.escape(value)
            parts.append(value);previous=c
            if c['c'] in ('\ufffd','\ufffe','\uffff'):flags.append('unmapped_native_glyph')
            if abs(c['direction'][1])>.01:flags.append('rotated_text')
        line=''.join(parts).strip()
        lines.append(line)
    text=''
    for line in lines:
        if not text:text=line
        elif text.endswith('\xad'):text=text[:-1]+line
        else:text+=' '+line
    text=text.replace('\xad','')
    return re.sub(r'\s+',' ',text).strip(),sorted(set(flags))

def extract(chars,box):
    selected=select_characters(chars,box)
    text,flags=render_characters(selected)
    return text,flags,[c['char_id'] for c in selected]

def search_text(value):
    value=html.unescape(re.sub(r'<[^>]*>','',value))
    return unicodedata.normalize('NFKC',value)

def typography(chars,box):
    selected=[c for c in select_characters(chars,box) if c['c'].strip()]
    counts=Counter((c['font'],round(c['size'],1)) for c in selected)
    if not counts:return None
    (font,size),count=counts.most_common(1)[0]
    return dict(font=font,size=size,dominant_characters=count,total_characters=len(selected))
