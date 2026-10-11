import hashlib,io,json,tarfile,tempfile,unittest
from pathlib import Path
from import_parse_outputs import import_archive,sha

def bundle(root,rows):
 p=root/'return.tar.gz';entries=[]
 with tarfile.open(p,'w:gz') as tar:
  for name,data in rows:
   i=tarfile.TarInfo(name);i.size=len(data);tar.addfile(i,io.BytesIO(data));entries.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
  m=json.dumps(dict(files=entries,completed=['d'],pending=[],pdfs_included=False)).encode();i=tarfile.TarInfo('return_manifest.json');i.size=len(m);tar.addfile(i,io.BytesIO(m))
 return p
class ImportTests(unittest.TestCase):
 def test_verified_import_and_resume(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=bundle(root,[('outputs/d/auto/d.md',b'body')]);out=root/'out'
   self.assertEqual(import_archive(p,out,sha(p))['imported_files'],1)
   self.assertEqual(import_archive(p,out,sha(p))['imported_files'],0)
 def test_conflict_checks_all_before_any_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=bundle(root,[('new.json',b'{}'),('old.json',b'new')]);out=root/'out';out.mkdir();(out/'old.json').write_bytes(b'old')
   with self.assertRaises(ValueError):import_archive(p,out,sha(p))
   self.assertFalse((out/'new.json').exists());self.assertEqual((out/'old.json').read_bytes(),b'old')
 def test_pdf_traversal_duplicate_and_bad_checksum_rejected(self):
  for rows in [[('../escape.json',b'{}')],[('x.pdf',b'PDF')],[('x.json',b'{}'),('x.json',b'{}')]]:
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);p=bundle(root,rows)
    with self.assertRaises(ValueError):import_archive(p,root/'out',sha(p))
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=bundle(root,[('x.json',b'{}')])
   with self.assertRaises(ValueError):import_archive(p,root/'out','0'*64)
if __name__=='__main__':unittest.main()
