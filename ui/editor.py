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
from ui.table_widget import TableWidget

RUN_PREFIX = "run|"
ALIGN_PREFIX = "align|"
STYLE_PREFIX = "style|"
LEVEL_PREFIX = "level|"  # Listenebene 1..2 (Ebene 0 hat keinen Tag)
PARA_PREFIXES = (ALIGN_PREFIX, STYLE_PREFIX, LEVEL_PREFIX)
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
        self.palette = theme.PAGE_PALETTES["neon"]
        self._known_run_tags: set[str] = set()
        self.tables: dict[str, TableWidget] = {}
        self.active_table: TableWidget | None = None

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
            # Listenebenen (Einzug) liegen über den Listenvorlagen
            for level in range(1, theme.MAX_LIST_LEVEL + 1):
                self.text.tag_raise(LEVEL_PREFIX + str(level))
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
            size, bold, _color = spec
            color = self.palette["headings"].get(name, _color)
            self.text.tag_configure(
                tag, foreground=color, spacing1=10, spacing3=8,
                font=(theme.DEFAULT_DOC_FONT, max(1, round(size * self.zoom / 100)),
                      "bold" if bold else "normal"),
            )
            self.text.tag_raise(tag)
        for level in range(1, theme.MAX_LIST_LEVEL + 1):
            indent = round(theme.LIST_INDENT * (level + 1) * self.zoom / 100)
            self.text.tag_configure(LEVEL_PREFIX + str(level), lmargin1=indent, lmargin2=indent)
            self.text.tag_raise(LEVEL_PREFIX + str(level))

    def set_page_mode(self, mode: str) -> None:
        """Seitenfarbe umschalten: "neon" oder "paper"."""
        self.palette = theme.PAGE_PALETTES[mode]
        pal = self.palette
        self.page.configure(fg_color=pal["page"], border_color=pal["border"])
        self.text.configure(bg=pal["page"], fg=pal["text"], insertbackground=pal["cursor"],
                            selectbackground=pal["selection"], selectforeground=pal["text"])
        self._configure_style_tags()
        self.schedule_markers()
        for table in self.tables.values():
            table.apply_palette(pal)

    def set_zoom(self, zoom: int) -> None:
        self.zoom = zoom
        for table in self.tables.values():
            table.apply_palette(self.palette, zoom)
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
                         if t.startswith(PARA_PREFIXES)]
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

    def list_level(self, line: int) -> int:
        return int(self.paragraph_value(LEVEL_PREFIX, f"{line}.0", "0"))

    def list_markers(self) -> list[tuple[int, str]]:
        """(Zeile, Markierung) für alle Listenabsätze. Nummern zählen je Ebene fortlaufend
        (1. / a. / i. wie in Word); eine tiefere Ebene beginnt nach jedem übergeordneten Punkt neu."""
        result = []
        counters = [0] * (theme.MAX_LIST_LEVEL + 1)
        last_line = int(self.text.index("end-1c").split(".")[0])
        for line in range(1, last_line + 1):
            style = self.paragraph_value(STYLE_PREFIX, f"{line}.0", "Normal")
            if style not in theme.LIST_STYLES:
                counters = [0] * (theme.MAX_LIST_LEVEL + 1)
                continue
            level = min(theme.MAX_LIST_LEVEL, self.list_level(line))
            for deeper in range(level + 1, theme.MAX_LIST_LEVEL + 1):
                counters[deeper] = 0
            if style == "List Bullet":
                result.append((line, theme.BULLET_CHARS[level]))
            else:
                counters[level] += 1
                result.append((line, _number_label(counters[level], level)))
        return result

    def change_list_level(self, delta: int) -> bool:
        """Listenebene der markierten Listenabsätze ändern (Tab / Umschalt+Tab). False, wenn
        keine Liste betroffen ist."""
        lines = [n for n in self._selected_lines()
                 if self.paragraph_value(STYLE_PREFIX, f"{n}.0", "Normal") in theme.LIST_STYLES]
        if not lines:
            return False
        for line in lines:
            level = max(0, min(theme.MAX_LIST_LEVEL, self.list_level(line) + delta))
            self._set_level(line, level)
        self.text.edit_modified(True)
        self.schedule_markers()
        return True

    def _set_level(self, line: int, level: int) -> None:
        start, end = f"{line}.0", f"{line}.0 lineend +1c"
        for tag in self.text.tag_names():
            if tag.startswith(LEVEL_PREFIX):
                self.text.tag_remove(tag, start, end)
        if level > 0:
            self.text.tag_add(LEVEL_PREFIX + str(level), start, end)

    def handle_tab(self, shift: bool = False) -> bool:
        """Wie Word: Tab am Anfang eines Listenpunkts (oder über mehrere Zeilen markiert)
        rückt die Liste ein, Umschalt+Tab rückt aus. Sonst normales Tab-Zeichen."""
        multi_line = self.has_selection() and \
            self.text.index("sel.first").split(".")[0] != self.text.index("sel.last").split(".")[0]
        at_start = self.text.compare("insert", "==", "insert linestart")
        if not (shift or multi_line or at_start):
            return False
        return self.change_list_level(-1 if shift else 1)

    def _refresh_markers(self) -> None:
        self._marker_job = None
        markers = []
        for line, label in self.list_markers():
            info = self.text.dlineinfo(f"{line}.0")
            if info:
                markers.append((info, label))
        while len(self._markers) < len(markers):
            self._markers.append(tk.Label(
                self.text, borderwidth=0, padx=0, pady=0))
        size = max(6, round(theme.DEFAULT_DOC_SIZE * self.zoom / 100))
        pad_x, pad_y = int(self.text.cget("padx")), int(self.text.cget("pady"))
        for widget, (info, label) in zip(self._markers, markers):
            x, y, _w, height, _base = info
            widget.configure(text=label, font=(theme.DEFAULT_DOC_FONT, size, "bold"),
                             bg=self.palette["page"], fg=self.palette["marker"])
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
        self.transform_format(lambda fmt: replace(fmt, **changes))

    def transform_format(self, func) -> None:
        """Wendet func(CharFormat) -> CharFormat auf jeden Abschnitt der Auswahl an
        (ohne Auswahl auf das Tippformat)."""
        if not self.has_selection():
            self.typing_format = func(self.typing_format)
            self._notify_cursor()
            return
        start, end = self.text.index("sel.first"), self.text.index("sel.last")
        self.text.edit_separator()
        for s, e, fmt in list(self._segments(start, end)):
            for tag in self.text.tag_names(s):
                if tag.startswith(RUN_PREFIX):
                    self.text.tag_remove(tag, s, e)
            self.text.tag_add(self._ensure_run_tag(func(fmt)), s, e)
        self.text.edit_separator()
        self.typing_format = func(self.format_at("sel.first"))
        self.text.edit_modified(True)

    def step_font_size(self, direction: int) -> None:
        """Wie Word (Strg+Shift+> / <): zur nächsten Größe der Standardliste springen."""
        sizes = theme.FONT_SIZES

        def step(fmt: CharFormat) -> CharFormat:
            if direction > 0:
                size = next((x for x in sizes if x > fmt.font_size), fmt.font_size + 10)
            else:
                size = next((x for x in reversed(sizes) if x < fmt.font_size), max(1, fmt.font_size - 1))
            return replace(fmt, font_size=min(400, size))

        self.transform_format(step)

    def clear_format(self) -> None:
        """Zeichenformat und Formatvorlage der Auswahl auf Standard zurücksetzen."""
        self.transform_format(lambda _fmt: CharFormat())
        if self.has_selection():
            lines = list(self._selected_lines())
            if any(self.paragraph_value(STYLE_PREFIX, f"{n}.0", "Normal") not in theme.LIST_STYLES
                   for n in lines):
                self.set_style("Normal")

    def change_case(self, mode: str) -> None:
        """mode: "upper", "lower", "title" oder "cycle" (wie Umschalt+F3 in Word)."""
        if not self.has_selection():
            return
        start, end = self.text.index("sel.first"), self.text.index("sel.last")
        content = self.text.get(start, end)
        if mode == "cycle":
            if content == content.lower():
                mode = "upper"
            elif content == content.upper():
                mode = "title"
            else:
                mode = "lower"
        convert = {"upper": str.upper, "lower": str.lower, "title": str.title}[mode]
        whole = convert(content)
        self.text.edit_separator()
        segments = list(self._segments(start, end))
        offsets, pos = [], 0
        for s_, e_, _fmt in segments:
            length = len(self.text.get(s_, e_))
            offsets.append((pos, pos + length))
            pos += length
        same_length = len(whole) == len(content)
        for (s_, e_, _fmt), (a_, b_) in reversed(list(zip(segments, offsets))):
            original = content[a_:b_]
            # Gleiche Länge: Ergebnis der Gesamtumwandlung verteilen (Wortanfänge stimmen
            # auch über Formatgrenzen); sonst (z.B. "ß" -> "SS") je Abschnitt umwandeln.
            new = whole[a_:b_] if same_length else convert(original)
            if new != original:
                self.replace_range(s_, e_, new)
        end = f"{start} +{len(whole)}c"
        self.text.tag_add("sel", start, end)
        self.text.edit_separator()

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
        if style not in theme.LIST_STYLES:
            for line in self._selected_lines():
                self._set_level(line, 0)

    # ------------------------------------------------------- Tabellen
    def _create_table_widget(self, table, index: str) -> TableWidget:
        widget = TableWidget(self.text, table, self.palette, self.zoom,
                             on_focus=self._table_focused, on_change=self._table_changed)
        self.text.window_create(index, window=widget, padx=2, pady=4)
        self.tables[str(widget)] = widget
        return widget

    def _table_focused(self, widget: TableWidget) -> None:
        self.active_table = widget

    def _table_changed(self) -> None:
        self.text.edit_modified(True)

    def table_on_line(self, line: int) -> TableWidget | None:
        for key, value, _index in self.text.dump(f"{line}.0", f"{line}.0 lineend", window=True):
            if key == "window" and value in self.tables:
                return self.tables[value]
        return None

    def insert_table(self, table) -> TableWidget:
        """Fügt die Tabelle als eigenen Block unterhalb des aktuellen Absatzes ein."""
        line = int(self.text.index("insert").split(".")[0])
        if self.text.get(f"{line}.0", f"{line}.0 lineend") or self.table_on_line(line):
            self.text.insert(f"{line}.0 lineend", "\n")
            line += 1
        self.text.edit_separator()
        widget = self._create_table_widget(table, f"{line}.0")
        if self.text.compare(f"{line}.0 lineend", "==", "end-1c"):
            self.text.insert("end-1c", "\n")  # Platz zum Weiterschreiben unter der Tabelle
        self.text.mark_set("insert", f"{line + 1}.0")
        self.active_table = widget
        self.text.edit_modified(True)
        return widget

    # ------------------------------------------------------- Inhalt
    def clear(self) -> None:
        for widget in self.tables.values():
            widget.destroy()
        self.tables.clear()
        self.active_table = None
        self.text.delete("1.0", "end")
        self.text.edit_reset()
        self.typing_format = CharFormat()

    def replace_range(self, start: str, end: str, new_text: str) -> None:
        """Ersetzt Text und übernimmt Zeichen-/Absatzformat vom Anfang des Bereichs."""
        tags = tuple(t for t in self.text.tag_names(start)
                     if t.startswith((RUN_PREFIX, *PARA_PREFIXES)))
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
            if getattr(para, "table", None) is not None:
                self._create_table_widget(para.table, "end-1c")
                if p_index < len(paragraphs) - 1:
                    self.text.tk.call(self._orig_cmd, "insert", "end-1c", "\n")
                continue
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
            if style in theme.LIST_STYLES:
                level = max(0, min(theme.MAX_LIST_LEVEL, int(getattr(para, "list_level", 0) or 0)))
                self._set_level(int(line), level)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.mark_set("insert", "1.0")
        self._on_cursor_moved()

    def to_document(self, document_cls, paragraph_cls, run_cls, table_cls=None, cell_cls=None):
        """Erzeugt ein Document aus dem Widget-Inhalt (Klassen werden übergeben,
        damit die UI nicht zur Ladezeit vom Core abhängt)."""
        paragraphs = []
        last_line = int(self.text.index("end-1c").split(".")[0])
        for line in range(1, last_line + 1):
            start, end = f"{line}.0", f"{line}.0 lineend"
            table_widget = self.table_on_line(line)
            if table_widget is not None and table_cls is not None:
                paragraphs.append(paragraph_cls(table=table_widget.to_table(table_cls, cell_cls)))
                continue
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
                extra = {"list_type": STYLE_TO_LIST_TYPE[style], "list_level": self.list_level(line)}
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


def _number_label(n: int, level: int) -> str:
    """1. / a. / i. je nach Listenebene (wie core.document_model)."""
    if level == 1:
        letters = ""
        while n > 0:
            n, rest = divmod(n - 1, 26)
            letters = chr(ord("a") + rest) + letters
        return f"{letters}."
    if level == 2:
        out = ""
        for value, symbol in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                              (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
            while n >= value:
                out += symbol
                n -= value
        return f"{out}."
    return f"{n}."


def _same_format(a: CharFormat, b: CharFormat) -> bool:
    return a == b
