import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.document_model import Document, Paragraph, Run  # noqa: E402
from core.docx_io import load_docx, save_docx  # noqa: E402
from core import file_manager  # noqa: E402


def test_new_document_has_one_empty_paragraph():
    doc = Document.new()
    assert len(doc.paragraphs) == 1
    assert doc.plain_text() == ""


def test_plain_text_and_counts():
    doc = Document.from_text("Hallo Welt\nZeile zwei")
    assert doc.plain_text() == "Hallo Welt\nZeile zwei"
    assert doc.word_count() == 4


def test_roundtrip_keeps_formatting(tmp_path):
    doc = Document(paragraphs=[
        Paragraph(runs=[Run("Titel")], style="Heading 1", alignment="center"),
        Paragraph(runs=[
            Run("fett ", bold=True),
            Run("kursiv ", italic=True),
            Run("unterstrichen", underline=True, font_family="Arial", font_size=14, color="#00FFCC"),
        ], alignment="justify"),
        Paragraph(runs=[]),
        Paragraph(runs=[Run("rechts")], alignment="right"),
    ])
    path = tmp_path / "out" / "test.docx"
    save_docx(doc, str(path))
    loaded = load_docx(str(path))

    assert loaded.plain_text() == doc.plain_text()
    assert loaded.path == str(path.resolve())
    assert loaded.paragraphs[0].style == "Heading 1"
    assert [p.alignment for p in loaded.paragraphs] == ["center", "justify", "left", "right"]
    runs = loaded.paragraphs[1].runs
    assert runs[0].bold and not runs[0].italic
    assert runs[1].italic and not runs[1].bold
    last = runs[2]
    assert last.underline and last.font_family == "Arial" and last.font_size == 14 and last.color == "#00FFCC"


def test_merge_runs():
    para = Paragraph(runs=[Run("a", bold=True), Run("b", bold=True), Run(""), Run("c")])
    para.merge_runs()
    assert [r.text for r in para.runs] == ["ab", "c"]


def test_recent_files_and_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXT_EDITOR_HOME", str(tmp_path / "home"))
    f1 = tmp_path / "a.docx"
    f2 = tmp_path / "b.docx"
    save_docx(Document.from_text("eins"), str(f1))
    save_docx(Document.from_text("zwei"), str(f2))
    file_manager.add_recent_file(str(f1))
    file_manager.add_recent_file(str(f2))
    file_manager.add_recent_file(str(f1))
    assert file_manager.get_recent_files() == [str(f1.resolve()), str(f2.resolve())]
    assert file_manager.autosave_path(str(f1)).name == "a.autosave.docx"
    backup = file_manager.backup_file(str(f1))
    assert backup is not None and backup.exists()
    assert file_manager.backup_file(str(tmp_path / "fehlt.docx")) is None
