"""Einstiegspunkt des Text Editors (NEON//WRITE).

Starten im Repo-Root oder aus VS Code:  python main.py
"""
import os
import sys

# Repo-Root in den Suchpfad, damit "ui" und "core" unabhängig vom Arbeitsverzeichnis gefunden werden.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ui.app import run  # noqa: E402


def main() -> None:
    run(sys.argv[1:])


if __name__ == "__main__":
    main()
