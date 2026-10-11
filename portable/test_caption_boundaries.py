import unittest
from caption_links import continuation_candidates
from consumer_exports import classify_embedded_labels
class BoundaryTests(unittest.TestCase):
 def fixtures(self):
  c=dict(page=1,bbox=[20,700,550,760],text='Fig. 1. Complete caption.',kind='figure',number='1',typography=dict(size=7.2,dominant_characters=100))
  b=dict(block_id='next',page=2,bbox=[20,40,270,100],text='The next paragraph describes different scientific results.',type='text',typography=dict(size=8,dominant_characters=100))
  return c,b
 def test_complete_caption_and_body_font_not_merged(self):
  c,b=self.fixtures();self.assertFalse(continuation_candidates(c,[b],{1:[600,800],2:[600,800]}));self.assertEqual(c['rejected_continuation_candidates'][0]['block_id'],'next')
 def test_explicit_label_survives_font_change(self):
  c,b=self.fixtures();b['text']='Fig. 1. Continued description on a second page.'
  self.assertEqual(len(continuation_candidates(c,[b],{1:[600,800],2:[600,800]})),1)
 def test_incomplete_caption_survives_font_change_for_review(self):
  c,b=self.fixtures();c['text']='Fig. 1. Caption continues with'
  self.assertEqual(len(continuation_candidates(c,[b],{1:[600,800],2:[600,800]})),1)
 def test_only_label_inside_figure_is_excluded(self):
  a=dict(asset_id='fig',kind='figure',page=1,bbox=[20,20,200,200])
  blocks=[dict(type='text',text='(b)',page=1,bbox=[30,30,40,40]),dict(type='text',text='B',page=1,bbox=[220,30,230,40]),dict(type='text',text='Catalyst B',page=1,bbox=[30,40,150,50])]
  classify_embedded_labels(blocks,[a]);self.assertEqual(blocks[0]['role'],'embedded_visual_label');self.assertNotIn('role',blocks[1]);self.assertNotIn('role',blocks[2])
if __name__=='__main__':unittest.main()
