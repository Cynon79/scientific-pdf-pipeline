import unittest
from propose_text_repairs import propose
class Repairs(unittest.TestCase):
 def test_preserves_scripts_and_changes_only_missing_symbol(self):
  a='Catalyst �-MnO₂ decomposes ozone at 30 °C.';b='Catalyst α-MnO2 decomposes ozone at 30 °C.'
  r=propose(a,b);self.assertEqual(len(r),1);self.assertEqual(r[0]['replacement'],'α');self.assertEqual(a[r[0]['offset']],'�')
 def test_does_not_rewrite_valid_but_different_text(self):
  self.assertEqual(propose('Catalyst δ-MnO₂ decomposes ozone.','Catalyst 8-MnO2 decomposes ozone.'),[])
 def test_rejects_unrelated_ocr(self):
  self.assertEqual(propose('Catalyst �-MnO₂ decomposes ozone.','Different results suggest platinum performs well.'),[])
 def test_requires_bilateral_matching_context(self):
  self.assertEqual(propose('�-MnO₂ decomposes ozone.','α-MnO2 decomposes ozone.'),[])
 def test_html_and_subscript_positions_remain_original(self):
  a='The value x<sub>i</sub> and �-MnO₂ were recorded.';b='The value xi and γ-MnO2 were recorded.'
  r=propose(a,b);self.assertEqual(len(r),1);self.assertEqual(a[r[0]['offset']],'�')
if __name__=='__main__':unittest.main()
