"""Portable, standard-library-only staging and verification. No model/API calls."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile

VERSION = '0.1-preparation'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def inside(root, relative):
    """Require portable paths, rejecting escape and symlink dependencies."""
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or '\\' in relative or not rel.parts:
        raise ValueError(f'Nonportable path: {relative}')
    current = Path(root)
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'Symlink dependency: {relative}')
    current.resolve().relative_to(Path(root).resolve())
    return current


def copy_checked(source, dest, expected=None):
    source = Path(source)
    before = sha(source)
    if expected and before != expected:
        raise ValueError(f'Source identity mismatch: {source.name}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    if sha(dest) != before:
        raise ValueError(f'Copy verification failed: {source.name}')
    return before


def stage_inputs(entries, root):
    if not isinstance(entries, list) or not entries:
        raise ValueError('A nonempty list of PDF entries is required')
    documents = {}
    for entry in entries:
        source = Path(entry['pdf']).resolve(strict=True)
        with source.open('rb') as stream:
            if b'%PDF-' not in stream.read(1024):
                raise ValueError(f'Not a PDF header: {source.name}')
        digest = sha(source)
        if digest not in documents:
            rel = f'inputs/{digest}.pdf'
            copy_checked(source, root / rel, digest)
            documents[digest] = {'document_id': digest, 'source_pdf': rel,
                                 'source_pdf_sha256': digest, 'aliases': [], 'asset_package': None,
                                 'document_role': 'unconfirmed', 'paper_id': None, 'title': None}
        documents[digest]['aliases'].append({'filename': source.name, 'label': entry.get('label', source.stem)})
    return list(documents.values())


def text_blocks(text):
    """Preserve source lines; legacy blocks have no invented PDF coordinates."""
    result, section, pending = [], [], []
    def flush():
        if not pending:
            return
        start, end = pending[0][0], pending[-1][0]
        content = '\n'.join(line for _, line in pending)
        heading = re.match(r'^(#{1,6})\s+(.+)$', content)
        if heading:
            depth = len(heading[1])
            section[:] = section[:depth-1] + [heading[2]]
        kind = 'heading' if heading else ('table' if '<table' in content else 'text')
        result.append({'block_id': f'b{len(result)+1:05d}', 'type': kind, 'text': content,
                       'reading_order': len(result), 'section_path': list(section),
                       'md_lines': [start, end], 'source_regions': [],
                       'source_mapping_status': 'unavailable_in_legacy_md'})
        pending.clear()
    for index, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            flush()
        else:
            if line.startswith('#'):
                flush()
            pending.append((index, line))
    flush()
    return result


def import_demo(records, root, documents):
    """Import reviewed source crops; do not claim automatic figure detection."""
    for doc in documents:
        selected = [r for r in records if r['source_pdf_sha256'] == doc['document_id']]
        if not selected:
            continue
        base = root / 'documents' / doc['document_id'] / 'legacy_demo_v1'
        base.mkdir(parents=True)
        first = selected[0]
        copy_checked(first['body_md_path'], base / 'body.md', first['body_md_sha256'])
        copy_checked(first['caption_md_path'], base / 'raw.md', first['caption_md_sha256'])
        text = (base / 'body.md').read_text(encoding='utf-8')
        blocks = text_blocks(text)
        figures, relations = [], []
        for item in selected:
            # Every record must belong to this exact source revision.
            for path_key, hash_key in [('source_pdf', 'source_pdf_sha256'),
                                       ('body_md_path', 'body_md_sha256'),
                                       ('caption_md_path', 'caption_md_sha256')]:
                if sha(item[path_key]) != item[hash_key]:
                    raise ValueError(f'Demo source changed: {path_key}')
            if item['body_md_sha256'] != first['body_md_sha256'] or item['caption_md_sha256'] != first['caption_md_sha256']:
                raise ValueError('Mixed MD revisions in one demo document')
            figure_id = 'fig' + re.fullmatch(r'Figure (\d+)', item['figure_id'])[1]
            image_path, caption_path = f'assets/{figure_id}.png', f'assets/{figure_id}_caption.png'
            copy_checked(item['image_path'], base / image_path, item['image_sha256'])
            copy_checked(item['caption_image_path'], base / caption_path)
            figures.append({'figure_id': figure_id, 'label': item['figure_id'], 'image': image_path,
                            'caption_image': caption_path, 'caption_text': item['caption_from_raw_md'],
                            'caption_raw_md_line': item['caption_md_line'],
                            'page_1based': item['page_1based'], 'page_size_points': item['page_size_points'],
                            'bbox_points_top_left': item['bbox_points_top_left'],
                            'caption_bbox_points_top_left': item['caption_bbox_points_top_left'],
                            'group_status': item['group_status'], 'bbox_method': item['bbox_method'],
                            'caption_text_status': item['caption_text_status']})
            for ref in item['body_reference_candidates']:
                matching = [b for b in blocks if b['md_lines'][0] <= ref['start_line'] <= ref['end_line'] <= b['md_lines'][1]]
                excerpt = '\n'.join(text.splitlines()[ref['start_line']-1:ref['end_line']])
                if len(matching) != 1 or excerpt != ref['text']:
                    raise ValueError('Body reference no longer matches source MD')
                relations.append({'source_block_id': matching[0]['block_id'], 'target_figure_id': figure_id,
                                  'relation_type': 'mentions_candidate', 'status': 'not_semantically_reviewed'})
        jsonl(base / 'blocks.jsonl', blocks)
        jsonl(base / 'figures.jsonl', figures)
        jsonl(base / 'relations.jsonl', relations)
        write(base / 'quality.json', {'scope': 'selected_manual_figures_only', 'scientific_ready': False,
                                     'missing': ['body_pdf_coordinates', 'all_figures_inventory', 'table_region_mapping',
                                                 'legacy_raw_image_links_unresolved'],
                                     'tables': 'existing HTML retained verbatim in body.md'})
        gallery = ['# 完整组图样例', '', '[完整正文（旧解析文字，未修正）](body.md)', '']
        for f in figures:
            gallery += [f"## {f['label']}", '', f"![]({f['image']})", '',
                        f"[原图注裁片]({f['caption_image']})", '', f['caption_text'], '']
        (base / 'reading.md').write_text('\n'.join(gallery), encoding='utf-8')
        doc['asset_package'] = base.relative_to(root).as_posix()


def seal(root, documents):
    write(root / 'bundle.json', {'schema_version': VERSION, 'documents': documents,
                                'scope': 'portable_inputs_and_optional_manual_demo; not production ingest'})
    files = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
    write(root / 'files.json', files)


def build(entries, destination, demo=None):
    destination = Path(destination).absolute()
    if destination.exists():
        raise ValueError('Output already exists; use a new bundle directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage-', dir=destination.parent) as folder:
        staging = Path(folder) / 'bundle'
        staging.mkdir()
        documents = stage_inputs(entries, staging)
        if demo:
            import_demo(demo, staging, documents)
        seal(staging, documents)
        verify(staging)
        # Refuse concurrent writers instead of replacing an existing bundle.
        if destination.exists():
            raise ValueError('Output appeared during preparation')
        staging.rename(destination)
    return verify(destination)


def verify_box(box, size):
    if len(box) != 4 or len(size) != 2 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in box + size):
        raise ValueError('Invalid region coordinates')
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1]):
        raise ValueError('Region is outside the source page')


def verify(root):
    root = Path(root)
    files = read(inside(root, 'files.json'))
    if not isinstance(files, dict) or 'bundle.json' not in files:
        raise ValueError('Missing bundle inventory')
    for rel, digest in files.items():
        path = inside(root, rel)
        if not path.is_file() or sha(path) != digest:
            raise ValueError(f'Missing or changed file: {rel}')
    bundle = read(root / 'bundle.json')
    if bundle['schema_version'] != VERSION or not bundle['documents']:
        raise ValueError('Unsupported or empty bundle')
    ids, figures_total = set(), 0
    for doc in bundle['documents']:
        key = doc['document_id']
        if key in ids or key != doc['source_pdf_sha256']:
            raise ValueError('Duplicate or inconsistent document identity')
        ids.add(key)
        if doc['source_pdf'] not in files or sha(inside(root, doc['source_pdf'])) != key:
            raise ValueError('Invalid PDF identity')
        if not doc['asset_package']:
            continue
        base = inside(root, doc['asset_package'])
        def asset(rel):
            path = inside(base, rel)
            if path.relative_to(root).as_posix() not in files:
                raise ValueError(f'Uninventoried asset: {rel}')
            return path
        blocks, figures = rows(asset('blocks.jsonl')), rows(asset('figures.jsonl'))
        lines = asset('body.md').read_text(encoding='utf-8').splitlines()
        block_ids, figure_ids = {b['block_id'] for b in blocks}, {f['figure_id'] for f in figures}
        if len(block_ids) != len(blocks) or len(figure_ids) != len(figures):
            raise ValueError('Duplicate block or figure IDs')
        for index, b in enumerate(blocks):
            start, end = b['md_lines']
            if not (1 <= start <= end <= len(lines)) or b['reading_order'] != index or '\n'.join(lines[start-1:end]) != b['text']:
                raise ValueError('Block/source text mismatch')
        raw_lines = asset('raw.md').read_text(encoding='utf-8').splitlines()
        for f in figures:
            asset(f['image']); asset(f['caption_image'])
            verify_box(f['bbox_points_top_left'], f['page_size_points'])
            verify_box(f['caption_bbox_points_top_left'], f['page_size_points'])
            if type(f['page_1based']) is not int or f['page_1based'] < 1:
                raise ValueError('Invalid source page')
            line = f['caption_raw_md_line']
            if not (1 <= line <= len(raw_lines)) or raw_lines[line-1] != f['caption_text']:
                raise ValueError('Caption/source text mismatch')
        for rel in rows(asset('relations.jsonl')):
            if rel['source_block_id'] not in block_ids or rel['target_figure_id'] not in figure_ids:
                raise ValueError('Dangling text/figure relation')
        if read(asset('quality.json'))['scientific_ready'] is not False:
            raise ValueError('Preparation bundle cannot claim scientific readiness')
        for link in re.findall(r'\]\(([^)]+)\)', asset('reading.md').read_text(encoding='utf-8')):
            asset(link)
        figures_total += len(figures)
    return {'state': 'portable_structure_verified', 'documents': len(ids), 'figures': figures_total,
            'inventoried_files': len(files), 'scientific_ready': False}


def plan(root, config):
    verify(root)
    if config['mineru_version'] != '3.4.4' or config['backend'] != 'hybrid-engine':
        raise ValueError('Only the reviewed 3.4.4 Hybrid command contract is supported')
    if config['efforts'] != ['medium', 'high'] or config['image_analysis'] is not False:
        raise ValueError('The initial comparison fixes image analysis off and compares medium/high')
    tasks = []
    identity = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    for doc in read(Path(root) / 'bundle.json')['documents']:
        for effort in config['efforts']:
            task_id = f"{doc['document_id'][:16]}_{identity[:16]}_{effort}"
            tasks.append({'task_id': task_id, 'state': 'planned_not_run', 'document_id': doc['document_id'],
                          'configuration_sha256': identity,
                          'argv_relative_to_bundle': ['mineru', '-p', doc['source_pdf'], '-o', f'results/{task_id}',
                                                     '-b', 'hybrid-engine', '--effort', effort,
                                                     '--image-analysis', 'false', '-m', 'auto', '-f', 'true', '-t', 'true']})
    return {'scope': 'commands only; no submission or model calls', 'tasks': tasks,
            'requirements_before_execution': ['GPU allocation and environment validation', 'pin model identities',
                                               'record effective server environment', 'configure persistent service and bounded workers']}


def doctor():
    try:
        mineru = importlib.metadata.version('mineru')
    except importlib.metadata.PackageNotFoundError:
        mineru = None
    gpu = {'available': False, 'devices': []}
    if shutil.which('nvidia-smi'):
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'],
                                    capture_output=True, text=True, timeout=10)
            gpu = {'available': result.returncode == 0 and bool(result.stdout.strip()),
                   'devices': result.stdout.strip().splitlines() if result.returncode == 0 else []}
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {'platform': platform.system(), 'machine': platform.machine(), 'python': platform.python_version(),
            'mineru_version': mineru, 'gpu': gpu, 'free_disk_bytes': shutil.disk_usage('.').free,
            'tools_present': {n: bool(shutil.which(n)) for n in ['sbatch', 'srun', 'apptainer', 'docker', 'mineru']},
            'gpu_smoke_test_candidate': platform.system() == 'Linux' and gpu['available'] and mineru == '3.4.4',
            'deployment_validated': False,
            'note': 'Inventory only; model loading, CUDA execution and scheduler allocation are not tested.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('manifest', type=Path); p.add_argument('output', type=Path)
    p = sub.add_parser('import-demo'); p.add_argument('manifest', type=Path); p.add_argument('output', type=Path)
    p = sub.add_parser('verify'); p.add_argument('bundle', type=Path)
    p = sub.add_parser('plan'); p.add_argument('bundle', type=Path); p.add_argument('--config', type=Path, required=True)
    sub.add_parser('doctor')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            entries = read(args.manifest)
            for entry in entries:
                if not Path(entry['pdf']).is_absolute():
                    entry['pdf'] = str(args.manifest.parent / entry['pdf'])
            result = build(entries, args.output)
        elif args.command == 'import-demo':
            demo = read(args.manifest)
            result = build([{'pdf': r['source_pdf'], 'label': r['document_id']} for r in demo], args.output, demo)
        elif args.command == 'verify':
            result = verify(args.bundle)
        elif args.command == 'plan':
            result = plan(args.bundle, read(args.config))
        else:
            result = doctor()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        print(json.dumps({'state': 'failed', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
