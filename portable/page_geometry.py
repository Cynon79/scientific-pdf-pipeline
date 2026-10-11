"""Display-coordinate adapter; keeps source PDF bytes and CropBox unchanged."""
import pymupdf as fitz

def display_box(page,box):return list(fitz.Rect(box)*page.rotation_matrix) if page.rotation else list(box)

def display_characters(page,characters):
    if not page.rotation:return characters
    matrix=page.rotation_matrix
    for c in characters:
        c['unrotated_bbox']=list(c['bbox']);c['unrotated_origin']=list(c['origin'])
        c['bbox']=display_box(page,c['bbox']);c['origin']=list(fitz.Point(c['origin'])*matrix)
        dx,dy=c['direction'];c['direction']=[matrix.a*dx+matrix.c*dy,matrix.b*dx+matrix.d*dy]
    return characters

def display_words(page):
    return [tuple(display_box(page,w[:4]))+tuple(w[4:]) for w in page.get_text('words')]

def display_lines(page):
    for block in page.get_text('dict',flags=0)['blocks']:
        for line in block.get('lines',[]):yield dict(line,bbox=display_box(page,line['bbox']))
