"""Verify a structured return archive before importing immutable files."""
import argparse,hashlib,json,os,tarfile,tempfile
from pathlib import Path,PurePosixPath

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def import_archive(archive,destination,expected_sha256):
    if sha(archive)!=expected_sha256:raise ValueError('Archive checksum mismatch')
    root=destination.resolve();root.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive) as tar:
        members=tar.getmembers();names=[m.name for m in members]
        if len(names)!=len(set(names)) or any(not m.isfile() for m in members):raise ValueError('Duplicate or nonregular archive member')
        manifest=json.load(tar.extractfile('return_manifest.json'))
        if manifest.get('pdfs_included') is not False:raise ValueError('Missing no-PDF declaration')
        entries=manifest['files'];paths=[e['path'] for e in entries]
        if len(paths)!=len(set(paths)) or set(names)!={'return_manifest.json',*paths}:raise ValueError('Archive member list mismatch')
        checked=[]
        for entry in entries:
            relative=PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts or str(relative)!=entry['path'] or relative.suffix not in ('.json','.md'):raise ValueError('Disallowed return path')
            dest=root/str(relative)
            if not dest.resolve().is_relative_to(root):raise ValueError('Return path escapes destination')
            if any(p.is_symlink() for p in [dest,*dest.parents] if p!=root and p.is_relative_to(root)):raise ValueError('Symlink destination')
            data=tar.extractfile(entry['path']).read()
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Member checksum mismatch')
            if dest.exists() and (not dest.is_file() or sha(dest)!=entry['sha256']):raise ValueError('Existing output differs')
            checked.append((entry,dest))
        imported=0
        for entry,dest in checked:
            if dest.exists():continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            fd,temp=tempfile.mkstemp(prefix='.incoming-',dir=dest.parent)
            try:
                with os.fdopen(fd,'wb') as f:f.write(tar.extractfile(entry['path']).read())
                try:os.link(temp,dest);imported+=1
                except FileExistsError:
                    if sha(dest)!=entry['sha256']:raise ValueError('Concurrent output differs')
            finally:os.unlink(temp)
    return dict(completed=len(manifest['completed']),pending=len(manifest['pending']),verified_files=len(checked),imported_files=imported,pdfs_returned=0,archive_sha256=expected_sha256)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--destination',type=Path,required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args()
    print(json.dumps(import_archive(a.archive,a.destination,a.sha256)))
