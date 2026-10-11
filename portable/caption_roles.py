"""Conservative caption-role classification from existing source geometry."""
import re

def contains(outer,inner):
    return outer[0]<=inner[0] and outer[1]<=inner[1] and outer[2]>=inner[2] and outer[3]>=inner[3]

def classify(caption,assets):
    if caption.get('number') is not None or not re.fullmatch(r'\(?[A-Za-z]\)?',caption.get('text','').strip()):return {'role':'caption','parent_asset_ids':[]}
    candidates=[]
    for a in assets:
        if a['kind'] not in ('figure','scheme') or a['page']!=caption['page']:continue
        if caption.get('owner') not in a.get('member_blocks',[]):continue
        if not a.get('label') or not a.get('caption_regions'):continue
        if not contains(a['bbox'],caption['bbox']):continue
        # Formal captions may themselves lie inside the padded image crop.
        # A candidate must be vertically separate from every formal caption.
        if not all(caption['bbox'][3]<r['bbox'][1] or caption['bbox'][1]>r['bbox'][3] for r in a['caption_regions']):continue
        candidates.append(a['asset_id'])
    return {'role':'visual_annotation' if len(candidates)==1 else 'caption','parent_asset_ids':candidates if len(candidates)==1 else []}
