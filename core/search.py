"""Suchen und Ersetzen im Dokumentmodell (wie Word: Groß-/Kleinschreibung, ganzes Wort, Platzhalter per Regex).

Treffer liegen immer innerhalb eines Absatzes. Ersetzter Text übernimmt die Formatierung
des ersten Zeichens des Treffers, der Rest der Formatierung bleibt unverändert.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.document_model import Document, Paragraph, Run


@dataclass(frozen=True)
class Match:
    paragraph: int  # Index des Absatzes
    start: int  # Zeichenposition im Absatztext
    end: int  # exklusiv
    text: str


def _compile(query: str, match_case: bool, whole_word: bool, regex: bool) -> re.Pattern | None:
    if not query:
        return None
    pattern = query if regex else re.escape(query)
    if whole_word:
        pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
    try:
        return re.compile(pattern, 0 if match_case else re.IGNORECASE)
    except re.error:
        return None


def is_valid_pattern(query: str, regex: bool) -> bool:
    """True, wenn die Suche ausführbar ist (bei Regex: gültiger Ausdruck)."""
    return _compile(query, True, False, regex) is not None


def find_all(doc: Document, query: str, match_case: bool = False, whole_word: bool = False,
             regex: bool = False) -> list[Match]:
    """Alle Treffer im Dokument in Lesereihenfolge. Leere Treffer werden ignoriert."""
    pattern = _compile(query, match_case, whole_word, regex)
    if pattern is None:
        return []
    matches: list[Match] = []
    for index, para in enumerate(doc.paragraphs):
        for m in pattern.finditer(para.text):
            if m.end() > m.start():
                matches.append(Match(index, m.start(), m.end(), m.group(0)))
    return matches


def find_next(doc: Document, query: str, paragraph: int = 0, offset: int = 0, wrap: bool = True,
              backwards: bool = False, **options) -> Match | None:
    """Nächster (bzw. vorheriger) Treffer ab Position (paragraph, offset), optional mit Umbruch."""
    matches = find_all(doc, query, **options)
    if not matches:
        return None
    position = (paragraph, offset)
    if backwards:
        before = [m for m in matches if (m.paragraph, m.start) < position]
        return before[-1] if before else (matches[-1] if wrap else None)
    after = [m for m in matches if (m.paragraph, m.start) >= position]
    return after[0] if after else (matches[0] if wrap else None)


def _replace_range(para: Paragraph, start: int, end: int, replacement: str) -> None:
    """Ersetzt Zeichen [start, end) eines Absatzes, Formatierung des ersten Zeichens wird übernommen."""
    new_runs: list[Run] = []
    position = 0
    inserted = False
    for run in para.runs:
        run_start, run_end = position, position + len(run.text)
        position = run_end
        if run_end <= start or run_start >= end:
            if run_start >= end and not inserted:
                new_runs.append(Run(**{**vars(run), "text": replacement}))
                inserted = True
            new_runs.append(Run(**vars(run)))
            continue
        head = run.text[: max(0, start - run_start)]
        tail = run.text[max(0, end - run_start):] if run_end > end else ""
        if head:
            new_runs.append(Run(**{**vars(run), "text": head}))
        if not inserted:
            new_runs.append(Run(**{**vars(run), "text": replacement}))
            inserted = True
        if tail:
            new_runs.append(Run(**{**vars(run), "text": tail}))
    if not inserted:
        new_runs.append(Run(**{**(vars(para.runs[-1]) if para.runs else {}), "text": replacement}))
    para.runs = new_runs
    para.merge_runs()


def _expand(match: Match, replacement: str, query: str, match_case: bool, whole_word: bool,
            regex: bool) -> str:
    if not regex:
        return replacement
    pattern = _compile(query, match_case, whole_word, regex)
    return pattern.sub(replacement, match.text, count=1) if pattern else replacement


def replace(doc: Document, match: Match, replacement: str, query: str = "", match_case: bool = False,
            whole_word: bool = False, regex: bool = False) -> None:
    """Ersetzt einen einzelnen Treffer. Bei Regex sind Rückverweise wie \\1 erlaubt (dann query angeben)."""
    text = _expand(match, replacement, query, match_case, whole_word, regex)
    _replace_range(doc.paragraphs[match.paragraph], match.start, match.end, text)


def replace_all(doc: Document, query: str, replacement: str, match_case: bool = False,
                whole_word: bool = False, regex: bool = False) -> int:
    """Ersetzt alle Treffer und gibt die Anzahl zurück."""
    options = dict(match_case=match_case, whole_word=whole_word, regex=regex)
    matches = find_all(doc, query, **options)
    for match in reversed(matches):  # von hinten, damit Positionen gültig bleiben
        replace(doc, match, replacement, query, **options)
    return len(matches)
