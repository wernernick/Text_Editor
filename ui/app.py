"""Hauptfenster: Ribbon, Dokumentseite und Statusleiste."""
from __future__ import annotations

import datetime
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk

from ui import theme
from ui.editor import ALIGN_PREFIX, STYLE_PREFIX, DocumentEditor
from ui.find_dialog import FindBar
from ui.ribbon import Ribbon

APP_NAME = "NEON//WRITE"
AUTOSAVE_MS = 60_000
FILE_TYPES = [("Word-Dokument", "*.docx"), ("Alle Dateien", "*.*")]


class StatusBar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=theme.BG_STATUS, corner_radius=0, height=26)
        ctk.CTkFrame(self, fg_color=theme.BORDER, height=1, corner_radius=0).pack(side="top", fill="x")
        self.left = ctk.CTkLabel(self, text="", font=theme.ui_font(11), text_color=theme.TEXT_MUTED)
        self.left.pack(side="left", padx=12)
        self.state = ctk.CTkLabel(self, text="● BEREIT", font=theme.ui_font(11, "bold"),
                                  text_color=theme.ACCENT_3)
        self.state.pack(side="right", padx=12)
        self.right = ctk.CTkLabel(self, text="", font=theme.ui_font(11), text_color=theme.TEXT_MUTED)
        self.right.pack(side="right", padx=12)

    def update_info(self, words: int, chars: int, line: int, col: int, zoom: int) -> None:
        self.left.configure(text=f"Wörter: {words}   Zeichen: {chars}")
        self.right.configure(text=f"Zeile {line}, Spalte {col}   |   {zoom} %")

    def set_state(self, text: str, ok: bool = True) -> None:
        self.state.configure(text=f"● {text}", text_color=theme.ACCENT_3 if ok else theme.ACCENT_2)


class TextEditorApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=theme.BG_APP)
        self.geometry("1200x780")
        self.minsize(820, 520)
        self.path: str | None = None
        self.dirty = False

        self.ribbon = Ribbon(self, self._actions())
        self.ribbon.pack(side="top", fill="x")
        self.status = StatusBar(self)
        self.status.pack(side="bottom", fill="x")
        self.editor = DocumentEditor(self, on_change=self._on_change, on_cursor=self._refresh_ui)
        self.editor.pack(side="top", fill="both", expand=True)
        self.find_bar = FindBar(self, self.editor, on_status=self.status.set_state)
        self.find_bar.on_close = self.find_bar.pack_forget

        self._bind_shortcuts()
        self._autosave_job = self.after(AUTOSAVE_MS, self._autosave)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_title()
        self._refresh_ui()
        self.editor.text.focus_set()

    # ---------------------------------------------------------- Aktionen
    def _actions(self) -> dict:
        return {
            "new": self.new_document, "open": self.open_document, "recent": self.show_recent_menu,
            "save": self.save_document, "save_as": self.save_document_as,
            "toggle": self._toggle, "font_family": self._set_font_family,
            "font_size": self._set_font_size, "color": self._choose_color,
            "align": self._set_alignment, "style": self._set_style,
            "insert_date": lambda: self._insert(datetime.date.today().strftime("%d.%m.%Y")),
            "insert_time": lambda: self._insert(datetime.datetime.now().strftime("%H:%M")),
            "insert_line": lambda: self._insert("\n" + "─" * 40 + "\n"),
            "insert_text": self._insert,
            "zoom_step": self._zoom_step, "zoom_reset": lambda: self._set_zoom(100),
            "list_bullet": lambda: self._toggle_list("List Bullet"),
            "list_number": lambda: self._toggle_list("List Number"),
            "find": lambda: self.show_find(False), "replace": lambda: self.show_find(True),
            "page_mode": lambda label: self.editor.set_page_mode("paper" if label == "Papier" else "neon"),
            "toggle_wrap": self._toggle_wrap, "toggle_status": self._toggle_status,
        }

    def _bind_shortcuts(self) -> None:
        bindings = {
            "n": self.new_document, "o": self.open_document, "s": self.save_document,
            "b": lambda: self._toggle("bold"), "i": lambda: self._toggle("italic"),
            "u": lambda: self._toggle("underline"),
            "e": lambda: self._set_alignment("center"), "l": lambda: self._set_alignment("left"),
            "r": lambda: self._set_alignment("right"), "j": lambda: self._set_alignment("justify"),
            "f": lambda: self.show_find(False), "h": lambda: self.show_find(True),
            "plus": lambda: self._zoom_step(1), "minus": lambda: self._zoom_step(-1),
        }
        for key, func in bindings.items():
            seq = f"<Control-{key}>"
            self.editor.text.bind(seq, lambda _e, f=func: (f(), "break")[1])
            self.bind(seq, lambda _e, f=func: f())
        self.editor.text.bind("<Control-Shift-S>", lambda _e: (self.save_document_as(), "break")[1])
        self.editor.text.bind("<Control-Shift-L>", lambda _e: (self._toggle_list("List Bullet"), "break")[1])
        self.editor.text.bind("<Control-y>", lambda _e: (self._redo(), "break")[1])
        for i, style in enumerate(("Heading 1", "Heading 2", "Heading 3"), start=1):
            self.editor.text.bind(f"<Control-Alt-Key-{i}>", lambda _e, s=style: (self._set_style(s), "break")[1])

    def show_find(self, replace: bool = False) -> None:
        if not self.find_bar.winfo_ismapped():
            self.find_bar.pack(side="top", fill="x", before=self.editor)
        self.find_bar.open(replace)

    def _toggle_list(self, style: str) -> None:
        self.editor.toggle_list(style)
        self._refresh_ui()
        self.editor.text.focus_set()

    def _toggle(self, attr: str) -> None:
        self.editor.toggle(attr)
        self._refresh_ui()

    def _set_font_family(self, family: str) -> None:
        if family:
            self.editor.apply_format(font_family=family)
            self._refresh_ui()
        self.editor.text.focus_set()

    def _set_font_size(self, value) -> None:
        try:
            size = int(float(str(value).replace(",", ".")))
        except ValueError:
            return
        if 1 <= size <= 400:
            self.editor.apply_format(font_size=size)
            self._refresh_ui()
        self.editor.text.focus_set()

    def _choose_color(self) -> None:
        initial = self.editor.current_format().color or theme.TEXT_PAGE
        result = colorchooser.askcolor(color=initial, title="Schriftfarbe", parent=self)
        if result and result[1]:
            self.editor.apply_format(color=result[1].lower())
            self._refresh_ui()

    def _set_alignment(self, alignment: str) -> None:
        self.editor.set_alignment(alignment)
        self._refresh_ui()

    def _set_style(self, style: str) -> None:
        self.editor.set_style(style)
        self._refresh_ui()
        self.editor.text.focus_set()

    def _insert(self, text: str) -> None:
        self.editor.insert_plain(text)
        self.editor.text.focus_set()

    def _redo(self) -> None:
        try:
            self.editor.text.edit_redo()
        except tk.TclError:
            pass

    def _set_zoom(self, zoom: int) -> None:
        self.editor.set_zoom(zoom)
        self.ribbon.zoom_label.configure(text=f"{zoom} %")
        self._refresh_ui()

    def _zoom_step(self, direction: int) -> None:
        levels = theme.ZOOM_LEVELS
        current = self.editor.zoom
        if direction > 0:
            nxt = next((z for z in levels if z > current), levels[-1])
        else:
            nxt = next((z for z in reversed(levels) if z < current), levels[0])
        self._set_zoom(nxt)

    def _toggle_wrap(self) -> None:
        self.editor.text.configure(wrap="word" if self.ribbon.wrap_switch.get() else "none")

    def _toggle_status(self) -> None:
        if self.ribbon.status_switch.get():
            self.status.pack(side="bottom", fill="x", before=self.editor)
        else:
            self.status.pack_forget()

    # ---------------------------------------------------------- Zustand
    def _on_change(self) -> None:
        if not self.dirty:
            self.dirty = True
            self._update_title()

    def _refresh_ui(self) -> None:
        fmt = self.editor.current_format()
        alignment = self.editor.paragraph_value(ALIGN_PREFIX, default="left")
        style = self.editor.paragraph_value(STYLE_PREFIX, default="Normal")
        self.ribbon.update_state(fmt, alignment, style)
        words, chars = self.editor.stats()
        line, col = self.editor.cursor_position()
        self.status.update_info(words, chars, line, col, self.editor.zoom)

    def _update_title(self) -> None:
        name = os.path.basename(self.path) if self.path else "Unbenannt"
        self.title(f"{'● ' if self.dirty else ''}{name} – {APP_NAME}")

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(
            APP_NAME, "Änderungen am Dokument speichern?", parent=self)
        if answer is None:
            return False
        if answer:
            return self.save_document()
        return True

    # ---------------------------------------------------------- Datei
    def new_document(self) -> None:
        if not self._confirm_discard():
            return
        self.editor.clear()
        self.path = None
        self.dirty = False
        self._update_title()
        self._refresh_ui()
        self.status.set_state("NEUES DOKUMENT")

    def open_document(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self, filetypes=FILE_TYPES)
        if path:
            self.load_path(path)

    def load_path(self, path: str) -> bool:
        try:
            from core.docx_io import load_docx  # spät importiert: main.py startet auch ohne Core
            document = load_docx(path)
        except Exception as exc:  # noqa: BLE001 - Fehler dem Nutzer zeigen statt abstürzen
            messagebox.showerror(APP_NAME, f"Datei konnte nicht geöffnet werden:\n{exc}", parent=self)
            self.status.set_state("FEHLER BEIM ÖFFNEN", ok=False)
            return False
        self.editor.load_document(document)
        self.path = path
        self.dirty = False
        self._update_title()
        self._refresh_ui()
        self.status.set_state("GEÖFFNET")
        self._remember(path)
        return True

    def _remember(self, path: str) -> None:
        try:
            from core.file_manager import add_recent_file
            add_recent_file(path)
        except Exception:  # noqa: BLE001 - Liste ist Komfort, darf nie stören
            pass

    def recent_files(self) -> list[str]:
        try:
            from core.file_manager import get_recent_files
            return get_recent_files()
        except Exception:  # noqa: BLE001
            return []

    def show_recent_menu(self, anchor=None) -> None:
        menu = tk.Menu(self, tearoff=0, bg=theme.BG_RIBBON, fg=theme.TEXT, activebackground=theme.BG_BUTTON_HOVER,
                       activeforeground=theme.ACCENT, borderwidth=1, relief="solid",
                       font=theme.ui_font(11))
        files = self.recent_files()
        if not files:
            menu.add_command(label="Keine zuletzt geöffneten Dateien", state="disabled")
        for path in files:
            menu.add_command(label=f"{os.path.basename(path)}   —   {os.path.dirname(path)}",
                             command=lambda p=path: self._open_recent(p))
        widget = anchor or self.ribbon
        menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def _open_recent(self, path: str) -> None:
        if self._confirm_discard():
            self.load_path(path)

    def _autosave(self) -> None:
        """Sichert ungespeicherte Änderungen regelmäßig in den Autosave-Ordner (Originaldatei bleibt unberührt)."""
        self._autosave_job = self.after(AUTOSAVE_MS, self._autosave)
        if not self.dirty:
            return
        try:
            from core.autosave import autosave
            document = self.build_document()
            document.path = self.path
            autosave(document)  # schreibt auch die Metadaten für die Wiederherstellung
        except Exception:  # noqa: BLE001 - Autosave darf die Arbeit nie unterbrechen
            self.status.set_state("AUTOSAVE FEHLGESCHLAGEN", ok=False)
            return
        self.status.set_state("AUTOGESICHERT " + datetime.datetime.now().strftime("%H:%M"))

    def save_document(self) -> bool:
        if not self.path:
            return self.save_document_as()
        return self._write(self.path)

    def save_document_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".docx", filetypes=FILE_TYPES,
            initialfile=os.path.basename(self.path) if self.path else "Dokument.docx")
        if not path:
            return False
        return self._write(path)

    def build_document(self):
        from core.document_model import Document, Paragraph, Run
        return self.editor.to_document(Document, Paragraph, Run)

    def _write(self, path: str) -> bool:
        try:
            from core.docx_io import save_docx
            from core.file_manager import backup_file
            document = self.build_document()
            document.path = path
            backup_file(path)  # vorherige Fassung sichern, bevor sie überschrieben wird
            save_docx(document, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"Datei konnte nicht gespeichert werden:\n{exc}", parent=self)
            self.status.set_state("FEHLER BEIM SPEICHERN", ok=False)
            return False
        self._drop_autosave(self.path)
        self._drop_autosave(path)
        self.path = path
        self.dirty = False
        self._update_title()
        self.status.set_state("GESPEICHERT")
        self._remember(path)
        return True

    def _drop_autosave(self, path: str | None) -> None:
        """Sicherung entfernen, sobald der Stand gespeichert oder bewusst verworfen wurde."""
        try:
            from core.autosave import discard
            discard(path)
        except Exception:  # noqa: BLE001
            pass

    def on_close(self) -> None:
        if self._confirm_discard():
            self._drop_autosave(self.path)
            self.destroy()

    def destroy(self) -> None:
        if getattr(self, "_autosave_job", None):
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
        super().destroy()


def run(argv: list[str] | None = None) -> None:
    app = TextEditorApp()
    # Datei aus der Kommandozeile öffnen (z.B. "Öffnen mit" auf die .exe)
    args = [a for a in (argv or []) if a.lower().endswith(".docx") and os.path.isfile(a)]
    if args:
        app.after(50, lambda: app.load_path(args[0]))
    # Für automatisierte Starttests: Fenster nach N Millisekunden schließen.
    autoclose = os.environ.get("TEXT_EDITOR_AUTOCLOSE_MS")
    if autoclose and autoclose.isdigit():
        app.after(int(autoclose), app.destroy)
    app.mainloop()
