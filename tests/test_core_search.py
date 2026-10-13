import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.document_model import Document, Paragraph, Run  # noqa: E402
from core.search import find_all, find_next, is_valid_pattern, replace, replace_all  # noqa: E402


def _doc():
    return Document(paragraphs=[
        Paragraph(runs=[Run("Hallo "), Run("Welt", bold=True), Run(", welt!")]),
        Paragraph(runs=[Run("Weltraum und Welt")]),
    ])


def test_find_case_and_whole_word():
    doc = _doc()
    assert len(find_all(doc, "welt")) == 4
    assert len(find_all(doc, "welt", match_case=True)) == 1
    hits = find_all(doc, "Welt", whole_word=True)
    assert [(m.paragraph, m.start) for m in hits] == [(0, 6), (0, 12), (1, 13)]
    assert find_all(doc, "") == []


def test_find_next_wraps_and_backwards():
    doc = _doc()
    m = find_next(doc, "welt", paragraph=1, offset=1)
    assert (m.paragraph, m.start) == (1, 13)
    m = find_next(doc, "welt", paragraph=1, offset=14)
    assert (m.paragraph, m.start) == (0, 6)
    assert find_next(doc, "welt", paragraph=1, offset=14, wrap=False) is None
    m = find_next(doc, "welt", paragraph=1, offset=0, backwards=True)
    assert (m.paragraph, m.start) == (0, 12)


def test_replace_keeps_formatting_across_runs():
    doc = _doc()
    match = find_all(doc, "lo Wel")[0]
    replace(doc, match, "XY")
    para = doc.paragraphs[0]
    assert para.text == "HalXYt, welt!"
    assert [(r.text, r.bold) for r in para.runs] == [("HalXY", False), ("t", True), (", welt!", False)]


def test_replace_all_and_regex_groups():
    doc = _doc()
    assert replace_all(doc, "welt", "Erde", whole_word=True) == 3
    assert doc.plain_text() == "Hallo Erde, Erde!\nWeltraum und Erde"
    assert doc.paragraphs[0].runs[1].bold and doc.paragraphs[0].runs[1].text == "Erde"
    assert replace_all(doc, r"(\w+) und (\w+)", r"\2 & \1", regex=True) == 1
    assert doc.paragraphs[1].text == "Erde & Weltraum"


def test_invalid_regex_is_safe():
    doc = _doc()
    assert not is_valid_pattern("(", regex=True)
    assert is_valid_pattern("(", regex=False)
    assert find_all(doc, "(", regex=True) == []
    assert replace_all(doc, "(", "x", regex=True) == 0
