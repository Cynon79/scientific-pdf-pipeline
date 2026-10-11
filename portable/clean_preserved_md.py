"""Initial MD denoising for preserved MinerU packages; no semantic chunking.

Reuse legacy heading normalization. Work on a new derived MD view and keep
original packages, scientific text, captions, assets and uncertainty untouched.
"""
import argparse,collections,hashlib,html,importlib.util,json,os,re,sys,unicodedata
from pathlib import Path
LEGACY=Path(__file__).resolve().with_name('legacy_clean_md_batch.py')
spec=importlib.util.spec_from_file_location('legacy_clean_md',LEGACY)
legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)

def norm(text):
 t=html.unescape(re.sub(r'<[^>]+>','',text))
 t=unicodedata.normalize('NFKC',t)
 t=re.sub(r'^[■▪•★*\s]+','',t)
 t=re.sub(r'^\d+(?:\.\d+)*[.)]?\s+','',t)
 return legacy.normalize_heading(t)

REF=re.compile(r'^(?:references?(?: and notes)?|bibliography|literature cited|参考文献)$')
META=re.compile(r'^(?:acknowledg(?:e)?ments?|author information|authors?|corresponding authors?|author contributions?|credit authorship contribution statement|declarations?(?: of competing interests?)?|competing interests?(?: statement)?|conflicts? of interests?(?: statement)?|data availability(?: statement)?|availability of data and materials|funding(?: information| sources| statement)?|notes|ethical approval|ethics declarations|author affiliations?)$')
SUPP=re.compile(r'^(?:(?:appendix [a-z][. ]+)?(?:supporting|supplementary) (?:information|data|material|materials)|associated content)$')
PROTECTED=re.compile(r'^(?:abstract|introduction|background|keywords?|highlights|graphical abstract|significance|conclusions?(?:\b.*)?|results(?:\b.*)?|discussion(?:\b.*)?|experimental(?:\b.*)?|materials and methods|methods(?:\b.*)?)$')
INLINE_META=re.compile(r'^(?:acknowledg(?:e)?ments?|author affiliations?|author contributions?|conflicts? of interests?|data availability(?: statement)?)[.:]\s*',re.I)
PUB=re.compile(r'^(?:received(?:\s+in revised form)?|revised|accepted(?: manuscript online)?|published online|version of record online|available online)\s*[:：]\s*',re.I)
MARKER=re.compile(r'(?m)^<!-- (?P<id>[^;\n]+); page=\d+; quality=[^\n]+ -->\n')

def rows(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def metadata_content(text):
 t=norm(text)
 return bool(re.search(
  r"\b(?:university|institute|department|school of|college of|laboratory of|orcid|e-?mail)\b|"
  r"\b(?:supported|funded|funding|financial support|grant no|grant number|acknowledge|gratefully|thank)\b|"
  r"\b(?:no|declare|declares|declared|declaration).{0,65}(?:conflict|competing|financial interest)|"
  r"\b(?:data|datasets?).{0,70}(?:available|request|deposited|accessed)|"
  r"\b(?:available|obtained).{0,45}supporting information|"
  r"\b(?:supplementary|supporting).{0,80}(?:online|free of charge|https?://)|"
  r"writing.{0,30}(?:review|original draft)|conceptualization|data curation|formal analysis|"
  r"\b(?:equal contribution|contributed equally|copyright|creative commons|publisher.s note)\b",t))

def front_metadata(text):
 t=norm(text)
 if re.match(r'^(?:abstract|keywords?|highlights)\b',t):return False
 if re.search(r'\b(?:university|institute|department|school of|college of|orcid|e-?mail)\b',t):return True
 # Name lists have no sentence punctuation or scientific verbs/quantities.
 if len(t.split())>45 or re.search(r'[.!?;:]|\b(?:is|are|was|were|can|has|have|using|show|shows|catalyst|ozone|oxidation|degradation)\b|\d',t):return False
 return bool(re.search(r'<sup>|,|\band\b',text))

def classify(blocks):
 """Return keep/drop decisions for existing source regions, never new chunks."""
 normalized=[norm(b['text']) for b in blocks]
 abstract=next((i for i,b in enumerate(blocks) if b['type']=='abstract' or normalized[i]=='abstract'),None)
 intro=next((i for i,t in enumerate(normalized) if t=='introduction'),None)
 front_end=abstract if abstract is not None else intro
 first_title=next((i for i,b in enumerate(blocks) if b['type']=='title' and b['page']<=2 and len(b['text'].split())>=5),None)
 mode=None;decisions=[];front_keywords=False
 for i,b in enumerate(blocks):
  text=b['text'];t=normalized[i];short=len(t.split())<=12
  heading=b['type']=='title' or (short and (REF.fullmatch(t) or META.fullmatch(t)))
  reason=None
  if b['type']=='ref_text':reason='parser_reference_record'
  elif heading and REF.fullmatch(t):mode='references';reason='reference_heading'
  elif heading and META.fullmatch(t) and not (t.startswith('data availability') and re.match(r'^\d',text.strip())):mode='metadata';reason='metadata_heading'
  elif heading and SUPP.fullmatch(t):
   # First-page SI badges are metadata only; never consume the abstract.
   mode='supplement_notice' if b['page']>2 else None;reason='supplement_notice_heading'
  elif PROTECTED.fullmatch(t) or b['type']=='abstract':
   mode=None;front_keywords=t.startswith('keyword')
  elif heading and mode!='references':mode=None
  elif mode=='references' and heading and not re.match(r'^\[?\d+[\].)]',text) and not re.search(r'\b(?:19|20)\d{2}\b|doi|https?://',t):
   # Preserve substantive appendices/methods appearing after bibliography.
   mode=None
  if reason is None and mode and (mode=='references' or metadata_content(text)):reason=mode+'_content'
  if reason is None and INLINE_META.match(t) and not re.match(r'^\d',text.strip()) and metadata_content(text):reason='explicit_inline_metadata'
  if reason is None and (legacy.is_junk_line(text) or PUB.match(t) or t in ('article info','article information','access')):reason='publication_noise'
  if reason is None and front_end is not None and i<front_end and i!=first_title and b['page']<=2:
   if re.match(r'^keywords?\b',t):front_keywords=True
   elif b['type']=='title' and t not in ('highlights','graphical abstract'):front_keywords=False
   # Preserve long introductory text, scientific highlights and keyword content.
   if not front_keywords and b['type']=='text' and front_metadata(text):reason='short_front_matter'
  decisions.append(dict(block_id=b['block_id'],keep=reason is None,reason=reason,page=b['page']))
 return decisions

def clean_document(d,out):
 blocks=rows(d/'llm_blocks.jsonl');decisions=classify(blocks);byid={r['block_id']:r for r in decisions}
 source=(d/'llm.md').read_text();body,assets=source.rsplit('\n## 图表公式引用\n',1)
 matches=list(MARKER.finditer(body));assert len(matches)==len(blocks)
 outparts=['# 清洗正文\n\n仅去除明确的参考文献与出版元数据；原文质量提示保留，尚未逐字人工核验。\n'];removed=[];kept=[]
 for i,m in enumerate(matches):
  ident=m['id'];b=blocks[i];assert b['block_id']==ident
  segment=body[m.start():matches[i+1].start() if i+1<len(matches) else len(body)]
  assert b['text'] in segment
  if byid[ident]['keep']:outparts.append(segment);kept.append(ident)
  else:removed.append(dict(**byid[ident],text=b['text']))
 # Keep exact caption text and all source-asset references; only rebase paths.
 assets=re.sub(r'\]\((assets/[^)]+)\)',lambda m:']('+os.path.relpath(d/m[1],out)+')',assets)
 outparts.append('\n## 图表公式引用\n'+assets)
 clean='\n'.join(outparts)
 assert kept,'No retained body regions'
 path=out/(d.name+'.md');path.write_text(clean)
 return dict(document_id=d.name,input_sha256=sha(d/'llm.md'),output_sha256=sha(path),input_chars=len(source),output_chars=len(clean),input_regions=len(blocks),retained_regions=len(kept),removed_regions=len(removed),reasons=dict(collections.Counter(r['reason'] for r in removed)),retained_ids=kept,removed=removed,source_md=os.path.relpath(d/'llm.md',out))

def run(collection,out):
 if out.exists():raise ValueError('Choose a new output directory; originals are immutable')
 assert out.resolve().is_relative_to(collection.resolve())
 out.mkdir(parents=True);reports=[]
 for d in sorted((collection/'documents').iterdir()):
  if (d/'publication.json').is_file():reports.append(clean_document(d,out))
 log=out/'cleaning_log.jsonl';log.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in reports))
 summary=dict(documents=len(reports),removed_regions=sum(r['removed_regions'] for r in reports),input_chars=sum(r['input_chars'] for r in reports),output_chars=sum(r['output_chars'] for r in reports),removal_reasons=dict(sum((collections.Counter(r['reasons']) for r in reports),collections.Counter())),original_packages_modified=False,asset_files_copied=0,semantic_chunking=False,legacy_code=str(LEGACY),legacy_sha256=sha(LEGACY),cleaner_sha256=sha(Path(__file__)))
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--collection',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.collection,a.out)
