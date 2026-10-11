"""Reuse verified source crops when PDF, page, display box and renderer match."""
import hashlib,json,os,shutil
from pathlib import Path
import pymupdf as fitz

class CropCache:
    def __init__(self,directory,source_sha256,renderer):
        self.root=directory.resolve();self.renderer=renderer;self.lookup={};self.reused=0;self.rendered=0
        receipt=json.loads((self.root/'publication.json').read_text());self.hashes=receipt['artifacts']
        if receipt['signature']['source_pdf_sha256']!=source_sha256:raise ValueError('Crop cache source PDF differs')
        for name in ['document.json','assets.jsonl','captions.json','blocks.jsonl']:self.checked(name)
        metadata=json.loads((self.root/'document.json').read_text())
        if metadata['parse_revision'] not in ('native-assets-v0.8-display-coordinates','native-assets-v0.9-caption-consolidation','native-assets-v0.10-figure-regions'):raise ValueError('Unknown crop rendering revision')
        if fitz.VersionBind!='1.26.4':raise ValueError('Crop cache renderer version differs')
        for line in (self.root/'assets.jsonl').read_text().splitlines():
            a=json.loads(line);self.add(a['page'],a['bbox'],a['image_path'])
        for c in json.loads((self.root/'captions.json').read_text()):
            self.add(c['page'],c['crop_bbox'],c['image_path'])
            for v in c.get('continuation_candidates',[]):self.add(v['page'],v['crop_bbox'],v['image_path'])
    def checked(self,relative):
        p=(self.root/relative).resolve()
        if not p.is_relative_to(self.root) or relative not in self.hashes or hashlib.sha256(p.read_bytes()).hexdigest()!=self.hashes[relative]:raise ValueError('Crop cache artifact changed: '+relative)
        return p
    def add(self,page,box,path):self.lookup[(page,tuple(box))]=path
    def __call__(self,page,box,destination,pad=4):
        rect=(fitz.Rect(box)+(-pad,-pad,pad,pad)) & page.rect;key=(page.number+1,tuple(rect))
        if key in self.lookup:
            source=self.checked(self.lookup[key])
            if destination.exists() or destination.is_symlink():raise FileExistsError(destination)
            try:os.link(source,destination)
            except FileExistsError:raise
            except OSError:shutil.copy2(source,destination)
            self.reused+=1;return list(rect)
        self.rendered+=1;return self.renderer(page,box,destination,pad=pad)
