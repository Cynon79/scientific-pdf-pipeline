import unittest
from asset_quality import review_reasons
class Quality(unittest.TestCase):
 def test_formula_without_caption_is_not_missing_caption(self):
  self.assertEqual(review_reasons(dict(kind='equation',bbox=[0,0,10,10])),[])
  self.assertEqual(review_reasons(dict(kind='table',bbox=[0,0,10,10])),['missing_caption'])
 def test_flags_and_ambiguous_continuation_are_visible(self):
  a=dict(kind='figure',caption='Fig. 1 caption',bbox=[0,0,10,10],flags=['body_overlap_needs_review'],continuation_group_status='same_label_needs_review')
  self.assertEqual(review_reasons(a),['body_overlap_needs_review','same_label_needs_review'])
 def test_inside_unused_region_not_reported_as_excluded(self):
  a=dict(kind='figure',caption='Fig. 1',bbox=[0,0,10,10],excluded_region_candidates=[dict(bbox=[1,1,5,5])],continuation_group_status='explicit_continuation')
  self.assertEqual(review_reasons(a),[])
  a['excluded_region_candidates'].append(dict(bbox=[20,20,30,30]));self.assertEqual(review_reasons(a),['excluded_region_candidate'])
if __name__=='__main__':unittest.main()
