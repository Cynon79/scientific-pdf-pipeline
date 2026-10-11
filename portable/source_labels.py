"""Recover printed asset labels from original PDF geometry, not recognition."""
import re
from page_geometry import display_words,display_lines

def label_above(page,box,kind):
    pattern=r'Table\s+(\d+[A-Za-z]?)\s*\.?$' if kind=='table' else r'(?:Fig(?:ure)?\.?|Scheme\.?)\s+(\d+[A-Za-z]?)\s*\.?$'
    candidates=[]
    for line in display_lines(page):
        text=''.join(s['text'] for s in line['spans']).strip();r=line['bbox']
        if re.fullmatch(pattern,text,re.I) and -2<=box[1]-r[3]<=18 and abs(r[0]-box[0])<=15:candidates.append((box[1]-r[3],text,list(r)))
    if not candidates:return None
    candidates.sort();return candidates[0][1:]

def equation_number(page,box):
    mid=page.rect.width/2;limit=mid+8 if box[2]<mid else page.rect.width
    candidates=[]
    for w in display_words(page):
        match=re.fullmatch(r'\((\d+[a-z]?)\)',w[4])
        if not match:continue
        dy=abs((w[1]+w[3]-box[1]-box[3])/2)
        if w[0]>=box[2]-12 and w[2]<=limit and dy<=max(10,(box[3]-box[1])/2) and w[0]-box[2]<260:candidates.append((match[1],list(w[:4])))
    return candidates[0] if len(candidates)==1 else None
