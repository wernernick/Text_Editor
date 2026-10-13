"""Ribbon-Menü im Word-Stil mit Tabs Start / Einfügen / Ansicht."""
from __future__ import annotations

import customtkinter as ctk

from ui import theme


def _button(master, text, command, width=None, accent=False):
    return ctk.CTkButton(
        master, text=text, command=command, width=width or 0, height=30,
        corner_radius=4, font=theme.ui_font(12, "bold" if accent else "normal"),
        fg_color=theme.BG_BUTTON, hover_color=theme.BG_BUTTON_HOVER,
        text_color=theme.ACCENT if accent else theme.TEXT,
        border_width=1, border_color=theme.BORDER,
    )


class RibbonGroup(ctk.CTkFrame):
    """Gruppe von Steuerelementen mit Beschriftung unten (wie in Word)."""

    def __init__(self, master, title: str):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True, padx=6, pady=(6, 0))
        ctk.CTkLabel(
            self, text=title.upper(), font=theme.ui_font(9, "bold"),
            text_color=theme.TEXT_MUTED, height=14,
        ).pack(side="bottom", pady=(0, 2))

    def row(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.pack(side="top", anchor="w", pady=2)
        return frame


class Ribbon(ctk.CTkFrame):
    def __init__(self, master, actions: dict):
        super().__init__(master, fg_color=theme.BG_RIBBON, corner_radius=0)
        self.actions = actions
        self.toggle_buttons: dict[str, ctk.CTkButton] = {}
        self.align_buttons: dict[str, ctk.CTkButton] = {}

        header = ctk.CTkFrame(self, fg_color=theme.BG_RIBBON, corner_radius=0)
        header.pack(side="top", fill="x")
        ctk.CTkLabel(
            header, text="◢ NEON//WRITE", font=theme.ui_font(14, "bold"),
            text_color=theme.ACCENT_2,
        ).pack(side="left", padx=(12, 18), pady=4)

        self.tab_buttons: dict[str, ctk.CTkButton] = {}
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.content = ctk.CTkFrame(self, fg_color=theme.BG_RIBBON, corner_radius=0,
                                    height=theme.RIBBON_HEIGHT)
        self.content.pack(side="top", fill="x")
        self.content.pack_propagate(False)

        for name, builder in (("Start", self._build_start), ("Einfügen", self._build_insert),
                              ("Ansicht", self._build_view)):
            btn = ctk.CTkButton(
                header, text=name, width=90, height=26, corner_radius=0,
                font=theme.ui_font(12, "bold"), fg_color="transparent",
                hover_color=theme.BG_BUTTON_HOVER, text_color=theme.TEXT_MUTED,
                command=lambda n=name: self.show_tab(n),
            )
            btn.pack(side="left", padx=1)
            self.tab_buttons[name] = btn
            page = ctk.CTkFrame(self.content, fg_color="transparent")
            builder(page)
            self.pages[name] = page

        # Neon-Linie unter dem Ribbon
        ctk.CTkFrame(self, fg_color=theme.ACCENT, height=2, corner_radius=0).pack(side="bottom", fill="x")
        self.show_tab("Start")

    def show_tab(self, name: str) -> None:
        for n, page in self.pages.items():
            page.pack_forget()
            self.tab_buttons[n].configure(
                text_color=theme.TEXT_MUTED, fg_color="transparent")
        self.pages[name].pack(fill="both", expand=True, padx=6)
        self.tab_buttons[name].configure(text_color=theme.ACCENT, fg_color=theme.BG_RIBBON_TAB)

    def _separator(self, page) -> None:
        ctk.CTkFrame(page, fg_color=theme.BORDER, width=1, corner_radius=0).pack(
            side="left", fill="y", pady=8)

    def _group(self, page, title) -> RibbonGroup:
        group = RibbonGroup(page, title)
        group.pack(side="left", fill="y")
        return group

    # ------------------------------------------------------------- Start
    def _build_start(self, page) -> None:
        a = self.actions
        g = self._group(page, "Datei")
        r = g.row()
        _button(r, "＋ Neu", a["new"], 80).pack(side="left", padx=2)
        _button(r, "📂 Öffnen", a["open"], 90).pack(side="left", padx=2)
        self.recent_button = _button(r, "🕘 Zuletzt", None, 80)
        self.recent_button.configure(command=lambda: a["recent"](self.recent_button))
        self.recent_button.pack(side="left", padx=2)
        r = g.row()
        _button(r, "💾 Speichern", a["save"], 80, accent=True).pack(side="left", padx=2)
        _button(r, "Speichern unter", a["save_as"], 120).pack(side="left", padx=2)
        self._separator(page)

        g = self._group(page, "Schriftart")
        r = g.row()
        self.font_family = ctk.CTkComboBox(
            r, values=theme.FONT_FAMILIES, width=150, height=28,
            command=a["font_family"], fg_color=theme.BG_BUTTON, border_color=theme.BORDER,
            button_color=theme.BORDER, button_hover_color=theme.ACCENT,
            dropdown_fg_color=theme.BG_RIBBON, dropdown_hover_color=theme.BG_BUTTON_HOVER,
            text_color=theme.TEXT, font=theme.ui_font(12),
        )
        self.font_family.set(theme.DEFAULT_DOC_FONT)
        self.font_family.pack(side="left", padx=2)
        self.font_size = ctk.CTkComboBox(
            r, values=[str(s) for s in theme.FONT_SIZES], width=70, height=28,
            command=a["font_size"], fg_color=theme.BG_BUTTON, border_color=theme.BORDER,
            button_color=theme.BORDER, button_hover_color=theme.ACCENT,
            dropdown_fg_color=theme.BG_RIBBON, dropdown_hover_color=theme.BG_BUTTON_HOVER,
            text_color=theme.TEXT, font=theme.ui_font(12),
        )
        self.font_size.set(str(theme.DEFAULT_DOC_SIZE))
        self.font_size.pack(side="left", padx=2)
        self.font_size._entry.bind("<Return>", lambda _e: a["font_size"](self.font_size.get()))
        r = g.row()
        for key, label, font in (("bold", "F", ("bold",)), ("italic", "K", ("italic",)),
                                 ("underline", "U", ("underline",))):
            btn = ctk.CTkButton(
                r, text=label, width=34, height=28, corner_radius=4,
                font=ctk.CTkFont(theme.UI_FONT_FAMILY, 13, weight="bold" if key == "bold" else "normal",
                                 slant="italic" if key == "italic" else "roman",
                                 underline=key == "underline"),
                fg_color=theme.BG_BUTTON, hover_color=theme.BG_BUTTON_HOVER, text_color=theme.TEXT,
                border_width=1, border_color=theme.BORDER, command=lambda k=key: a["toggle"](k),
            )
            btn.pack(side="left", padx=2)
            self.toggle_buttons[key] = btn
        self.color_button = _button(r, "A ▾", a["color"], 46)
        self.color_button.pack(side="left", padx=2)
        self._separator(page)

        g = self._group(page, "Absatz")
        r = g.row()
        for key, label in (("left", "⯇ Links"), ("center", "≡ Mitte"), ("right", "Rechts ⯈"),
                           ("justify", "☰ Block")):
            btn = _button(r, label, lambda k=key: a["align"](k), 70)
            btn.pack(side="left", padx=2)
            self.align_buttons[key] = btn
        r = g.row()
        _button(r, theme.BULLET_CHAR + " Aufzählung", a["list_bullet"], 110).pack(side="left", padx=2)
        _button(r, "1. Nummerierung", a["list_number"], 120).pack(side="left", padx=2)
        self._separator(page)

        g = self._group(page, "Formatvorlagen")
        r = g.row()
        self._style_by_label = {v: k for k, v in theme.STYLE_LABELS.items()}
        self.style_menu = ctk.CTkOptionMenu(
            r, values=list(theme.STYLE_LABELS.values()), width=160, height=28,
            command=lambda label: a["style"](self._style_by_label[label]),
            fg_color=theme.BG_BUTTON, button_color=theme.BORDER, button_hover_color=theme.ACCENT,
            dropdown_fg_color=theme.BG_RIBBON, dropdown_hover_color=theme.BG_BUTTON_HOVER,
            text_color=theme.TEXT, font=theme.ui_font(12),
        )
        self.style_menu.pack(side="left", padx=2)
        r = g.row()
        for style in ("Heading 1", "Heading 2"):
            _button(r, theme.STYLE_LABELS[style].replace("Überschrift", "Ü"),
                    lambda s=style: a["style"](s), 78).pack(side="left", padx=2)

        self._separator(page)
        g = self._group(page, "Bearbeiten")
        r = g.row()
        _button(r, "⌕ Suchen", a["find"], 96).pack(side="left", padx=2)
        r = g.row()
        _button(r, "⇄ Ersetzen", a["replace"], 96).pack(side="left", padx=2)

    # ---------------------------------------------------------- Einfügen
    def _build_insert(self, page) -> None:
        a = self.actions
        g = self._group(page, "Text")
        r = g.row()
        _button(r, "📅 Datum", a["insert_date"], 90).pack(side="left", padx=2)
        _button(r, "🕒 Uhrzeit", a["insert_time"], 90).pack(side="left", padx=2)
        r = g.row()
        _button(r, "— Trennlinie", a["insert_line"], 110).pack(side="left", padx=2)
        self._separator(page)
        g = self._group(page, "Symbole")
        r = g.row()
        for sym in ("©", "®", "™", "€", "§", "→", "•", "…"):
            _button(r, sym, lambda s=sym: a["insert_text"](s), 32).pack(side="left", padx=1)

    # ----------------------------------------------------------- Ansicht
    def _build_view(self, page) -> None:
        a = self.actions
        g = self._group(page, "Zoom")
        r = g.row()
        _button(r, "－", lambda: a["zoom_step"](-1), 34).pack(side="left", padx=2)
        self.zoom_label = ctk.CTkLabel(r, text="100 %", width=60, text_color=theme.ACCENT,
                                       font=theme.ui_font(12, "bold"))
        self.zoom_label.pack(side="left", padx=2)
        _button(r, "＋", lambda: a["zoom_step"](1), 34).pack(side="left", padx=2)
        r = g.row()
        _button(r, "100 %", a["zoom_reset"], 110).pack(side="left", padx=2)
        self._separator(page)
        g = self._group(page, "Anzeigen")
        r = g.row()
        self.wrap_switch = ctk.CTkSwitch(
            r, text="Zeilenumbruch", command=a["toggle_wrap"], progress_color=theme.ACCENT,
            text_color=theme.TEXT, font=theme.ui_font(12))
        self.wrap_switch.select()
        self.wrap_switch.pack(side="left", padx=4)
        r = g.row()
        self.status_switch = ctk.CTkSwitch(
            r, text="Statusleiste", command=a["toggle_status"], progress_color=theme.ACCENT,
            text_color=theme.TEXT, font=theme.ui_font(12))
        self.status_switch.select()
        self.status_switch.pack(side="left", padx=4)
        self._separator(page)
        g = self._group(page, "Seitenfarbe")
        r = g.row()
        self.page_mode = ctk.CTkSegmentedButton(
            r, values=["Neon", "Papier"], command=a["page_mode"], height=28,
            selected_color="#0f6a80", selected_hover_color="#13809a",
            unselected_color=theme.BG_BUTTON, unselected_hover_color=theme.BG_BUTTON_HOVER,
            fg_color=theme.BORDER, text_color=theme.TEXT, font=theme.ui_font(12))
        self.page_mode.set("Neon")
        self.page_mode.pack(side="left", padx=4)

    # ---------------------------------------------------- Zustand anzeigen
    def update_state(self, fmt, alignment: str, style: str) -> None:
        for key, btn in self.toggle_buttons.items():
            on = getattr(fmt, key)
            btn.configure(fg_color=theme.BG_BUTTON_ACTIVE if on else theme.BG_BUTTON,
                          border_color=theme.ACCENT if on else theme.BORDER,
                          text_color=theme.ACCENT if on else theme.TEXT)
        for key, btn in self.align_buttons.items():
            on = key == alignment
            btn.configure(fg_color=theme.BG_BUTTON_ACTIVE if on else theme.BG_BUTTON,
                          border_color=theme.ACCENT if on else theme.BORDER)
        if self.font_family.get() != fmt.font_family:
            self.font_family.set(fmt.font_family)
        if self.font_size.get() != str(fmt.font_size):
            self.font_size.set(str(fmt.font_size))
        self.color_button.configure(text_color=fmt.color or theme.ACCENT)
        label = theme.STYLE_LABELS.get(style, theme.STYLE_LABELS["Normal"])
        if self.style_menu.get() != label:
            self.style_menu.set(label)
