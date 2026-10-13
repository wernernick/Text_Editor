"""Lesen und Schreiben von .docx-Dateien über python-docx."""
from __future__ import annotations

import os

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from core.document_model import Document, Paragraph, Run

_ALIGN_TO_DOCX = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}
_DOCX_TO_ALIGN = {value: key for key, value in _ALIGN_TO_DOCX.items()}


def _style_name(paragraph) -> str:
    try:
        return paragraph.style.name if paragraph.style is not None else "Normal"
    except (KeyError, ValueError):
        return "Normal"


def _read_color(run) -> str | None:
    try:
        rgb = run.font.color.rgb if run.font.color is not None and run.font.color.type is not None else None
    except (AttributeError, ValueError):
        return None
    return f"#{rgb}" if rgb is not None else None


def load_docx(path: str) -> Document:
    """Lädt eine .docx-Datei in das Dokumentmodell."""
    source = docx.Document(path)
    paragraphs: list[Paragraph] = []
    for para in source.paragraphs:
        runs = [
            Run(
                text=run.text,
                bold=bool(run.bold),
                italic=bool(run.italic),
                underline=bool(run.underline),
                font_family=run.font.name,
                font_size=run.font.size.pt if run.font.size is not None else None,
                color=_read_color(run),
            )
            for run in para.runs
        ]
        model_para = Paragraph(
            runs=runs,
            alignment=_DOCX_TO_ALIGN.get(para.alignment, "left"),
            style=_style_name(para),
        )
        model_para.merge_runs()
        paragraphs.append(model_para)
    if not paragraphs:
        paragraphs.append(Paragraph(runs=[]))
    return Document(paragraphs=paragraphs, path=os.path.abspath(path))


def save_docx(doc: Document, path: str) -> None:
    """Speichert das Dokumentmodell als .docx-Datei."""
    target = docx.Document()
    style_names = {style.name for style in target.styles}
    for para in doc.paragraphs:
        out = target.add_paragraph()
        if para.style in style_names:
            out.style = target.styles[para.style]
        out.alignment = _ALIGN_TO_DOCX.get(para.alignment, WD_ALIGN_PARAGRAPH.LEFT)
        for run in para.runs:
            out_run = out.add_run(run.text)
            out_run.bold = run.bold
            out_run.italic = run.italic
            out_run.underline = run.underline
            if run.font_family:
                out_run.font.name = run.font_family
            if run.font_size:
                out_run.font.size = Pt(run.font_size)
            if run.color:
                out_run.font.color.rgb = RGBColor.from_string(run.color.lstrip("#").upper())
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    target.save(path)
    doc.path = os.path.abspath(path)
