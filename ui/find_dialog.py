"""Suchen-und-Ersetzen-Leiste (Strg+F / Strg+H) im Cyber-Stil."""
from __future__ import annotations

import customtkinter as ctk

from ui import theme

HIT_TAG = "find|hit"
CURRENT_TAG = "find|current"


class FindBar(ctk.CTkFrame):
    """Leiste oberhalb der Seite, wie der Navigationsbereich in Word."""

    def __init__(self, master, editor, on_status=None):
        super().__init__(master, fg_color=theme.BG_RIBBON, corner_radius=0)
        self.editor = editor
        self.text = editor.text
        self.on_status = on_status
        self.on_close = None
        self.matches: list[tuple[str, str]] = []
        self.current = -1

        self.text.tag_configure(HIT_TAG, background="#3a1240", foreground=theme.TEXT_PAGE)
        self.text.tag_configure(CURRENT_TAG, background=theme.ACCENT_2, foreground="#000000")

        entry_kw = dict(height=28, fg_color=theme.BG_BUTTON, border_color=theme.BORDER,
                        text_color=theme.TEXT, font=theme.ui_font(12))
        btn_kw = dict(height=28, corner_radius=4, font=theme.ui_font(12), fg_color=theme.BG_BUTTON,
                      hover_color=theme.BG_BUTTON_HOVER, text_color=theme.TEXT,
                      border_width=1, border_color=theme.BORDER)

        ctk.CTkLabel(self, text="⌕ SUCHEN", text_color=theme.ACCENT,
                     font=theme.ui_font(11, "bold")).grid(row=0, column=0, padx=(12, 6), pady=6)
        self.find_entry = ctk.CTkEntry(self, width=220, placeholder_text="Suchbegriff", **entry_kw)
        self.find_entry.grid(row=0, column=1, padx=3)
        ctk.CTkButton(self, text="▲", width=32, command=self.previous, **btn_kw).grid(row=0, column=2, padx=2)
        ctk.CTkButton(self, text="▼", width=32, command=self.next, **btn_kw).grid(row=0, column=3, padx=2)
        self.case_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Aa", variable=self.case_var, command=self.refresh, width=50,
                        checkbox_width=18, checkbox_height=18, fg_color=theme.ACCENT,
                        text_color=theme.TEXT, font=theme.ui_font(12)).grid(row=0, column=4, padx=6)
        self.count_label = ctk.CTkLabel(self, text="", width=110, text_color=theme.TEXT_MUTED,
                                        font=theme.ui_font(11))
        self.count_label.grid(row=0, column=5, padx=4)

        self.replace_label = ctk.CTkLabel(self, text="⇄ ERSETZEN", text_color=theme.ACCENT_2,
                                          font=theme.ui_font(11, "bold"))
        self.replace_entry = ctk.CTkEntry(self, width=180, placeholder_text="Ersetzen durch", **entry_kw)
        self.replace_btn = ctk.CTkButton(self, text="Ersetzen", width=80, command=self.replace_one, **btn_kw)
        self.replace_all_btn = ctk.CTkButton(self, text="Alle ersetzen", width=100,
                                             command=self.replace_all, **btn_kw)
        self.grid_columnconfigure(10, weight=1)
        ctk.CTkButton(self, text="✕", width=30, command=self.close, **btn_kw).grid(
            row=0, column=11, padx=(4, 12))

        self.find_entry.bind("<KeyRelease>", self._on_find_key)
        self.find_entry.bind("<Return>", lambda _e: self.next())
        self.find_entry.bind("<Shift-Return>", lambda _e: self.previous())
        self.find_entry.bind("<Escape>", lambda _e: self.close())
        self.replace_entry.bind("<Return>", lambda _e: self.replace_one())
        self.replace_entry.bind("<Escape>", lambda _e: self.close())
        self.visible = False

    # ------------------------------------------------------------ Anzeige
    def open(self, replace: bool = False) -> None:
        widgets = (self.replace_label, self.replace_entry, self.replace_btn, self.replace_all_btn)
        if replace:
            for col, w in enumerate(widgets, start=6):
                w.grid(row=0, column=col, padx=3)
        else:
            for w in widgets:
                w.grid_remove()
        self.visible = True
        if self.editor.has_selection():
            selected = self.text.get("sel.first", "sel.last")
            if selected and "\n" not in selected:
                self.find_entry.delete(0, "end")
                self.find_entry.insert(0, selected)
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")
        self.refresh()

    def close(self) -> None:
        self.visible = False
        self.text.tag_remove(HIT_TAG, "1.0", "end")
        self.text.tag_remove(CURRENT_TAG, "1.0", "end")
        self.matches = []
        self.current = -1
        if self.on_close:
            self.on_close()
        self.text.focus_set()

    # ------------------------------------------------------------- Suche
    def _on_find_key(self, event) -> None:
        if event.keysym not in ("Return", "Escape", "Shift_L", "Shift_R"):
            self.refresh()

    def refresh(self) -> None:
        """Alle Treffer neu suchen und markieren."""
        self.text.tag_remove(HIT_TAG, "1.0", "end")
        self.text.tag_remove(CURRENT_TAG, "1.0", "end")
        self.matches = []
        needle = self.find_entry.get()
        if needle:
            count = ctk.IntVar(master=self)
            idx = "1.0"
            nocase = not self.case_var.get()
            while True:
                idx = self.text.search(needle, idx, stopindex="end", nocase=nocase, count=count)
                if not idx or count.get() == 0:
                    break
                end = f"{idx} +{count.get()}c"
                self.matches.append((idx, self.text.index(end)))
                self.text.tag_add(HIT_TAG, idx, end)
                idx = end
        self.text.tag_raise(HIT_TAG)
        self.text.tag_raise(CURRENT_TAG)
        # aktuellen Treffer an der Cursorposition wählen
        self.current = -1
        for i, (start, _end) in enumerate(self.matches):
            if self.text.compare(start, ">=", "insert"):
                self.current = i
                break
        if self.matches and self.current == -1:
            self.current = 0
        self._show_current()

    def _show_current(self) -> None:
        self.text.tag_remove(CURRENT_TAG, "1.0", "end")
        if not self.matches:
            text = "Keine Treffer" if self.find_entry.get() else ""
            self.count_label.configure(text=text, text_color=theme.ACCENT_2 if text else theme.TEXT_MUTED)
            return
        start, end = self.matches[self.current]
        self.text.tag_add(CURRENT_TAG, start, end)
        self.text.see(start)
        self.count_label.configure(text=f"{self.current + 1} von {len(self.matches)}",
                                   text_color=theme.ACCENT_3)

    def next(self) -> None:
        if not self.matches:
            self.refresh()
            return
        self.current = (self.current + 1) % len(self.matches)
        self._show_current()

    def previous(self) -> None:
        if not self.matches:
            self.refresh()
            return
        self.current = (self.current - 1) % len(self.matches)
        self._show_current()

    # ---------------------------------------------------------- Ersetzen
    def replace_one(self) -> None:
        if not self.matches:
            self.refresh()
            if not self.matches:
                return
        start, end = self.matches[self.current]
        self.text.edit_separator()
        self.editor.replace_range(start, end, self.replace_entry.get())
        self.text.mark_set("insert", f"{start} +{len(self.replace_entry.get())}c")
        self.refresh()

    def replace_all(self) -> int:
        self.refresh()
        replacement = self.replace_entry.get()
        count = len(self.matches)
        self.text.edit_separator()
        for start, end in reversed(self.matches):
            self.editor.replace_range(start, end, replacement)
        self.text.edit_separator()
        self.refresh()
        if self.on_status:
            self.on_status(f"{count} ERSETZT")
        return count
