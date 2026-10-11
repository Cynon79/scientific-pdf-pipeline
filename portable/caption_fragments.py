"""Consolidate redundant caption fragments belonging to one layout object."""
import copy,re
from collections import defaultdict

def normalize(text):
    return re.sub(r'\s+',' ',text).strip().rstrip('.').casefold()

def consolidate(captions):
    """Only absorb contained text with the same owner, label and overlapping box.

    Distinct captions and ambiguous adjacent prose are left intact. Preserve the
    absorbed source records so consolidation cannot erase provenance.
    """
    result=copy.deepcopy(captions);groups=defaultdict(list);removed=set()
    for i,c in enumerate(result):
        if c.get('number') is not None:
            groups[(c['page'],c['owner'],c['kind'],c['number'])].append(i)
    for indices in groups.values():
        for i in sorted(indices,key=lambda i:len(normalize(result[i]['text']))):
            if i in removed:continue
            c=result[i];text=normalize(c['text']);box=c['bbox'];choices=[]
            if not text:continue
            for j in indices:
                if i==j or j in removed:continue
                other=result[j];long=normalize(other['text']);b=other['bbox']
                if len(long)<=len(text) or not long.startswith(text+' '):continue
                if min(box[2],b[2])<=max(box[0],b[0]) or min(box[3],b[3])<max(box[1],b[1]):continue
                if not all([b[0]<=box[0]+3,b[1]<=box[1]+3,b[2]>=box[2]-3,b[3]>=box[3]-3]):continue
                choices.append(j)
            if len(choices)!=1:continue
            target=result[choices[0]]
            target.setdefault('absorbed_caption_fragments',[]).append(copy.deepcopy(c))
            target['flags']=sorted(set(target.get('flags',[])+c.get('flags',[])))
            removed.add(i)
    return [c for i,c in enumerate(result) if i not in removed]
