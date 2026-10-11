"""Conservative caption association. Figures remain on one physical page."""
import re

LABEL=re.compile(r'^(Fig(?:ure)?\.?|Scheme\.?|Table)\s*(S?\d+)\b[\s.:]*(.*)',re.I|re.S)

def parse_label(text):
    m=LABEL.match(text.strip())
    if not m:return None
    kind='table' if m[1].lower()=='table' else ('scheme' if m[1].lower().startswith('scheme') else 'figure')
    return kind,m[2]

def union(boxes):
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]

def horizontal(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))/max(1,min(a[2]-a[0],b[2]-b[0]))

def associate(visuals,captions,page_sizes):
    groups=[];unassigned=[]
    for c in captions:
        if c['kind']!='table' and c.get('number') is not None:groups.append(dict(caption=c,members=[],method='same_page_caption'))
    for v in visuals:
        bb=v['bbox'];p=v['page']
        candidates=[g for g in groups if g['caption']['page']==p and
                    (g['caption'].get('owner')==v['owner'] or
                     (g['caption']['bbox'][1]>=bb[3]-15 and horizontal(bb,g['caption']['bbox'])>=.2))]
        if not candidates:unassigned.append(v);continue
        nearest=min(g['caption']['bbox'][1] for g in candidates)
        row=[g for g in candidates if abs(g['caption']['bbox'][1]-nearest)<30]
        own=[g for g in row if g['caption'].get('owner')==v['owner']]
        chosen=own[0] if own else min(row,key=lambda g:abs(sum(g['caption']['bbox'][::2])/2-sum(bb[::2])/2))
        chosen['members'].append(v)
    # Adjacent-page links remain candidates, even when unique. No forced crop union
    # when several independent figures could be present on the source page.
    adjacent=[]
    for v in unassigned:
        if (v['bbox'][2]-v['bbox'][0])*(v['bbox'][3]-v['bbox'][1])<400:continue
        for g in groups:
            c=g['caption']
            if g['members'] or c['page']!=v['page']+1:continue
            if v['bbox'][3]<page_sizes[v['page']][1]*.6 or c['bbox'][1]>page_sizes[c['page']][1]*.25:continue
            if horizontal(v['bbox'],c['bbox'])<.2:continue
            adjacent.append(dict(visual_id=v['visual_id'],caption_id=c['caption_id'],
                                 figure_page=v['page'],caption_page=c['page'],status='candidate_needs_review'))
    return [g for g in groups if g['members']],unassigned,adjacent

def continuation_candidates(caption,blocks,page_sizes):
    p=caption['page'];h=page_sizes[p][1]
    if caption['bbox'][3]<h*.65:return []
    result=[]
    for b in blocks:
        if b['page']!=p+1 or b['bbox'][1]>page_sizes.get(p+1,[0,0])[1]*.25:continue
        if b['type'] in ('title','ref_text') or horizontal(caption['bbox'],b['bbox'])<.2:continue
        label=parse_label(b['text'])
        if label and label!=(caption['kind'],caption['number']):continue
        if len(b['text'])<25:continue
        if not label and caption['text'].rstrip().endswith(('.', '。')) and caption['bbox'][3]<h*.90:continue
        cp=caption.get('typography');bp=b.get('typography')
        if not label and caption['text'].rstrip().endswith(('.', '。')) and cp and bp and min(cp['dominant_characters'],bp['dominant_characters'])>=20 and abs(cp['size']-bp['size'])/max(cp['size'],1)>.07:
            caption.setdefault('rejected_continuation_candidates',[]).append(dict(block_id=b['block_id'],page=b['page'],bbox=b['bbox'],reason='completed_sentence_and_font_size_mismatch',caption_typography=cp,block_typography=bp))
            continue
        result.append(dict(block_id=b['block_id'],page=b['page'],bbox=b['bbox'],text=b['text'],
                           status='explicit_repeated_label' if label else 'possible_continuation_needs_review'))
    return result
