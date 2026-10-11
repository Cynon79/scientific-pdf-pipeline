"""Behavior tests for migration, identity, broken associations and honest status."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import platform_cli as app


class PortablePlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root / 'source.pdf'
        self.pdf.write_bytes(b'%PDF-1.7\nunit-test fixture; not a visual PDF\n')
        self.dest = self.root / 'bundle'

    def prepare(self):
        return app.build([{'pdf': str(self.pdf)}], self.dest)

    def demo(self):
        body = self.root / 'body.md'
        body.write_text('# Title\n\nObservation (Figure 1).\n\nFigure 1. Caption.\n')
        raw = self.root / 'raw.md'
        raw.write_text('Figure 1. Caption.\n')
        figure, caption = self.root / 'figure.png', self.root / 'caption.png'
        figure.write_bytes(b'fixture figure bytes'); caption.write_bytes(b'fixture caption bytes')
        record = {'source_pdf': str(self.pdf), 'source_pdf_sha256': app.sha(self.pdf),
                  'body_md_path': str(body), 'body_md_sha256': app.sha(body),
                  'caption_md_path': str(raw), 'caption_md_sha256': app.sha(raw),
                  'image_path': str(figure), 'image_sha256': app.sha(figure),
                  'caption_image_path': str(caption), 'caption_from_raw_md': 'Figure 1. Caption.',
                  'caption_md_line': 1, 'figure_id': 'Figure 1', 'page_1based': 1,
                  'page_size_points': [600, 800], 'bbox_points_top_left': [20, 20, 500, 400],
                  'caption_bbox_points_top_left': [20, 410, 500, 450],
                  'group_status': 'unreviewed_fixture', 'bbox_method': 'test_fixture',
                  'caption_text_status': 'uncorrected',
                  'body_reference_candidates': [{'start_line': 3, 'end_line': 3, 'text': 'Observation (Figure 1).'}]}
        return record

    def build_demo(self):
        record = self.demo()
        app.build([{'pdf': str(self.pdf)}], self.dest, [record])
        doc = app.read(self.dest / 'bundle.json')['documents'][0]
        return self.dest / doc['asset_package']

    def reseal_file(self, path):
        # A hash alone is insufficient: semantic validation must also fail.
        inventory = app.read(self.dest / 'files.json')
        inventory[path.relative_to(self.dest).as_posix()] = app.sha(path)
        app.write(self.dest / 'files.json', inventory)

    def test_identical_pdf_aliases_deduplicate(self):
        twin = self.root / 'renamed.pdf'; shutil.copyfile(self.pdf, twin)
        result = app.build([{'pdf': str(self.pdf)}, {'pdf': str(twin)}], self.dest)
        self.assertEqual(result['documents'], 1)
        self.assertEqual(len(app.read(self.dest / 'bundle.json')['documents'][0]['aliases']), 2)

    def test_same_filename_different_content_not_deduplicated(self):
        other = self.root / 'other'; other.mkdir()
        twin = other / self.pdf.name; twin.write_bytes(b'%PDF-1.7\ndifferent paper\n')
        result = app.build([{'pdf': str(self.pdf)}, {'pdf': str(twin)}], self.dest)
        self.assertEqual(result['documents'], 2)

    def test_relocation_works_without_original_paths(self):
        self.build_demo()
        moved = self.root / 'new mount 中文' / 'bundle'; moved.parent.mkdir()
        shutil.move(self.dest, moved)
        for p in self.root.iterdir():
            if p.is_file(): p.unlink()
        result = app.verify(moved)
        self.assertEqual(result['figures'], 1)
        self.assertFalse(result['scientific_ready'])

    def test_existing_output_never_overwritten(self):
        self.prepare()
        before = app.sha(self.dest / 'bundle.json')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(app.sha(self.dest / 'bundle.json'), before)

    def test_invalid_input_leaves_no_final_bundle(self):
        self.pdf.write_text('not a PDF')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())

    def test_tampered_input_detected(self):
        self.prepare()
        next((self.dest / 'inputs').glob('*.pdf')).write_bytes(b'%PDF-altered')
        with self.assertRaisesRegex(ValueError, 'changed'): app.verify(self.dest)

    def test_missing_image_detected(self):
        base = self.build_demo(); (base / 'assets/fig1.png').unlink()
        with self.assertRaises(ValueError): app.verify(self.dest)

    def test_path_escape_and_symlink_rejected(self):
        with self.assertRaises(ValueError): app.inside(self.root, '../elsewhere')
        with self.assertRaises(ValueError): app.inside(self.root, '/absolute/path')
        (self.root / 'linked.pdf').symlink_to(self.pdf)
        with self.assertRaises(ValueError): app.inside(self.root, 'linked.pdf')

    def test_dangling_relation_rejected_even_with_valid_hash(self):
        base = self.build_demo(); path = base / 'relations.jsonl'
        rel = app.rows(path); rel[0]['target_figure_id'] = 'fig999'; app.jsonl(path, rel); self.reseal_file(path)
        with self.assertRaisesRegex(ValueError, 'Dangling'): app.verify(self.dest)

    def test_wrong_source_line_rejected_even_with_valid_hash(self):
        base = self.build_demo(); path = base / 'blocks.jsonl'
        blocks = app.rows(path); blocks[1]['md_lines'] = [1, 1]; app.jsonl(path, blocks); self.reseal_file(path)
        with self.assertRaisesRegex(ValueError, 'text mismatch'): app.verify(self.dest)

    def test_out_of_page_figure_rejected(self):
        base = self.build_demo(); path = base / 'figures.jsonl'
        figures = app.rows(path); figures[0]['bbox_points_top_left'][2] = 900
        app.jsonl(path, figures); self.reseal_file(path)
        with self.assertRaisesRegex(ValueError, 'outside'): app.verify(self.dest)

    def test_changed_historical_md_rejected_on_import(self):
        record = self.demo(); Path(record['body_md_path']).write_text('revised')
        with self.assertRaises(ValueError): app.build([{'pdf': str(self.pdf)}], self.dest, [record])
        self.assertFalse(self.dest.exists())

    def test_preparation_cannot_claim_scientific_readiness(self):
        base = self.build_demo(); path = base / 'quality.json'
        quality = app.read(path); quality['scientific_ready'] = True; app.write(path, quality); self.reseal_file(path)
        with self.assertRaisesRegex(ValueError, 'scientific'): app.verify(self.dest)

    def test_plan_changes_with_config_and_never_runs(self):
        self.prepare()
        config = {'mineru_version': '3.4.4', 'backend': 'hybrid-engine',
                  'efforts': ['medium', 'high'], 'image_analysis': False, 'model_revision': None}
        first = app.plan(self.dest, config)
        self.assertEqual(len(first['tasks']), 2)
        self.assertTrue(all(t['state'] == 'planned_not_run' for t in first['tasks']))
        self.assertFalse((self.dest / 'results').exists())
        config['model_revision'] = 'new-model'
        self.assertNotEqual(first['tasks'][0]['task_id'], app.plan(self.dest, config)['tasks'][0]['task_id'])
        config['mineru_version'] = '2.0.4'
        with self.assertRaises(ValueError): app.plan(self.dest, config)


if __name__ == '__main__':
    unittest.main()
