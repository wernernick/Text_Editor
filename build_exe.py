"""Baut den Text Editor als eigenständige .exe (PyInstaller).

Aufruf: python build_exe.py  ->  Ergebnis: dist/TextEditor(.exe)
"""
import os
import sys

import PyInstaller.__main__

ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    os.chdir(ROOT)
    PyInstaller.__main__.run([
        "main.py",
        "--onefile",
        "--windowed",
        "--name", "TextEditor",
        "--collect-data", "customtkinter",
        "--collect-data", "docx",
        "--noconfirm",
        "--clean",
    ])
    exe = os.path.join(ROOT, "dist", "TextEditor.exe" if sys.platform == "win32" else "TextEditor")
    print(f"Fertig: {exe}")


if __name__ == "__main__":
    main()
