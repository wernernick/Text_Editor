"""Datenmodell eines Dokuments: Dokument -> Absätze -> Runs (gleich formatierter Text)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ALIGNMENTS = ("left", "center", "right", "justify")


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

    def word_count(self) -> int:
        return len(self.plain_text().split())

    def char_count(self) -> int:
        return sum(len(p.text) for p in self.paragraphs)
