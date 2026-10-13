"""Zentrale Farben, Schriften und Maße für das Cyber-Design."""

# Grundflächen
BG_APP = "#07090f"          # Fensterhintergrund
BG_RIBBON = "#0d1220"       # Ribbon-Fläche
BG_RIBBON_TAB = "#111a2e"   # Inaktiver Tab
BG_PAGE = "#0b1018"         # Dokumentseite
BG_STATUS = "#0a0f1a"       # Statusleiste
BG_BUTTON = "#141d33"
BG_BUTTON_HOVER = "#1d2a4a"
BG_BUTTON_ACTIVE = "#0f3b4a"  # Umschalter aktiv (z.B. Fett an)

# Neon-Akzente
ACCENT = "#00e5ff"          # Cyan
ACCENT_2 = "#ff2bd6"        # Magenta
ACCENT_3 = "#7cff6b"        # Grün (Status ok)
BORDER = "#1f2b47"

# Text
TEXT = "#d7e3ff"
TEXT_MUTED = "#6c7a99"
TEXT_PAGE = "#e6edf7"
SELECTION_BG = "#14506a"
CURSOR = ACCENT

# Schriften
UI_FONT_FAMILY = "Segoe UI"
UI_FONT_SIZE = 12
MONO_FONT_FAMILY = "Consolas"
DEFAULT_DOC_FONT = "Calibri"
DEFAULT_DOC_SIZE = 11
FONT_FAMILIES = [
    "Calibri", "Arial", "Times New Roman", "Segoe UI", "Consolas",
    "Courier New", "Georgia", "Verdana", "Cambria", "Tahoma",
]
FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72]

# Absatzformatvorlagen: Name -> (Größe, fett, Farbe)
PARAGRAPH_STYLES = {
    "Normal": None,
    "Heading 1": (20, True, ACCENT),
    "Heading 2": (16, True, ACCENT_2),
    "Heading 3": (13, True, "#9fb4ff"),
    "Title": (28, True, ACCENT),
    "List Bullet": "list",   # Listen: Einzug + Aufzählungszeichen als Overlay
    "List Number": "list",
}
# Seitenfarben: "neon" (dunkle Cyber-Seite) und "paper" (helle Seite wie gedruckt)
PAGE_PALETTES = {
    "neon": {
        "page": BG_PAGE, "text": TEXT_PAGE, "selection": SELECTION_BG, "cursor": ACCENT,
        "border": ACCENT, "marker": ACCENT,
        "headings": {"Heading 1": ACCENT, "Heading 2": ACCENT_2, "Heading 3": "#9fb4ff", "Title": ACCENT},
    },
    "paper": {
        "page": "#fbfcff", "text": "#1a1f2b", "selection": "#bdeffa", "cursor": "#c2109a",
        "border": ACCENT_2, "marker": "#0086a8",
        "headings": {"Heading 1": "#0086a8", "Heading 2": "#b0128f", "Heading 3": "#3b4f9c", "Title": "#0086a8"},
    },
}

LIST_STYLES = ("List Bullet", "List Number")
LIST_INDENT = 28
BULLET_CHAR = "◆"
STYLE_LABELS = {
    "Normal": "Standard",
    "Heading 1": "Überschrift 1",
    "Heading 2": "Überschrift 2",
    "Heading 3": "Überschrift 3",
    "Title": "Titel",
    "List Bullet": "Aufzählung",
    "List Number": "Nummerierung",
}

# Maße
PAGE_WIDTH = 820
PAGE_PADDING = 48
RIBBON_HEIGHT = 108
ZOOM_LEVELS = [50, 75, 90, 100, 110, 125, 150, 175, 200]


def ui_font(size: int = UI_FONT_SIZE, weight: str = "normal"):
    return (UI_FONT_FAMILY, size, weight)
