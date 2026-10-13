"""Tabellen als eingebettete Widgets in der Textfläche (ein Tabellenblock = eine Zeile)."""
from __future__ import annotations

import tkinter as tk

from ui import theme

PARA_MARK = " ¶ "  # Zeilenumbruch innerhalb einer Zelle in der einzeiligen Anzeige


class TableWidget(tk.Frame):
    """Raster aus Eingabefeldern. Unveränderte Zellen behalten ihre Originalformatierung."""

    def __init__(self, master, table, palette: dict, zoom: int = 100, on_focus=None, on_change=None):
        super().__init__(master, borderwidth=0, highlightthickness=0)
        self.palette = palette
        self.zoom = zoom
        self.on_focus = on_focus
        self.on_change = on_change
        self.header_row = bool(getattr(table, "header_row", False))
        self.cells: list[list[tk.Entry]] = []
        self.originals: list[list[tuple[object, str]]] = []  # (TableCell, angezeigter Text)
        for row in getattr(table, "rows", []):
            self._add_row([(cell, _cell_text(cell)) for cell in row])
        self.apply_palette(palette)

    # ------------------------------------------------------------ Aufbau
    def _make_entry(self, text: str) -> tk.Entry:
        entry = tk.Entry(self, relief="flat", borderwidth=0, highlightthickness=1)
        entry.insert(0, text)
        entry.bind("<FocusIn>", lambda _e: self.on_focus and self.on_focus(self))
        entry.bind("<KeyRelease>", lambda _e: self.on_change and self.on_change())
        entry.bind("<Tab>", self._next_cell)
        for seq in ("<Shift-Tab>", "<ISO_Left_Tab>"):  # Windows / Linux
            try:
                entry.bind(seq, lambda e: self._next_cell(e, -1))
            except tk.TclError:
                pass
        return entry

    def _add_row(self, cells: list[tuple[object, str]], index: int | None = None) -> None:
        index = len(self.cells) if index is None else index
        self.cells.insert(index, [self._make_entry(text) for _cell, text in cells])
        self.originals.insert(index, list(cells))
        self._regrid()

    def _regrid(self) -> None:
        for r, row in enumerate(self.cells):
            for c, entry in enumerate(row):
                entry.grid(row=r, column=c, padx=1, pady=1, sticky="nsew", ipady=3)
        self.apply_palette(self.palette)

    def _next_cell(self, event, step: int = 1) -> str:
        """Tab springt wie in Word zur nächsten Zelle; in der letzten Zelle kommt eine Zeile dazu."""
        flat = [e for row in self.cells for e in row]
        idx = flat.index(event.widget) + step
        if idx >= len(flat):
            self.insert_row()
            flat = [e for row in self.cells for e in row]
        flat[max(0, idx)].focus_set()
        return "break"

    @property
    def row_count(self) -> int:
        return len(self.cells)

    @property
    def col_count(self) -> int:
        return len(self.cells[0]) if self.cells else 0

    def focused_position(self) -> tuple[int, int]:
        focus = self.focus_get()
        for r, row in enumerate(self.cells):
            for c, entry in enumerate(row):
                if entry is focus:
                    return r, c
        return self.row_count - 1, self.col_count - 1

    # ------------------------------------------------------- Bearbeiten
    def insert_row(self, below: bool = True) -> None:
        r, _c = self.focused_position()
        self._add_row([(None, "")] * max(1, self.col_count), r + 1 if below else r)
        self._changed()

    def insert_column(self, right: bool = True) -> None:
        _r, c = self.focused_position()
        index = c + 1 if right else c
        for r, row in enumerate(self.cells):
            row.insert(index, self._make_entry(""))
            self.originals[r].insert(index, (None, ""))
        self._regrid()
        self._changed()

    def delete_row(self) -> None:
        if self.row_count <= 1:
            return
        r, _c = self.focused_position()
        for entry in self.cells.pop(r):
            entry.destroy()
        self.originals.pop(r)
        self._regrid()
        self._changed()

    def delete_column(self) -> None:
        if self.col_count <= 1:
            return
        _r, c = self.focused_position()
        for r, row in enumerate(self.cells):
            row.pop(c).destroy()
            self.originals[r].pop(c)
        for widget in self.grid_slaves():
            widget.grid_forget()
        self._regrid()
        self._changed()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    # ---------------------------------------------------------- Anzeige
    def apply_palette(self, palette: dict, zoom: int | None = None) -> None:
        self.palette = palette
        if zoom is not None:
            self.zoom = zoom
        size = max(6, round(theme.DEFAULT_DOC_SIZE * self.zoom / 100))
        width = max(6, 72 // max(1, self.col_count))
        self.configure(bg=palette["marker"])
        for r, row in enumerate(self.cells):
            header = self.header_row and r == 0
            for entry in row:
                entry.configure(
                    width=width, bg=palette["page"], fg=palette["text"],
                    insertbackground=palette["cursor"], selectbackground=palette["selection"],
                    highlightbackground=palette["page"], highlightcolor=palette["cursor"],
                    font=(theme.DEFAULT_DOC_FONT, size, "bold" if header else "normal"),
                )

    # --------------------------------------------------------- Export
    def to_table(self, table_cls, cell_cls):
        rows = []
        for r, row in enumerate(self.cells):
            out = []
            for c, entry in enumerate(row):
                original, shown = self.originals[r][c]
                text = entry.get()
                if original is not None and text == shown:
                    out.append(original)  # unverändert: Formatierung der Zelle behalten
                else:
                    out.append(cell_cls.from_text(text.replace(PARA_MARK, "\n")))
            rows.append(out)
        return table_cls(rows=rows, header_row=self.header_row)

    def texts(self) -> list[list[str]]:
        return [[e.get() for e in row] for row in self.cells]


def _cell_text(cell) -> str:
    return getattr(cell, "text", "").replace("\n", PARA_MARK)
