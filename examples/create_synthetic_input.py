"""Generate an authored one-page PDF and mock MinerU layout; never runs MinerU."""
import argparse
import hashlib
import json
from pathlib import Path
import pymupdf as fitz


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=False)
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((50, 60), "Synthetic materials document", fontsize=16)
    page.insert_text((50, 105), "Synthetic ozone example. Figure 1 is an authored diagram, not research data.", fontsize=11)
    page.draw_rect(fitz.Rect(60, 160, 300, 280), color=(0, 0, 0))
    page.draw_line(fitz.Point(80, 260), fitz.Point(275, 180), color=(0, 0, 1))
    page.insert_text((60, 310), "Fig. 1. Synthetic ozone illustration; no measured result.", fontsize=10)
    page.insert_text((60, 380), "y = x + 1", fontsize=12)
    pdf = out / "synthetic.pdf"
    doc.save(pdf)
    doc.close()
    def block(kind, box, text=""):
        return {"type": kind, "bbox": box, "lines": [{"spans": [{"content": text}]}]}
    image = block("image", [60, 160, 300, 280])
    image["blocks"] = [block("image_body", [60, 160, 300, 280]), block("image_caption", [60, 295, 400, 315], "Fig. 1. Synthetic ozone illustration; no measured result.")]
    layout = {"_version_name": "authored_mock_not_mineru_inference", "pdf_info": [{"page_idx": 0, "page_size": [600, 800], "para_blocks": [block("title", [50, 40, 400, 65], "Synthetic materials document"), block("text", [50, 90, 560, 110], "Synthetic ozone example. Figure 1 is an authored diagram, not research data."), image, block("interline_equation", [60, 363, 180, 385], "y = x + 1")]}]}
    (out / "layout.json").write_text(json.dumps(layout, indent=2))
    (out / "glyph_library.json").write_text("[]\n")
    paper = {"id": "synthetic_001", "pages": 1, "staged": "synthetic.pdf", "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "layout": "layout.json", "glyph_library": "glyph_library.json"}
    (out / "manifest.json").write_text(json.dumps({"papers": [paper]}, indent=2))
    print("Created authored synthetic PDF and mock layout in", out)

if __name__ == "__main__":
    main()
