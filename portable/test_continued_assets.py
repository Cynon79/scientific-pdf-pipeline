import unittest
from continued_assets import group_assets
class Continued(unittest.TestCase):
 def asset(self,i,page,text):return dict(asset_id=str(i),document_id='d',kind='table',label='Table 1',page=page,caption=text,image_path=str(i)+'.png')
 def test_explicit_continuation_shares_caption_without_stitching(self):
  a=[self.asset(1,1,'Table 1. Catalyst properties.'),self.asset(2,2,'Table 1 (continued)')];g=group_assets(a)
  self.assertEqual(g[0]['state'],'explicit_continuation');self.assertFalse(g[0]['images_stitched']);self.assertEqual(a[1]['group_caption_source_asset_id'],'1')
 def test_repeated_number_without_evidence_requires_review(self):
  a=[self.asset(1,1,'Table 1. First'),self.asset(2,2,'Table 1. Second')];g=group_assets(a);self.assertEqual(g[0]['state'],'same_label_needs_review');self.assertNotIn('group_caption',a[1])
 def test_missing_first_part_is_not_complete(self):
  a=[self.asset(1,2,'Table 1 (continued)'),self.asset(2,3,'Table 1 (continued)')];self.assertEqual(group_assets(a)[0]['state'],'continuation_start_missing')
if __name__=='__main__':unittest.main()
