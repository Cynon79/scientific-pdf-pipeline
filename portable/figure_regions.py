"""Compute figure regions without importing distant stray caption detections."""
def union(boxes):return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]

def boundary_annotation(box, visual):
    """Keep short owned annotations that the four-point render padding would cut.

    Use the original visual extent, never recursively enlarged caption boxes.
    Long paragraphs and horizontally remote detections remain review candidates.
    """
    return (0 < box[3]-box[1] <= 24
            and visual[0]-12 <= box[0] < box[2] <= visual[2]+12
            and box[3] >= visual[1]-4 and box[1] <= visual[3]+4)

def region(members,caption,page):
    boxes=[m['bbox'] for m in members]
    for m in members:
        boxes.extend(v['bbox'] for v in m['raw'].get('blocks',[]) if v.get('type') in ('image_body','chart_body') and v.get('bbox'))
    visual=union(boxes);near=[visual[0]-12,visual[1]-12,visual[2]+12,visual[3]+12];excluded=[]
    for m in members:
        for v in m['raw'].get('blocks',[]):
            b=v.get('bbox')
            if not b or v.get('type') in ('image_body','chart_body'):continue
            contained=near[0]<=b[0] and near[1]<=b[1] and near[2]>=b[2] and near[3]>=b[3]
            boundary=v.get('type') in ('image_caption','chart_caption') and boundary_annotation(b,visual)
            if contained or boundary:boxes.append(b)
            else:excluded.append(dict(owner=m['owner'],type=v.get('type'),bbox=b,reason='outside_visual_extent_and_margin'))
    if caption['page']==page:boxes.append(caption['bbox'])
    return union(boxes),excluded
