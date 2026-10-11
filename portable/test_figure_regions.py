"""Regression guards for source labels at the edge of scientific figures."""
import unittest
from figure_regions import region


class FigureRegionTests(unittest.TestCase):
    def bounds(self, annotations):
        visual=[70,68,520,250]
        members=[dict(owner='panel',bbox=visual,raw=dict(blocks=[
            dict(type='chart_caption',bbox=b) for b in annotations]))]
        return region(members,dict(page=1,bbox=[190,258,400,268]),1)

    def test_panel_label_crossing_crop_boundary_is_whole(self):
        box,excluded=self.bounds([[84,54,102,68],[316,54,334,69]])
        self.assertEqual(box,[70,54,520,268])
        self.assertEqual(excluded,[])

    def test_title_touching_render_padding_is_preserved(self):
        box,excluded=self.bounds([[143,49,451,65]])
        self.assertEqual(box[1],49)
        self.assertEqual(excluded,[])

    def test_distant_caption_and_large_paragraph_stay_excluded(self):
        box,excluded=self.bounds([[90,5,300,20],[90,25,300,70]])
        self.assertEqual(box,[70,68,520,268])
        self.assertEqual(len(excluded),2)

    def test_expansion_does_not_recursively_absorb_neighbor(self):
        box,excluded=self.bounds([[84,54,102,68],[84,39,102,54]])
        self.assertEqual(box[1],54)
        self.assertEqual(len(excluded),1)


if __name__=='__main__':unittest.main()
