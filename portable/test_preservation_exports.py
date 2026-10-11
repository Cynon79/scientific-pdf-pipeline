import json,tempfile,unittest
from pathlib import Path
from consumer_exports import export_document,build_search
from search_assets import query

class PreservationTests(unittest.TestCase):
    def test_unverified_transcription_not_searchable_and_cross_page_caption_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/'documents'/'d';(d/'assets').mkdir(parents=True)
            b=dict(block_id='d:b',document_id='d',page=1,type='text',text='Ozone removal on MnO₂.',flags=[],source_regions=[{'page_1based':1,'bbox':[1,1,20,20]}],section_path=[])
            c=dict(caption_id='d:c',page=1,bbox=[1,600,40,700],text='Table 1. Ozone removal',flags=[],continuation_candidates=[dict(block_id='d:continued',page=2,bbox=[1,20,40,70],text='continued catalyst conditions',status='possible_continuation_needs_review')])
            a=dict(asset_id='d:t',document_id='d',kind='table',page=1,bbox=[1,300,40,700],image_path='assets/table.png',caption=c['text'],caption_regions=[{'page':1,'bbox':c['bbox']}],label='Table 1',linked_block_ids=['d:b'],native_text='POISON_UNVERIFIED_CELL',mineru_transcription='POISON_UNVERIFIED_FORMULA')
            def crop(page,box,path):path.write_bytes(b'fixture');return box
            export_document(d,[None,None],[b],[c],[a],crop)
            self.assertTrue((d/c['image_path']).exists())
            self.assertTrue((d/c['continuation_candidates'][0]['image_path']).exists())
            self.assertEqual(c['continuation_candidates'][0]['page'],2)
            self.assertNotIn('POISON',a['retrieval_text'])
            (d/'assets.jsonl').write_text(json.dumps(a)+'\n');(d/'captions.json').write_text(json.dumps([c]))
            build_search(root)
            self.assertFalse(query(root,'POISON_UNVERIFIED_CELL'))
            self.assertEqual(query(root,'MnO2',kind='table')[0]['record_id'],'d:t')
            result=query(root,'continued',kind='caption_candidate')[0]
            self.assertEqual(result['quality'],'needs_review')
            self.assertEqual(int(result['page']),2)
            self.assertEqual(query(root,'Ozone',kind='body')[0]['record_id'],'d:b')
    def test_unmapped_character_is_not_silently_accepted(self):
        from native_text import render_characters
        c=dict(c='\x02',size=10,origin=[0,10],bbox=[0,0,5,12],direction=[1,0])
        text,flags=render_characters([c])
        self.assertEqual(text,'�');self.assertIn('unmapped_native_glyph',flags)

if __name__=='__main__':unittest.main()
