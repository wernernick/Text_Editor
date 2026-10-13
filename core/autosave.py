"""Automatisches Zwischenspeichern und Wiederherstellung nach Absturz (wie Word "Dokumentwiederherstellung").

Ablauf für die UI:
- alle N Sekunden bei ungespeicherten Änderungen: ``autosave(doc)``
- nach erfolgreichem Speichern oder bewusstem Schließen ohne Speichern: ``discard(doc.path)``
- beim Start: ``list_recoverable()`` anzeigen, ``recover(entry)`` öffnet die Sicherung.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from core import file_manager
from core.docx_io import load_docx, save_docx
from core.document_model import Document

DEFAULT_INTERVAL_SECONDS = 120  # Word sichert standardmäßig alle 10 Minuten; 2 Minuten verlieren weniger


@dataclass(frozen=True)
class RecoveryEntry:
    autosave_path: str
    original_path: str | None  # None = Dokument war noch nie gespeichert
    saved_at: float  # Unix-Zeit

    @property
    def display_name(self) -> str:
        name = os.path.basename(self.original_path) if self.original_path else "Unbenannt"
        return f"{name} ({time.strftime('%d.%m.%Y %H:%M', time.localtime(self.saved_at))})"


def _meta_path(autosave_file: Path) -> Path:
    return autosave_file.with_name(autosave_file.name + ".json")


def autosave(doc: Document) -> Path:
    """Speichert eine Sicherung des Dokuments, ohne doc.path zu verändern."""
    original = doc.path
    target = file_manager.autosave_path(original)
    try:
        save_docx(doc, str(target))
    finally:
        doc.path = original
    meta = {"original_path": os.path.abspath(original) if original else None, "saved_at": time.time()}
    _meta_path(target).write_text(json.dumps(meta), encoding="utf-8")
    return target


def discard(doc_path: str | None) -> None:
    """Entfernt die Sicherung eines Dokuments (z.B. nach normalem Speichern)."""
    target = file_manager.autosave_path(doc_path)
    for path in (target, _meta_path(target)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def list_recoverable() -> list[RecoveryEntry]:
    """Alle vorhandenen Sicherungen, neueste zuerst."""
    folder = file_manager.app_dir() / "autosave"
    entries: list[RecoveryEntry] = []
    if not folder.is_dir():
        return entries
    for docx_file in folder.glob("*.autosave.docx"):
        original, saved_at = None, docx_file.stat().st_mtime
        try:
            meta = json.loads(_meta_path(docx_file).read_text(encoding="utf-8"))
            original = meta.get("original_path") or None
            saved_at = float(meta.get("saved_at", saved_at))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        entries.append(RecoveryEntry(str(docx_file), original, saved_at))
    entries.sort(key=lambda e: e.saved_at, reverse=True)
    return entries


def recover(entry: RecoveryEntry) -> Document:
    """Lädt eine Sicherung; doc.path zeigt wieder auf die Originaldatei (oder None)."""
    doc = load_docx(entry.autosave_path)
    doc.path = entry.original_path
    return doc


def is_due(last_autosave: float, interval: float = DEFAULT_INTERVAL_SECONDS, now: float | None = None) -> bool:
    """True, wenn seit der letzten Sicherung das Intervall vergangen ist."""
    return ((time.time() if now is None else now) - last_autosave) >= interval
