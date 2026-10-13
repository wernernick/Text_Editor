"""Textfläche mit Formatierung und Konvertierung Text-Widget <-> Document-Modell.

Formatierung wird über Tk-Tags abgebildet:
- Zeichenformat: genau ein kombinierter Tag pro Zeichen, z.B. "run|1|0|0|Calibri|11|#ff00aa"
  (fett|kursiv|unterstrichen|Schriftart|Größe|Farbe, Farbe leer = Standard).
- Absatzformat: "align|<left|center|right|justify>" und "style|<Name>" über die ganze Zeile.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, replace

import customtkinter as ctk

from ui import theme

RUN_PREFIX = "run|"
ALIGN_PREFIX = "align|"
STYLE_PREFIX = "style|"
ALIGNMENTS = ("left", "center", "right", "justify")
LIST_TYPE_TO_STYLE = {"bullet": "List Bullet", "number": "List Number"}
STYLE_TO_LIST_TYPE = {v: k for k, v in LIST_TYPE_TO_STYLE.items()}


@dataclass(frozen=True)
class CharFormat:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_family: str = theme.DEFAULT_DOC_FONT
    font_size: int = theme.DEFAULT_DOC_SIZE
    color: str | None = None

    def tag(self) -> str:
        return "|".join([
            "run", str(int(self.bold)), str(int(self.italic)), str(int(self.underline)),
            self.font_family, str(self.font_size), self.color or "",
        ])

    @staticmethod
    def from_tag(tag: str) -> "CharFormat":
        _, b, i, u, family, size, color = tag.split("|", 6)
        return CharFormat(b == "1", i == "1", u == "1", family, int(size), color or None)


class DocumentEditor(ctk.CTkFrame):
    """Seite im Cyber-Look mit einem tk.Text darin."""

    def __init__(self, master, on_change=None, on_cursor=None, **kwargs):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.on_change = on_change
        self.on_cursor = on_cursor
        self.zoom = 100
        self.typing_format = CharFormat()
        self._known_run_tags: set[str] = set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.page = ctk.CTkFrame(
            self, fg_color=theme.BG_PAGE, corner_radius=6,
            border_width=1, border_color=theme.ACCENT, width=theme.PAGE_WIDTH,
        )
        self.page.grid(row=0, column=1, sticky="ns", pady=18)
        self.page.grid_propagate(False)
        self.page.grid_rowconfigure(0, weight=1)
        self.page.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(
            self.page, wrap="word", undo=True, autoseparators=True, maxundo=-1,
            bg=theme.BG_PAGE, fg=theme.TEXT_PAGE, insertbackground=theme.CURSOR,
            insertwidth=2, selectbackground=theme.SELECTION_BG, selectforeground=theme.TEXT_PAGE,
            relief="flat", borderwidth=0, highlightthickness=0,
            padx=theme.PAGE_PADDING, pady=theme.PAGE_PADDING,
            font=(theme.DEFAULT_DOC_FONT, theme.DEFAULT_DOC_SIZE),
            spacing1=2, spacing3=6,
        )
        self.text.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.scrollbar = ctk.CTkScrollbar(
            self, command=self.text.yview, button_color=theme.BORDER,
            button_hover_color=theme.ACCENT,
        )
        self.scrollbar.grid(row=0, column=3, sticky="ns")
        self.text.configure(yscrollcommand=self._on_yscroll)
        self._markers: list[tk.Label] = []
        self._marker_job = None
        self.text.bind("<Configure>", lambda _e: self.schedule_markers(), add="+")

        for align in ALIGNMENTS:
            self.text.tag_configure(ALIGN_PREFIX + align, justify="left" if align == "justify" else align)
        self._configure_style_tags()

        self._install_insert_proxy()
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<Return>", lambda _e: self.text.after_idle(self._after_return), add="+")
        for seq in ("<KeyRelease>", "<ButtonRelease-1>", "<<Selection>>"):
            self.text.bind(seq, self._on_cursor_moved, add="+")

    # ------------------------------------------------------------------ Tags
    def _font_for(self, fmt: CharFormat) -> tkfont.Font:
        size = max(1, round(fmt.font_size * self.zoom / 100))
        return tkfont.Font(
            family=fmt.font_family, size=size,
            weight="bold" if fmt.bold else "normal",
            slant="italic" if fmt.italic else "roman",
            underline=fmt.underline,
        )

    def _ensure_run_tag(self, fmt: CharFormat) -> str:
        tag = fmt.tag()
        if tag not in self._known_run_tags:
            self._known_run_tags.add(tag)
            self.text.tag_configure(tag, font=self._font_for(fmt), foreground=fmt.color or "")
            # Absatzvorlagen sollen weiterhin über Zeichenformaten liegen.
            for style in theme.PARAGRAPH_STYLES:
                if theme.PARAGRAPH_STYLES[style]:
                    self.text.tag_raise(STYLE_PREFIX + style)
        return tag

    def _configure_style_tags(self) -> None:
        for name, spec in theme.PARAGRAPH_STYLES.items():
            tag = STYLE_PREFIX + name
            if spec is None:
                self.text.tag_configure(tag)
                continue
            if spec == "list":
                indent = round(theme.LIST_INDENT * self.zoom / 100)
                self.text.tag_configure(tag, lmargin1=indent, lmargin2=indent)
                continue
            size, bold, color = spec
            self.text.tag_configure(
                tag, foreground=color, spacing1=10, spacing3=8,
                font=(theme.DEFAULT_DOC_FONT, max(1, round(size * self.zoom / 100)),
                      "bold" if bold else "normal"),
            )
            self.text.tag_raise(tag)

    def set_zoom(self, zoom: int) -> None:
        self.zoom = zoom
        self.schedule_markers()
        for tag in self._known_run_tags:
            self.text.tag_configure(tag, font=self._font_for(CharFormat.from_tag(tag)))
        self._configure_style_tags()
        width = max(300, round(theme.PAGE_WIDTH * zoom / 100))
        self.page.configure(width=width)
        self.text.configure(font=(theme.DEFAULT_DOC_FONT, max(1, round(theme.DEFAULT_DOC_SIZE * zoom / 100))))

    # ------------------------------------------------- Einfügen abfangen
    def _install_insert_proxy(self) -> None:
        """Leitet 'insert' des Tk-Widgets um, damit neuer Text (Tippen, Einfügen)
        das aktuelle Zeichen- und Absatzformat bekommt."""
        widget = str(self.text)
        self._orig_cmd = widget + "_orig"
        tk_ = self.text.tk
        tk_.call("rename", widget, self._orig_cmd)
        tk_.createcommand(widget, self._proxy)

    def _proxy(self, *args):
        tk_ = self.text.tk
        if args and args[0] == "insert" and len(args) >= 3:
            index = str(tk_.call(self._orig_cmd, "index", args[1]))
            line = index.split(".")[0]
            para_tags = [t for t in tk_.splitlist(tk_.call(self._orig_cmd, "tag", "names", f"{line}.0"))
                         if t.startswith((ALIGN_PREFIX, STYLE_PREFIX))]
            run_tag = self._ensure_run_tag(self.typing_format)
            tags = (run_tag, *para_tags)
            # insert index chars ?tagList chars tagList ...? -> nur einfache Form umschreiben
            if len(args) == 3 or (len(args) == 4 and not args[3]):
                args = ("insert", args[1], args[2], tags)
        return tk_.call((self._orig_cmd,) + tuple(args))

    # ---------------------------------------------------------- Events
    # ------------------------------------------------- Listen-Markierungen
    def _on_yscroll(self, first, last) -> None:
        self.scrollbar.set(first, last)
        self.schedule_markers()

    def schedule_markers(self) -> None:
        if self._marker_job is None:
            self._marker_job = self.text.after_idle(self._refresh_markers)

    def list_markers(self) -> list[tuple[int, str]]:
        """(Zeile, Markierung) für alle Listenabsätze; Nummern zählen fortlaufend."""
        result = []
        number = 0
        last_line = int(self.text.index("end-1c").split(".")[0])
        for line in range(1, last_line + 1):
            style = self.paragraph_value(STYLE_PREFIX, f"{line}.0", "Normal")
            if style == "List Number":
                number += 1
                result.append((line, f"{number}."))
            else:
                number = 0
                if style == "List Bullet":
                    result.append((line, theme.BULLET_CHAR))
        return result

    def _refresh_markers(self) -> None:
        self._marker_job = None
        markers = []
        for line, label in self.list_markers():
            info = self.text.dlineinfo(f"{line}.0")
            if info:
                markers.append((info, label))
        while len(self._markers) < len(markers):
            self._markers.append(tk.Label(
                self.text, bg=theme.BG_PAGE, fg=theme.ACCENT, borderwidth=0, padx=0, pady=0))
        size = max(6, round(theme.DEFAULT_DOC_SIZE * self.zoom / 100))
        pad_x, pad_y = int(self.text.cget("padx")), int(self.text.cget("pady"))
        for widget, (info, label) in zip(self._markers, markers):
            x, y, _w, height, _base = info
            widget.configure(text=label, font=(theme.DEFAULT_DOC_FONT, size, "bold"))
            # place() rechnet ab dem inneren Rand (padx/pady) des Text-Widgets
            widget.place(x=x - round(theme.LIST_INDENT * self.zoom / 100) - pad_x,
                         y=y - pad_y, height=height)
        for widget in self._markers[len(markers):]:
            widget.place_forget()

    def toggle_list(self, style: str) -> None:
        """Wie Word: Liste ein-/ausschalten für die markierten Absätze."""
        lines = list(self._selected_lines())
        all_set = all(self.paragraph_value(STYLE_PREFIX, f"{n}.0", "Normal") == style for n in lines)
        self.set_style("Normal" if all_set else style)

    def _on_modified(self, _event=None) -> None:
        self.schedule_markers()
        if self.text.edit_modified():
            if self.on_change:
                self.on_change()
            self.text.edit_modified(False)
            self._notify_cursor()

    def _on_cursor_moved(self, _event=None) -> None:
        fmt = self.format_at("insert -1c") if self.text.compare("insert", ">", "insert linestart") \
            else self.format_at("insert")
        if not self.has_selection():
            self.typing_format = fmt
        self._notify_cursor()

    def _after_return(self) -> None:
        """Wie in Word: nach einer Überschrift beginnt der neue Absatz als "Normal"."""
        line = int(self.text.index("insert").split(".")[0])
        prev_style = self.paragraph_value(STYLE_PREFIX, f"{line - 1}.0", "Normal")
        if line > 1 and prev_style in theme.LIST_STYLES:
            if not self.text.get(f"{line - 1}.0", f"{line}.0 lineend").strip("\n"):
                # Enter in leerem Listenpunkt beendet die Liste
                self.text.delete(f"{line - 1}.0 lineend")
                self.text.mark_set("insert", f"{line - 1}.0")
                self.set_style("Normal")
            self.schedule_markers()
            return
        if line > 1 and prev_style != "Normal" and not self.text.get(f"{line}.0", f"{line}.0 lineend"):
            start, end = f"{line}.0", f"{line}.0 lineend +1c"
            for tag in self.text.tag_names(start):
                if tag.startswith(STYLE_PREFIX):
                    self.text.tag_remove(tag, start, end)
            self.typing_format = CharFormat()
            self._notify_cursor()

    def _notify_cursor(self) -> None:
        if self.on_cursor:
            self.on_cursor()

    # ---------------------------------------------------------- Abfragen
    def has_selection(self) -> bool:
        return bool(self.text.tag_ranges("sel"))

    def format_at(self, index: str) -> CharFormat:
        for tag in self.text.tag_names(index):
            if tag.startswith(RUN_PREFIX):
                return CharFormat.from_tag(tag)
        return CharFormat()

    def current_format(self) -> CharFormat:
        if self.has_selection():
            return self.format_at("sel.first")
        return self.typing_format

    def paragraph_value(self, prefix: str, index: str = "insert", default: str = "") -> str:
        for tag in self.text.tag_names(f"{index} linestart"):
            if tag.startswith(prefix):
                return tag[len(prefix):]
        return default

    def get_plain_text(self) -> str:
        return self.text.get("1.0", "end-1c")

    def stats(self) -> tuple[int, int]:
        content = self.get_plain_text()
        return len(content.split()), len(content.replace("\n", ""))

    def cursor_position(self) -> tuple[int, int]:
        line, col = self.text.index("insert").split(".")
        return int(line), int(col) + 1

    # ---------------------------------------------------- Zeichenformat
    def _run_tag_at(self, index: str) -> str | None:
        for tag in self.text.tag_names(index):
            if tag.startswith(RUN_PREFIX):
                return tag
        return None

    def _segments(self, start: str, end: str):
        """Liefert (start, end, CharFormat)-Abschnitte mit gleichem Zeichenformat."""
        start, end = self.text.index(start), self.text.index(end)
        if self.text.compare(start, ">=", end):
            return
        active = self._run_tag_at(start)
        seg_start = start
        for key, value, index in self.text.dump(start, end, tag=True):
            if not value.startswith(RUN_PREFIX) or self.text.compare(index, "<=", seg_start):
                if key == "tagon" and value.startswith(RUN_PREFIX):
                    active = value
                continue
            if key == "tagon" or (key == "tagoff" and value == active):
                yield seg_start, index, CharFormat.from_tag(active) if active else CharFormat()
                seg_start = index
                active = value if key == "tagon" else None
        if self.text.compare(seg_start, "<", end):
            yield seg_start, end, CharFormat.from_tag(active) if active else CharFormat()

    def apply_format(self, **changes) -> None:
        """Ändert Zeichenformat der Auswahl bzw. das Tippformat ohne Auswahl."""
        if not self.has_selection():
            self.typing_format = replace(self.typing_format, **changes)
            self._notify_cursor()
            return
        start, end = self.text.index("sel.first"), self.text.index("sel.last")
        self.text.edit_separator()
        segments = list(self._segments(start, end))
        for s, e, fmt in segments:
            for tag in self.text.tag_names(s):
                if tag.startswith(RUN_PREFIX):
                    self.text.tag_remove(tag, s, e)
            new_tag = self._ensure_run_tag(replace(fmt, **changes))
            self.text.tag_add(new_tag, s, e)
        self.text.edit_separator()
        self.typing_format = replace(self.current_format(), **changes)
        self.text.edit_modified(True)

    def toggle(self, attr: str) -> None:
        current = getattr(self.current_format(), attr)
        self.apply_format(**{attr: not current})

    # ---------------------------------------------------- Absatzformat
    def _selected_lines(self) -> range:
        if self.has_selection():
            first = int(self.text.index("sel.first").split(".")[0])
            last = int(self.text.index("sel.last").split(".")[0])
        else:
            first = last = int(self.text.index("insert").split(".")[0])
        return range(first, last + 1)

    def _set_paragraph_tag(self, prefix: str, value: str) -> None:
        for line in self._selected_lines():
            start, end = f"{line}.0", f"{line}.0 lineend +1c"
            for tag in list(self.text.tag_names()):
                if tag.startswith(prefix):
                    self.text.tag_remove(tag, start, end)
            self.text.tag_add(prefix + value, start, end)
        self.text.edit_modified(True)

    def set_alignment(self, alignment: str) -> None:
        self._set_paragraph_tag(ALIGN_PREFIX, alignment)

    def set_style(self, style: str) -> None:
        self._set_paragraph_tag(STYLE_PREFIX, style)

    # ------------------------------------------------------- Inhalt
    def clear(self) -> None:
        self.text.delete("1.0", "end")
        self.text.edit_reset()
        self.typing_format = CharFormat()

    def replace_range(self, start: str, end: str, new_text: str) -> None:
        """Ersetzt Text und übernimmt Zeichen-/Absatzformat vom Anfang des Bereichs."""
        tags = tuple(t for t in self.text.tag_names(start)
                     if t.startswith((RUN_PREFIX, ALIGN_PREFIX, STYLE_PREFIX)))
        start = self.text.index(start)
        self.text.delete(start, end)
        if new_text:
            self.text.tk.call(self._orig_cmd, "insert", start, new_text, tags)
        self.text.edit_modified(True)

    def insert_plain(self, text: str) -> None:
        self.text.insert("insert", text)

    def load_document(self, document) -> None:
        """Füllt das Widget aus einem core.document_model.Document."""
        self.clear()
        paragraphs = list(getattr(document, "paragraphs", []) or [])
        for p_index, para in enumerate(paragraphs):
            line_start = self.text.index("end-1c")
            for run in getattr(para, "runs", []) or []:
                fmt = CharFormat(
                    bold=bool(getattr(run, "bold", False)),
                    italic=bool(getattr(run, "italic", False)),
                    underline=bool(getattr(run, "underline", False)),
                    font_family=getattr(run, "font_family", None) or theme.DEFAULT_DOC_FONT,
                    font_size=int(round(getattr(run, "font_size", None) or theme.DEFAULT_DOC_SIZE)),
                    color=getattr(run, "color", None) or None,
                )
                text = getattr(run, "text", "") or ""
                if text:
                    tag = self._ensure_run_tag(fmt)
                    self.text.tk.call(self._orig_cmd, "insert", "end-1c", text, (tag,))
            if p_index < len(paragraphs) - 1:
                self.text.tk.call(self._orig_cmd, "insert", "end-1c", "\n")
            line = line_start.split(".")[0]
            alignment = getattr(para, "alignment", "left") or "left"
            if alignment not in ALIGNMENTS:
                alignment = "left"
            style = getattr(para, "style", "Normal") or "Normal"
            list_type = getattr(para, "list_type", None)
            if list_type in LIST_TYPE_TO_STYLE:
                style = LIST_TYPE_TO_STYLE[list_type]
            self.text.tag_add(ALIGN_PREFIX + alignment, f"{line}.0", f"{line}.0 lineend +1c")
            if style in theme.PARAGRAPH_STYLES:
                self.text.tag_add(STYLE_PREFIX + style, f"{line}.0", f"{line}.0 lineend +1c")
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.mark_set("insert", "1.0")
        self._on_cursor_moved()

    def to_document(self, document_cls, paragraph_cls, run_cls):
        """Erzeugt ein Document aus dem Widget-Inhalt (Klassen werden übergeben,
        damit die UI nicht zur Ladezeit vom Core abhängt)."""
        paragraphs = []
        last_line = int(self.text.index("end-1c").split(".")[0])
        for line in range(1, last_line + 1):
            start, end = f"{line}.0", f"{line}.0 lineend"
            runs = []
            for s, e, fmt in self._segments(start, end):
                text = self.text.get(s, e)
                if not text:
                    continue
                if runs and _same_format(runs[-1][1], fmt):
                    runs[-1] = (runs[-1][0] + text, fmt)
                else:
                    runs.append((text, fmt))
            style = self.paragraph_value(STYLE_PREFIX, start, "Normal")
            extra = {}
            if style in STYLE_TO_LIST_TYPE:
                # Listen stehen im Core-Modell als list_type, nicht als Formatvorlage
                extra = {"list_type": STYLE_TO_LIST_TYPE[style], "list_level": 0}
                style = "Normal"
            paragraphs.append(paragraph_cls(
                runs=[run_cls(text=t, bold=f.bold, italic=f.italic, underline=f.underline,
                              font_family=f.font_family, font_size=f.font_size, color=f.color)
                      for t, f in runs],
                alignment=self.paragraph_value(ALIGN_PREFIX, start, "left"),
                style=style,
                **extra,
            ))
        return document_cls(paragraphs=paragraphs)


def _same_format(a: CharFormat, b: CharFormat) -> bool:
    return a == b
