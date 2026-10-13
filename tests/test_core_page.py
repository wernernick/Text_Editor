import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import docx  # noqa: E402
import pytest  # noqa: E402

from core.document_model import Document, PageSetup  # noqa: E402
from core.docx_io import load_docx, save_docx  # noqa: E402


def test_defaults_are_a4_normal():
    page = Document.new().page
    assert page.paper_name == "A4" and page.orientation == "portrait"
    assert page.text_width_mm == 160


def test_orientation_paper_and_presets():
    page = PageSetup()
    page.set_orientation("landscape")
    assert (page.width_mm, page.height_mm) == (297, 210)
    page.set_paper("A5")
    assert (page.width_mm, page.height_mm) == (210, 148) and page.paper_name == "A5"
    page.apply_margin_preset("Schmal")
    assert page.margin_left_mm == 12.7
    with pytest.raises(ValueError):
        page.set_orientation("schräg")
    page.width_mm = 100
    assert page.paper_name is None


def test_page_setup_roundtrip(tmp_path):
    doc = Document.from_text("Quer")
    doc.page.set_paper("Letter")
    doc.page.set_orientation("landscape")
    doc.page.apply_margin_preset("Breit")
    path = str(tmp_path / "seite.docx")
    save_docx(doc, path)
    assert docx.Document(path).sections[0].orientation == docx.enum.section.WD_ORIENT.LANDSCAPE
    page = load_docx(path).page
    assert page.paper_name == "Letter" and page.orientation == "landscape"
    assert (page.margin_top_mm, page.margin_left_mm) == pytest.approx((25.4, 50.8), abs=0.1)
