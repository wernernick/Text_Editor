import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from core import autosave  # noqa: E402
from core.document_model import Document  # noqa: E402
from core.docx_io import save_docx  # noqa: E402


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXT_EDITOR_HOME", str(tmp_path / "home"))


def test_autosave_and_recover_saved_document(tmp_path):
    original = tmp_path / "brief.docx"
    doc = Document.from_text("Version 1")
    save_docx(doc, str(original))
    doc.paragraphs[0].runs[0].text = "Version 2 ungespeichert"
    autosave.autosave(doc)
    assert doc.path == str(original.resolve())

    entries = autosave.list_recoverable()
    assert len(entries) == 1 and entries[0].original_path == str(original.resolve())
    assert "brief.docx" in entries[0].display_name
    restored = autosave.recover(entries[0])
    assert restored.plain_text() == "Version 2 ungespeichert"
    assert restored.path == str(original.resolve())

    autosave.discard(doc.path)
    assert autosave.list_recoverable() == []


def test_autosave_untitled_document():
    doc = Document.from_text("Notiz")
    autosave.autosave(doc)
    assert doc.path is None
    entry = autosave.list_recoverable()[0]
    assert entry.original_path is None
    assert autosave.recover(entry).path is None
    autosave.discard(None)
    autosave.discard(None)  # zweimal ist kein Fehler
    assert autosave.list_recoverable() == []


def test_is_due():
    assert autosave.is_due(0, 120, now=120)
    assert not autosave.is_due(100, 120, now=150)


def test_atomic_save_leaves_no_temp_files(tmp_path):
    save_docx(Document.from_text("x"), str(tmp_path / "a.docx"))
    save_docx(Document.from_text("y"), str(tmp_path / "a.docx"))
    assert [name for name in os.listdir(tmp_path) if name.startswith(".~")] == []
