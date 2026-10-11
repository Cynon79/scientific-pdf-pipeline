import unittest
from caption_roles import classify
class Roles(unittest.TestCase):
 def setUp(self):
  self.asset=dict(asset_id='fig3',kind='figure',page=6,label='Fig. 3',bbox=[30,50,562,369],member_blocks=['b0'],caption_regions=[dict(page=6,bbox=[34,353,558,365])])
  self.cap=dict(number=None,page=6,owner='b0',bbox=[40,54,65,74],text='(a)')
 def test_long_text_inside_badly_oversized_figure_stays_caption(self):
  self.cap['text']='Summary of the adsorption energy and bonding lengths.'
  self.assertEqual(classify(self.cap,[self.asset])['role'],'caption')
 def test_internal_annotation_has_parent(self):self.assertEqual(classify(self.cap,[self.asset]),dict(role='visual_annotation',parent_asset_ids=['fig3']))
 def test_formal_caption_band_and_other_owner_not_reclassified(self):
  self.cap['bbox']=[40,354,90,363];self.assertEqual(classify(self.cap,[self.asset])['role'],'caption')
  self.cap['bbox']=[40,54,65,74];self.cap['owner']='other';self.assertEqual(classify(self.cap,[self.asset])['role'],'caption')
 def test_labeled_or_ambiguous_not_reclassified(self):
  self.cap['number']='3';self.assertEqual(classify(self.cap,[self.asset])['role'],'caption')
  self.cap['number']=None;self.assertEqual(classify(self.cap,[self.asset,dict(self.asset,asset_id='other')])['role'],'caption')
if __name__=='__main__':unittest.main()
