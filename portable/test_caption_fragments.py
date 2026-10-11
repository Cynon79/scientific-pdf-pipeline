import unittest
from caption_fragments import consolidate

def cap(ident,text,box,owner='table0',number='3'):
 return dict(caption_id=ident,text=text,bbox=box,owner=owner,page=9,kind='table',number=number,flags=[])
class Fragments(unittest.TestCase):
 def test_label_and_title_keep_long_caption_and_source(self):
  a=cap('a','Table 3',[49,152,80,161]);b=cap('b','Table 3 Molecular characterization.',[49,151,420,171])
  result=consolidate([a,b]);self.assertEqual(len(result),1);self.assertEqual(result[0]['caption_id'],'b');self.assertEqual(result[0]['absorbed_caption_fragments'][0],a)
  self.assertNotIn('absorbed_caption_fragments',b)
 def test_different_owner_or_noncontained_box_not_absorbed(self):
  a=cap('a','Table 3',[49,152,80,161]);b=cap('b','Table 3 Caption.',[49,180,420,200])
  self.assertEqual(len(consolidate([a,b])),2)
  b['bbox']=[49,151,420,171];b['owner']='other';self.assertEqual(len(consolidate([a,b])),2)
 def test_ambiguous_two_titles_not_chosen(self):
  caps=[cap('a','Table 3',[49,152,80,161]),cap('b','Table 3 One title.',[49,151,420,171]),cap('c','Table 3 Another title.',[49,151,420,171])]
  self.assertEqual(len(consolidate(caps)),3)
if __name__=='__main__':unittest.main()
