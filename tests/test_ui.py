"""UI-Tests: Konvertierung Text-Widget <-> Document und DOCX-Rundreise.

Braucht ein Display (unter Linux z.B. `xvfb-run python -m pytest`); ohne Display wird übersprungen.
"""
import os
import tempfile
import unittest

# App-Daten (zuletzt geöffnet, Autosave, Backups) der Tests nicht ins echte Home schreiben
os.environ["TEXT_EDITOR_HOME"] = tempfile.mkdtemp(prefix="text_editor_test_")

try:
    from ui.app import TextEditorApp
    _app = TextEditorApp()
    _app.withdraw()
    _app.destroy()
    HAS_DISPLAY = True
except Exception:  # noqa: BLE001 - kein Display / kein tkinter
    HAS_DISPLAY = False

from core.document_model import Document, Paragraph, Run


def _create_app(attempts: int = 3):
    """Tk-Fenster anlegen; auf Windows-CI schlägt Tk() gelegentlich beim Lesen von init.tcl fehl."""
    import time
    import tkinter

    for attempt in range(attempts):
        try:
            return TextEditorApp()
        except tkinter.TclError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5)


@unittest.skipUnless(HAS_DISPLAY, "kein Display für Tk verfügbar")
class EditorConversionTest(unittest.TestCase):
    def setUp(self):
        self.app = _create_app()
        self.app.withdraw()
        self.editor = self.app.editor

    def tearDown(self):
        self.app.dirty = False
        self.app.destroy()

    def _sample(self):
        return Document(paragraphs=[
            Paragraph(runs=[Run("Titel")], style="Heading 1", alignment="center"),
            Paragraph(runs=[Run("Hallo "), Run("fett", bold=True), Run(" und "),
                            Run("bunt", italic=True, color="#ff2bd6", font_size=14, font_family="Arial")]),
            Paragraph(runs=[]),
            Paragraph(runs=[Run("Ende", underline=True)], alignment="right"),
        ])

    def test_roundtrip_model(self):
        self.editor.load_document(self._sample())
        doc = self.app.build_document()
        self.assertEqual(doc.plain_text(), "Titel\nHallo fett und bunt\n\nEnde")
        self.assertEqual(doc.paragraphs[0].style, "Heading 1")
        self.assertEqual(doc.paragraphs[0].alignment, "center")
        self.assertEqual(doc.paragraphs[3].alignment, "right")
        runs = doc.paragraphs[1].runs
        self.assertEqual([r.text for r in runs], ["Hallo ", "fett", " und ", "bunt"])
        self.assertTrue(runs[1].bold)
        self.assertEqual((runs[3].italic, runs[3].color, runs[3].font_size, runs[3].font_family),
                         (True, "#ff2bd6", 14, "Arial"))
        self.assertTrue(doc.paragraphs[3].runs[0].underline)

    def test_toggle_bold_on_selection(self):
        self.editor.load_document(Document.from_text("abc def"))
        self.editor.text.tag_add("sel", "1.0", "1.3")
        self.editor.toggle("bold")
        runs = self.app.build_document().paragraphs[0].runs
        self.assertEqual([(r.text, r.bold) for r in runs], [("abc", True), (" def", False)])
        # erneut umschalten -> wieder normal und zusammengefasst
        self.editor.toggle("bold")
        runs = self.app.build_document().paragraphs[0].runs
        self.assertEqual([(r.text, r.bold) for r in runs], [("abc def", False)])

    def test_typing_uses_typing_format(self):
        self.editor.clear()
        self.editor.apply_format(italic=True)
        self.editor.text.insert("insert", "kursiv")
        runs = self.app.build_document().paragraphs[0].runs
        self.assertEqual([(r.text, r.italic) for r in runs], [("kursiv", True)])
        self.assertEqual(self.editor.stats(), (1, 6))

    def test_alignment_and_style(self):
        self.editor.load_document(Document.from_text("eins\nzwei"))
        self.editor.text.mark_set("insert", "2.1")
        self.editor.set_alignment("justify")
        self.editor.set_style("Heading 2")
        doc = self.app.build_document()
        self.assertEqual((doc.paragraphs[0].alignment, doc.paragraphs[0].style), ("left", "Normal"))
        self.assertEqual((doc.paragraphs[1].alignment, doc.paragraphs[1].style), ("justify", "Heading 2"))

    def test_docx_roundtrip(self):
        self.editor.load_document(self._sample())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.docx")
            self.assertTrue(self.app._write(path))
            self.app.new_document()
            self.assertTrue(self.app.load_path(path))
        doc = self.app.build_document()
        self.assertEqual(doc.plain_text(), "Titel\nHallo fett und bunt\n\nEnde")
        self.assertTrue(doc.paragraphs[1].runs[1].bold)
        self.assertEqual(doc.paragraphs[0].style, "Heading 1")

    def test_return_after_heading_is_normal(self):
        self.editor.load_document(Document(paragraphs=[Paragraph([Run("Kopf")], style="Heading 1")]))
        self.editor.text.mark_set("insert", "1.end")
        self.editor.text.insert("insert", "\n")
        self.editor._after_return()
        self.editor.text.insert("insert", "Text")
        doc = self.app.build_document()
        self.assertEqual([p.style for p in doc.paragraphs], ["Heading 1", "Normal"])

    def test_find_and_replace(self):
        self.editor.load_document(Document(paragraphs=[
            Paragraph([Run("Neon "), Run("neon", bold=True), Run(" NEON")])]))
        self.app.show_find(replace=True)
        bar = self.app.find_bar
        bar.find_entry.insert(0, "neon")
        bar.refresh()
        self.assertEqual(len(bar.matches), 3)
        bar.case_var.set(True)
        bar.refresh()
        self.assertEqual(len(bar.matches), 1)
        bar.case_var.set(False)
        bar.replace_entry.insert(0, "Cyber")
        self.assertEqual(bar.replace_all(), 3)
        doc = self.app.build_document()
        self.assertEqual(doc.plain_text(), "Cyber Cyber Cyber")
        # Formatierung des ersetzten Wortes bleibt erhalten
        self.assertEqual([(r.text, r.bold) for r in doc.paragraphs[0].runs],
                         [("Cyber ", False), ("Cyber", True), (" Cyber", False)])
        bar.close()
        self.assertEqual(self.editor.text.tag_ranges("find|hit"), ())

    def test_lists(self):
        self.editor.load_document(Document.from_text("a\nb\nc\nd"))
        self.editor.text.tag_add("sel", "1.0", "2.1")
        self.app._toggle_list("List Number")
        self.editor.text.tag_remove("sel", "1.0", "end")
        self.editor.text.mark_set("insert", "4.0")
        self.app._toggle_list("List Bullet")
        self.assertEqual(self.editor.list_markers(), [(1, "1."), (2, "2."), (4, "◆")])
        doc = self.app.build_document()
        self.assertEqual([p.list_type for p in doc.paragraphs], ["number", "number", None, "bullet"])
        self.assertEqual([p.style for p in doc.paragraphs], ["Normal"] * 4)
        # nochmal umschalten -> Liste aus
        self.app._toggle_list("List Bullet")
        self.assertIsNone(self.app.build_document().paragraphs[3].list_type)
        # Enter in Listenpunkt setzt die Liste fort, Enter auf leerem Punkt beendet sie
        self.editor.text.mark_set("insert", "2.end")
        self.editor.text.insert("insert", "\n")
        self.editor._after_return()
        self.assertEqual(self.editor.list_markers()[-1], (3, "3."))
        self.editor.text.insert("insert", "\n")
        self.editor._after_return()
        doc = self.app.build_document()
        self.assertEqual(doc.plain_text(), "a\nb\n\nc\nd")
        self.assertIsNone(doc.paragraphs[2].list_type)

    def test_lists_docx_roundtrip(self):
        self.editor.load_document(Document(paragraphs=[
            Paragraph([Run("Punkt")], list_type="bullet"),
            Paragraph([Run("Eins")], list_type="number")]))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.docx")
            self.assertTrue(self.app._write(path))
            self.assertTrue(self.app.load_path(path))
        self.assertEqual([p.list_type for p in self.app.build_document().paragraphs],
                         ["bullet", "number"])
        self.assertEqual(self.editor.list_markers(), [(1, "◆"), (2, "1.")])

    def test_recent_backup_and_autosave(self):
        from core.file_manager import app_dir, autosave_path
        self.editor.load_document(Document.from_text("eins"))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.docx")
            self.assertTrue(self.app._write(path))
            self.assertEqual(self.app.recent_files()[0], os.path.abspath(path))
            self.editor.text.insert("end", " zwei")
            self.assertTrue(self.app._write(path))  # zweites Speichern legt Backup an
            self.assertTrue(list((app_dir() / "backups").glob("r.*.docx")))
            self.editor.text.insert("end", " drei")
            self.app.update()  # <<Modified>> kommt asynchron
            self.assertTrue(self.app.dirty)
            self.app._autosave()
            self.assertTrue(autosave_path(path).exists())
            self.assertTrue(self.app.dirty)  # Autosave ersetzt kein echtes Speichern

    def test_page_mode(self):
        self.editor.load_document(Document(paragraphs=[Paragraph([Run("K")], style="Heading 1")]))
        self.app.ribbon.page_mode.set("Papier")
        self.app._actions()["page_mode"]("Papier")
        self.assertEqual(self.editor.text.cget("bg"), "#fbfcff")
        self.assertEqual(self.editor.text.tag_cget("style|Heading 1", "foreground"), "#0086a8")
        self.app._actions()["page_mode"]("Neon")
        self.assertEqual(self.editor.text.cget("bg"), "#0b1018")

    def test_font_step_and_clear_format(self):
        self.editor.load_document(Document(paragraphs=[
            Paragraph([Run("ab", bold=True, font_size=11), Run("cd", font_size=20)], style="Heading 1")]))
        self.editor.text.tag_add("sel", "1.0", "1.4")
        self.app._font_step(1)
        runs = self.app.build_document().paragraphs[0].runs
        self.assertEqual([r.font_size for r in runs], [12, 24])
        self.app._font_step(-1)
        self.app._font_step(-1)
        runs = self.app.build_document().paragraphs[0].runs
        self.assertEqual([r.font_size for r in runs], [10, 18])
        self.app._clear_format()
        para = self.app.build_document().paragraphs[0]
        self.assertEqual([(r.text, r.bold, r.font_size) for r in para.runs], [("abcd", False, 11)])
        self.assertEqual(para.style, "Normal")

    def test_change_case_keeps_formatting(self):
        self.editor.load_document(Document(paragraphs=[
            Paragraph([Run("hallo "), Run("neon", bold=True), Run("welt straße")])]))
        self.editor.text.tag_add("sel", "1.0", "1.end")
        self.app._change_case("title")
        runs = self.app.build_document().paragraphs[0].runs
        self.assertEqual([(r.text, r.bold) for r in runs],
                         [("Hallo ", False), ("Neonwelt"[:4], True), ("welt Straße", False)])
        self.app._change_case("upper")  # "ß" -> "SS" ändert die Länge
        doc = self.app.build_document()
        self.assertEqual(doc.plain_text(), "HALLO NEONWELT STRASSE")
        self.assertTrue(doc.paragraphs[0].runs[1].bold)
        self.app._change_case("cycle")  # GROSS -> Titel
        self.assertEqual(self.app.build_document().plain_text(), "Hallo Neonwelt Strasse")

    def test_context_menu_and_clipboard(self):
        self.editor.load_document(Document.from_text("kopier mich"))
        menu = self.app.build_context_menu()
        self.assertEqual(menu.entrycget(0, "state"), "disabled")  # Ausschneiden ohne Auswahl
        self.editor.text.tag_add("sel", "1.0", "1.6")
        menu = self.app.build_context_menu()
        self.assertEqual(menu.entrycget(0, "state"), "normal")
        self.app._clipboard("<<Copy>>")
        self.assertEqual(self.app.clipboard_get(), "kopier")
        self.editor.text.tag_remove("sel", "1.0", "end")
        self.editor.text.mark_set("insert", "1.end")
        self.app._clipboard("<<Paste>>")
        self.assertEqual(self.editor.get_plain_text(), "kopier michkopier")
        self.app._undo()
        self.assertEqual(self.editor.get_plain_text(), "kopier mich")

    def test_zoom(self):
        self.app._zoom_step(1)
        self.assertEqual(self.editor.zoom, 110)
        self.app._set_zoom(100)
        self.assertEqual(self.editor.zoom, 100)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAS_DISPLAY, "kein Display für Tk verfügbar")
class AutosaveWiringTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("TEXT_EDITOR_HOME")
        os.environ["TEXT_EDITOR_HOME"] = self._tmp.name
        self.app = _create_app()
        self.app.withdraw()

    def tearDown(self):
        self.app.dirty = False
        self.app.destroy()
        if self._old_home is None:
            os.environ.pop("TEXT_EDITOR_HOME", None)
        else:
            os.environ["TEXT_EDITOR_HOME"] = self._old_home
        self._tmp.cleanup()

    def test_autosave_is_recoverable_and_removed_after_save(self):
        from core import autosave
        self.app.editor.load_document(Document.from_text("Ungespeichert"))
        self.app.dirty = True
        self.app._autosave()
        entries = autosave.list_recoverable()
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0].original_path)
        self.assertEqual(autosave.recover(entries[0]).plain_text(), "Ungespeichert")

        self.assertTrue(self.app._write(os.path.join(self._tmp.name, "doc.docx")))
        self.assertEqual(autosave.list_recoverable(), [])
