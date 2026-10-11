"""Derive consumer review reasons from preserved asset diagnostics."""
def review_reasons(asset):
    reasons=set(asset.get('flags',[]))
    reasons.update('caption_'+f for f in asset.get('caption_flags',[]) if f!='caption_from_text_block')
    if asset['kind']=='unassigned_visual':reasons.add('unassigned_visual')
    if asset['kind'] in ('figure','scheme','table') and not asset.get('caption','').strip():reasons.add('missing_caption')
    group=asset.get('continuation_group_status')
    if group in ('same_label_needs_review','continuation_start_missing'):reasons.add(group)
    if asset.get('caption_continuation_candidates'):reasons.add('caption_continuation_candidate')
    b=asset['bbox']
    if any(not (b[0]<=e['bbox'][0] and b[1]<=e['bbox'][1] and b[2]>=e['bbox'][2] and b[3]>=e['bbox'][3]) for e in asset.get('excluded_region_candidates',[])):reasons.add('excluded_region_candidate')
    return sorted(reasons)
