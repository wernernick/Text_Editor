"""Lesen und Schreiben von .docx-Dateien über python-docx."""
from __future__ import annotations

import io
import os
import tempfile

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.enum.section import WD_ORIENT
from docx.shared import Mm, Pt, RGBColor
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

from core.document_model import (
    LIST_TYPES, MAX_LIST_LEVEL, Document, Image, PageSetup, Paragraph, Run, Table, TableCell,
)

EMU_PER_PT = 12700

_ALIGN_TO_DOCX = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}
_DOCX_TO_ALIGN = {value: key for key, value in _ALIGN_TO_DOCX.items()}
_LIST_STYLE_BASE = {"bullet": "List Bullet", "number": "List Number"}


def _list_style_name(list_type: str, level: int) -> str:
    base = _LIST_STYLE_BASE[list_type]
    return base if level <= 0 else f"{base} {level + 1}"


def _parse_list_style(style: str) -> tuple[str, int] | None:
    """"List Bullet 2" -> ("bullet", 1); andere Formatvorlagen -> None."""
    for list_type, base in _LIST_STYLE_BASE.items():
        if style == base:
            return list_type, 0
        if style.startswith(base + " ") and style[len(base) + 1:].isdigit():
            return list_type, min(MAX_LIST_LEVEL, int(style[len(base) + 1:]) - 1)
    return None


def _numbering_list(paragraph) -> tuple[str, int] | None:
    """Erkennt direkte Nummerierung (w:numPr) von Listen, die nicht über Formatvorlagen laufen."""
    p_pr = paragraph._p.pPr
    num_pr = p_pr.numPr if p_pr is not None else None
    if num_pr is None or num_pr.numId is None or num_pr.numId.val == 0:
        return None
    level = num_pr.ilvl.val if num_pr.ilvl is not None else 0
    list_type = "number"
    try:
        numbering = paragraph.part.numbering_part.element
        num = numbering.num_having_numId(num_pr.numId.val)
        abstract_id = num.abstractNumId.val
        for abstract in numbering.findall(qn("w:abstractNum")):
            if abstract.get(qn("w:abstractNumId")) != str(abstract_id):
                continue
            for lvl in abstract.findall(qn("w:lvl")):
                if lvl.get(qn("w:ilvl")) == str(level):
                    fmt = lvl.find(qn("w:numFmt"))
                    if fmt is not None and fmt.get(qn("w:val")) == "bullet":
                        list_type = "bullet"
    except (AttributeError, KeyError, NotImplementedError):
        pass
    return list_type, min(MAX_LIST_LEVEL, level)


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


def _read_paragraph(para) -> Paragraph:
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
    style = _style_name(para)
    list_info = _parse_list_style(style) or _numbering_list(para)
    if list_info and style.startswith(("List Bullet", "List Number")):
        style = "Normal"
    model_para = Paragraph(
        runs=runs,
        alignment=_DOCX_TO_ALIGN.get(para.alignment, "left"),
        style=style,
        list_type=list_info[0] if list_info else None,
        list_level=list_info[1] if list_info else 0,
    )
    model_para.merge_runs()
    return model_para


def _read_table(table: DocxTable) -> Table:
    rows: list[list[TableCell]] = []
    for row in table.rows:
        cells = []
        for cell in row.cells:  # verbundene Zellen erscheinen mehrfach; das Raster bleibt rechteckig
            paragraphs = [_read_paragraph(p) for p in cell.paragraphs] or [Paragraph()]
            cells.append(TableCell(paragraphs=paragraphs))
        rows.append(cells)
    width = max((len(r) for r in rows), default=1)
    for r in rows:
        r.extend(TableCell() for _ in range(width - len(r)))
    header = False
    if table.rows:
        tr_pr = table.rows[0]._tr.trPr
        header = tr_pr is not None and tr_pr.find(qn("w:tblHeader")) is not None
    return Table(rows=rows or [[TableCell()]], header_row=header)


def _iter_blocks(source):
    """Absätze und Tabellen des Dokumentkörpers in Originalreihenfolge."""
    for child in source.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield DocxParagraph(child, source)
        elif isinstance(child, CT_Tbl):
            yield DocxTable(child, source)


def _read_images(para) -> list[Image]:
    """Eingebettete Bilder (w:drawing mit a:blip) eines Absatzes."""
    images: list[Image] = []
    for drawing in para._p.iter(qn("w:drawing")):
        blip = next(drawing.iter(qn("a:blip")), None)
        r_id = blip.get(qn("r:embed")) if blip is not None else None
        if not r_id:
            continue
        try:
            part = para.part.related_parts[r_id]
        except KeyError:
            continue
        extent = next(drawing.iter(qn("wp:extent")), None)
        width = height = None
        if extent is not None:
            width = int(extent.get("cx", 0)) / EMU_PER_PT or None
            height = int(extent.get("cy", 0)) / EMU_PER_PT or None
        name = os.path.basename(getattr(part, "partname", "") or "") or "bild.png"
        images.append(Image(data=part.blob, filename=name, width_pt=width, height_pt=height))
    return images


def load_docx(path: str) -> Document:
    """Lädt eine .docx-Datei in das Dokumentmodell."""
    source = docx.Document(path)
    paragraphs: list[Paragraph] = []
    for block in _iter_blocks(source):
        if isinstance(block, DocxTable):
            paragraphs.append(Paragraph(table=_read_table(block)))
            continue
        model_para = _read_paragraph(block)
        images = _read_images(block)
        if model_para.text or not images:
            paragraphs.append(model_para)
        # Bilder werden zu eigenen Blöcken hinter dem Text des Absatzes
        paragraphs.extend(Paragraph(image=img, alignment=model_para.alignment) for img in images)
    if not paragraphs:
        paragraphs.append(Paragraph(runs=[]))
    return Document(paragraphs=paragraphs, path=os.path.abspath(path), page=_read_page(source))


def _read_page(source) -> PageSetup:
    page = PageSetup()
    if not source.sections:
        return page
    section = source.sections[0]
    for attr, value in (("width_mm", section.page_width), ("height_mm", section.page_height),
                        ("margin_top_mm", section.top_margin), ("margin_bottom_mm", section.bottom_margin),
                        ("margin_left_mm", section.left_margin), ("margin_right_mm", section.right_margin)):
        if value is not None:
            setattr(page, attr, round(value.mm, 1))
    return page


def _write_page(target, page: PageSetup) -> None:
    for section in target.sections:
        section.orientation = WD_ORIENT.LANDSCAPE if page.orientation == "landscape" else WD_ORIENT.PORTRAIT
        section.page_width = Mm(page.width_mm)
        section.page_height = Mm(page.height_mm)
        section.top_margin = Mm(page.margin_top_mm)
        section.bottom_margin = Mm(page.margin_bottom_mm)
        section.left_margin = Mm(page.margin_left_mm)
        section.right_margin = Mm(page.margin_right_mm)


def _write_paragraph(out, para: Paragraph, target) -> None:
    style = para.style
    if para.list_type in LIST_TYPES:
        style = _list_style_name(para.list_type, max(0, min(MAX_LIST_LEVEL, para.list_level)))
    if style in _style_names(target):
        out.style = target.styles[style]
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


def _style_names(target) -> set[str]:
    cached = getattr(target, "_te_style_names", None)
    if cached is None:
        cached = {style.name for style in target.styles}
        target._te_style_names = cached
    return cached


def _write_table(target, table: Table) -> None:
    out = target.add_table(rows=max(1, table.row_count), cols=max(1, table.col_count))
    if "Table Grid" in _style_names(target):
        out.style = target.styles["Table Grid"]
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row):
            out_cell = out.cell(r, c)
            for i, para in enumerate(cell.paragraphs or [Paragraph()]):
                out_para = out_cell.paragraphs[0] if i == 0 else out_cell.add_paragraph()
                _write_paragraph(out_para, para, target)
    if table.header_row:
        # Word: "Überschriftenzeilen wiederholen" markiert die Kopfzeile
        tr_pr = out.rows[0]._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:tblHeader"))


def unsupported_image_text(image: Image) -> str:
    """Platzhaltertext für Bilder, die python-docx nicht schreiben kann (EMF, WMF, SVG ...)."""
    return f"[Bild nicht unterstützt: {image.filename}]"


def _write_image(target, para: Paragraph) -> None:
    out = target.add_paragraph()
    out.alignment = _ALIGN_TO_DOCX.get(para.alignment, WD_ALIGN_PARAGRAPH.LEFT)
    if not para.image.is_supported:
        # python-docx kann nur PNG, JPEG, GIF, BMP und TIFF einbetten; statt abzubrechen
        # bleibt eine sichtbare Markierung, der Rest des Dokuments wird gespeichert.
        out.add_run(unsupported_image_text(para.image)).italic = True
        return
    width, height = para.image.display_size_pt()
    out.add_run().add_picture(io.BytesIO(para.image.data), width=Pt(width), height=Pt(height))


def save_docx(doc: Document, path: str) -> None:
    """Speichert das Dokumentmodell als .docx-Datei."""
    target = docx.Document()
    _write_page(target, doc.page)
    for para in doc.paragraphs:
        if para.table is not None:
            _write_table(target, para.table)
        elif para.image is not None:
            _write_image(target, para)
        else:
            _write_paragraph(target.add_paragraph(), para, target)
    _atomic_save(target, path)
    doc.path = os.path.abspath(path)


def _atomic_save(target, path: str) -> None:
    """Schreibt erst in eine Temp-Datei und ersetzt dann das Ziel: ein Absturz beim Speichern
    zerstört so nie die vorhandene Datei."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".~", suffix=".docx", dir=folder)
    os.close(fd)
    try:
        target.save(tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
