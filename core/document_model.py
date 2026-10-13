"""Datenmodell eines Dokuments: Dokument -> Absätze -> Runs (gleich formatierter Text)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ALIGNMENTS = ("left", "center", "right", "justify")
LIST_TYPES = ("bullet", "number")
MAX_LIST_LEVEL = 2  # Ebenen 0..2, wie die Word-Standardvorlagen "List Bullet", "List Bullet 2", "List Bullet 3"
BULLET_SYMBOLS = ("•", "◦", "▪")


@dataclass
class Run:
    """Ein Textstück mit einheitlicher Formatierung."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_family: Optional[str] = None
    font_size: Optional[float] = None  # in Punkt
    color: Optional[str] = None  # "#RRGGBB"

    def same_format(self, other: "Run") -> bool:
        return (
            self.bold == other.bold
            and self.italic == other.italic
            and self.underline == other.underline
            and self.font_family == other.font_family
            and self.font_size == other.font_size
            and self.color == other.color
        )


@dataclass
class Paragraph:
    """Ein Absatz aus mehreren Runs."""

    runs: list[Run] = field(default_factory=list)
    alignment: str = "left"  # left | center | right | justify
    style: str = "Normal"  # z.B. "Heading 1"
    list_type: Optional[str] = None  # None | "bullet" | "number"
    list_level: int = 0  # Einrückungsebene der Liste, 0..MAX_LIST_LEVEL

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)

    def merge_runs(self) -> None:
        """Fasst benachbarte Runs mit gleicher Formatierung zusammen und entfernt leere."""
        merged: list[Run] = []
        for run in self.runs:
            if not run.text:
                continue
            if merged and merged[-1].same_format(run):
                merged[-1].text += run.text
            else:
                merged.append(Run(**vars(run)))
        self.runs = merged


@dataclass
class Document:
    """Ein komplettes Dokument."""

    paragraphs: list[Paragraph] = field(default_factory=list)
    path: Optional[str] = None

    @classmethod
    def new(cls) -> "Document":
        return cls(paragraphs=[Paragraph(runs=[])])

    @classmethod
    def from_text(cls, text: str) -> "Document":
        lines = text.split("\n")
        return cls(paragraphs=[Paragraph(runs=[Run(line)] if line else []) for line in lines])

    def plain_text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)

    def list_labels(self) -> list[Optional[str]]:
        """Aufzählungszeichen bzw. Nummer je Absatz ("•", "1.", "a." ...), None ohne Liste.

        Nummerierung zählt pro Ebene fortlaufend, bis ein Absatz ohne Liste sie unterbricht;
        eine tiefere Ebene beginnt nach jedem übergeordneten Eintrag neu (wie in Word).
        """
        labels: list[Optional[str]] = []
        counters = [0] * (MAX_LIST_LEVEL + 1)
        for para in self.paragraphs:
            if para.list_type not in LIST_TYPES:
                counters = [0] * (MAX_LIST_LEVEL + 1)
                labels.append(None)
                continue
            level = max(0, min(MAX_LIST_LEVEL, para.list_level))
            for deeper in range(level + 1, MAX_LIST_LEVEL + 1):
                counters[deeper] = 0
            if para.list_type == "bullet":
                labels.append(BULLET_SYMBOLS[level])
                continue
            counters[level] += 1
            labels.append(_number_label(counters[level], level))
        return labels

    def word_count(self) -> int:
        return len(self.plain_text().split())

    def char_count(self) -> int:
        return sum(len(p.text) for p in self.paragraphs)


def _number_label(n: int, level: int) -> str:
    """1. / a. / i. je nach Ebene."""
    if level == 1:
        letters = ""
        while n > 0:
            n, rest = divmod(n - 1, 26)
            letters = chr(ord("a") + rest) + letters
        return f"{letters}."
    if level == 2:
        return f"{_roman(n)}."
    return f"{n}."


def _roman(n: int) -> str:
    values = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
              (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))
    out = ""
    for value, symbol in values:
        while n >= value:
            out += symbol
            n -= value
    return out
