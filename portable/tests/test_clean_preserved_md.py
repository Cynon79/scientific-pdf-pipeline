import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clean_preserved_md import classify

def b(text,kind='text',page=4):return dict(text=text,type=kind,page=page,block_id=text)
class CleaningSafety(unittest.TestCase):
 def test_references_only_exact_heading(self):
  r=classify([b('Reference catalyst performance','title'),b('The reference catalyst removed ozone.'),b('References','title'),b('[1] Smith 2020 Journal 1 2')]);self.assertEqual([x['keep'] for x in r],[True,True,False,False])
 def test_interleaved_conclusion_is_kept(self):
  r=classify([b('Acknowledgements','title'),b('This study achieved 95% ozone removal within 30 min.'),b('This work was supported by grant No. 12.')]);self.assertEqual([x['keep'] for x in r],[False,True,False])
 def test_numbered_data_availability_is_scientific(self):
  r=classify([b('3.1. Data Availability. We analyzed 31 studies and 100 assays.')]);self.assertTrue(r[0]['keep'])
 def test_supplement_badge_does_not_remove_abstract(self):
  r=classify([b('Supporting Information','title',1),b('Ozone removal reached 95 percent.','abstract',1)]);self.assertEqual([x['keep'] for x in r],[False,True])
 def test_methods_after_references_preserved(self):
  r=classify([b('References','title'),b('[1] Smith (2020)'),b('Appendix B. Kinetic model','title'),b('The rate constant was calculated from ln(C/C0).')]);self.assertEqual([x['keep'] for x in r],[False,False,True,True])
 def test_chemical_front_text_preserved(self):
  r=classify([b('A full study of heterogeneous ozone catalysis','title',1),b('Mn<sup>2+</sup> and ozone react at surface sites.','text',1),b('Abstract','title',1)]);self.assertTrue(r[1]['keep'])
if __name__=='__main__':unittest.main()
