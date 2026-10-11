import hashlib,json,sys,tempfile,unittest
from pathlib import Path
import pymupdf as fitz
from source_crop_cache import CropCache
class Cache(unittest.TestCase):
 def setup_cache(self,root):
  files={'document.json':json.dumps({'parse_revision':'native-assets-v0.9-caption-consolidation'}),'assets.jsonl':json.dumps(dict(page=1,bbox=[10,10,30,30],image_path='image.png'))+'\n','captions.json':'[]','blocks.jsonl':'','image.png':'image bytes'}
  for n,s in files.items():(root/n).write_text(s)
  (root/'publication.json').write_text(json.dumps(dict(signature=dict(source_pdf_sha256='source'),artifacts={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files})))
  def render(page,box,dest,pad=4):dest.write_bytes(b'rendered');return list((fitz.Rect(box)+(-pad,-pad,pad,pad)) & page.rect)
  return CropCache(root,'source',render)
 def test_same_box_reused_other_box_rendered(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);cache=self.setup_cache(r);doc=fitz.open();p=doc.new_page()
   cache(p,[14,14,26,26],r/'reused.png');cache(p,[20,20,30,30],r/'new.png')
   self.assertEqual((r/'reused.png').read_bytes(),b'image bytes');self.assertEqual((cache.reused,cache.rendered),(1,1))
 def test_source_or_corrupted_image_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);cache=self.setup_cache(r)
   with self.assertRaises(ValueError):CropCache(r,'other',lambda *a:None)
   (r/'image.png').write_bytes(b'changed');doc=fitz.open();p=doc.new_page()
   with self.assertRaises(ValueError):cache(p,[14,14,26,26],r/'out.png')
 def test_existing_destination_never_overwritten(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);cache=self.setup_cache(r);(r/'out.png').write_bytes(b'keep');doc=fitz.open();p=doc.new_page()
   with self.assertRaises(FileExistsError):cache(p,[14,14,26,26],r/'out.png')
   self.assertEqual((r/'out.png').read_bytes(),b'keep')
if __name__=='__main__':unittest.main()
