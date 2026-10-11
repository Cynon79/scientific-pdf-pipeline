"""Link separately preserved page regions carrying explicit continued labels."""
import re
from collections import defaultdict

def group_assets(assets):
    grouped=defaultdict(list)
    for a in assets:
        if a.get('label') and a['kind'] in ('figure','scheme','table'):
            grouped[(a['document_id'],a['kind'],a['label'].replace('.','').lower())].append(a)
    results=[]
    for (doc,kind,label),members in grouped.items():
        if len(members)<2:continue
        members=sorted(members,key=lambda a:a['page']);pages=[a['page'] for a in members]
        explicit=all(re.search(r'\bcontinued\b',a['caption'],re.I) for a in members[1:])
        state='explicit_continuation' if explicit and len(set(pages))==len(pages) else 'same_label_needs_review'
        if re.search(r'\bcontinued\b',members[0]['caption'],re.I):state='continuation_start_missing'
        gid=f'{doc}:{kind}:{label.replace(" ","_")}:pages'
        row=dict(group_id=gid,state=state,asset_ids=[a['asset_id'] for a in members],pages=pages,
                 image_paths=[a['image_path'] for a in members],caption=members[0]['caption'],images_stitched=False)
        for a in members:
            a['continuation_group_id']=gid;a['continuation_group_status']=state
            if state=='explicit_continuation':
                a['group_caption']=members[0]['caption'];a['group_caption_source_asset_id']=members[0]['asset_id']
        results.append(row)
    return results
