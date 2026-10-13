"""Dateisystem-Hilfen: zuletzt geöffnete Dateien, Autosave- und Backup-Pfade."""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

APP_DIR_NAME = ".text_editor"
MAX_RECENT = 10


def app_dir() -> Path:
    """Ordner für App-Daten im Home-Verzeichnis (wird bei Bedarf angelegt)."""
    base = Path(os.environ.get("TEXT_EDITOR_HOME", Path.home() / APP_DIR_NAME))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _recent_file() -> Path:
    return app_dir() / "recent_files.json"


def get_recent_files() -> list[str]:
    """Liste zuletzt geöffneter Dateien (neueste zuerst), nur noch existierende."""
    try:
        data = json.loads(_recent_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [p for p in data if isinstance(p, str) and os.path.exists(p)]


def add_recent_file(path: str) -> list[str]:
    """Setzt eine Datei an die Spitze der Liste und speichert sie."""
    path = os.path.abspath(path)
    recent = [p for p in get_recent_files() if p != path]
    recent.insert(0, path)
    recent = recent[:MAX_RECENT]
    try:
        _recent_file().write_text(json.dumps(recent, indent=2), encoding="utf-8")
    except OSError:
        pass
    return recent


def autosave_path(doc_path: str | None = None) -> Path:
    """Pfad für die Autosave-Datei eines Dokuments (oder eines unbenannten)."""
    folder = app_dir() / "autosave"
    folder.mkdir(parents=True, exist_ok=True)
    name = Path(doc_path).stem if doc_path else "Unbenannt"
    return folder / f"{name}.autosave.docx"


def backup_file(path: str, keep: int = 5) -> Path | None:
    """Kopiert eine vorhandene Datei vor dem Überschreiben in den Backup-Ordner."""
    if not os.path.exists(path):
        return None
    folder = app_dir() / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stem = Path(path).stem
    target = folder / f"{stem}.{time.strftime('%Y%m%d-%H%M%S')}{Path(path).suffix}"
    shutil.copy2(path, target)
    old = sorted(folder.glob(f"{stem}.*{Path(path).suffix}"))
    for stale in old[:-keep] if keep > 0 else []:
        try:
            stale.unlink()
        except OSError:
            pass
    return target
