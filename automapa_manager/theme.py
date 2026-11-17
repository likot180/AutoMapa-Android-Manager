"""Motywy jasny/ciemny w stylu Ustawień Windows 11 (ttk) oraz wykrywanie motywu systemowego."""
from __future__ import annotations

import subprocess
import sys
import tkinter.font as tkfont
from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str  # tło okna i paska bocznego
    card: str  # karty
    fg: str
    muted: str
    field: str
    border: str  # obramowanie kart
    input_border: str
    button: str
    button_hover: str
    accent: str
    accent_fg: str
    nav_sel: str
    nav_hover: str
    ok: str
    warn: str
    err: str
    # --- kontrolki Fluent ---
    ctrl: str  # wypełnienie przycisku / pola wyboru
    ctrl_hover: str
    ctrl_press: str
    ctrl_border: str
    accent_hover: str
    accent_press: str
    flyout: str  # lista rozwijana, okna dialogowe
    flyout_border: str
    track: str  # tło paska postępu
    check_border: str  # obrys niezaznaczonego pola / opcji
    input_fill: str  # wypełnienie pól tekstowych i konsoli


LIGHT = Palette("light", "#f3f3f3", "#ffffff", "#1a1a1a", "#5f5f5f", "#ffffff", "#e3e3e3", "#8a8a8a",
                "#fdfdfd", "#f3f3f3", "#0067c0", "#ffffff", "#e6e6e6", "#ebebeb",
                "#0f7b0f", "#9d5d00", "#c42b1c",
                "#fbfbfb", "#f4f4f4", "#ececec", "#dcdcdc", "#1975c5", "#3183ca",
                "#fcfcfc", "#dedede", "#d4d4d4", "#6e6e6e", "#f6f6f6")
DARK = Palette("dark", "#202020", "#2b2b2b", "#ffffff", "#a8a8a8", "#2b2b2b", "#383838", "#8d8d8d",
               "#373737", "#404040", "#4cc2ff", "#00121c", "#2f2f2f", "#2a2a2a",
               "#6ccb5f", "#f7c948", "#ff7b72",
               "#373737", "#3f3f3f", "#2f2f2f", "#434343", "#47b1e8", "#42a1d2",
               "#2c2c2c", "#454545", "#4a4a4a", "#a0a0a0", "#232323")


def system_theme() -> str:
    try:
        if sys.platform.startswith("win"):
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                return "light" if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else "dark"
        if sys.platform == "darwin":
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True
            ).stdout
            return "dark" if "Dark" in out else "light"
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        return "dark" if "dark" in out.lower() else "light"
    except Exception:
        return "light"


def resolve(mode: str) -> Palette:
    name = system_theme() if mode == "system" else mode
    return DARK if name == "dark" else LIGHT


# Czcionki dostępne dla reszty aplikacji po wywołaniu apply().
F: dict[str, tkfont.Font] = {}
ICON_FAMILY: str = ""  # Segoe Fluent Icons / Segoe MDL2 Assets (tylko Windows)


def _make_fonts(root) -> None:
    global ICON_FAMILY
    fams = set(tkfont.families(root))
    base_family = tkfont.nametofont("TkDefaultFont").actual("family")
    if sys.platform.startswith("win"):
        for cand in ("Segoe UI Variable Text", "Segoe UI"):
            if cand in fams:
                base_family = cand
                break
    semi = "Segoe UI Semibold" if "Segoe UI Semibold" in fams else base_family
    semi_weight = "normal" if semi != base_family else "bold"

    def font(family, size, weight="normal", **kw):
        return tkfont.Font(root=root, family=family, size=size, weight=weight, **kw)

    F["base"] = font(base_family, 11)
    F["small"] = font(base_family, 10)
    F["bold"] = font(semi, 11, semi_weight)
    F["h1"] = font(semi, 22, semi_weight)
    F["h2"] = font(semi, 14, semi_weight)
    F["h3"] = font(semi, 12, semi_weight)
    F["link"] = font(base_family, 11, underline=True)
    F["mono"] = font(tkfont.nametofont("TkFixedFont").actual("family"), 10)
    for icon in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if icon in fams:
            ICON_FAMILY = icon
            break
    F["icon"] = font(ICON_FAMILY or base_family, 14)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        tkfont.nametofont(name).configure(family=base_family, size=11)


def apply(root, mode: str) -> Palette:
    p = resolve(mode)
    style = ttk.Style(root)
    style.theme_use("clam")
    if not F:
        _make_fonts(root)

    root.configure(background=p.bg)
    style.configure(".", background=p.bg, foreground=p.fg, fieldbackground=p.field, font=F["base"],
                    bordercolor=p.border, lightcolor=p.bg, darkcolor=p.bg, troughcolor=p.field,
                    focuscolor=p.bg, selectbackground=p.accent, selectforeground=p.accent_fg,
                    insertcolor=p.fg)
    style.map(".", foreground=[("disabled", p.muted)])

    # --- przyciski ---
    style.configure("TButton", background=p.button, foreground=p.fg, padding=(16, 7),
                    bordercolor=p.input_border, lightcolor=p.button, darkcolor=p.button, focusthickness=0)
    style.map("TButton", background=[("disabled", p.bg), ("pressed", p.border), ("active", p.button_hover)],
              bordercolor=[("disabled", p.border)])
    style.configure("Accent.TButton", background=p.accent, foreground=p.accent_fg, padding=(20, 8),
                    bordercolor=p.accent, lightcolor=p.accent, darkcolor=p.accent, font=F["bold"])
    style.map("Accent.TButton", background=[("disabled", p.button), ("pressed", p.accent), ("active", p.accent)],
              foreground=[("disabled", p.muted)], bordercolor=[("disabled", p.border)])

    # --- pola wyboru (tło okna i tło karty) ---
    for prefix, bg in (("", p.bg), ("Card.", p.card)):
        for w in ("TCheckbutton", "TRadiobutton"):
            name = prefix + w
            style.configure(name, background=bg, foreground=p.fg, indicatorbackground=p.field,
                            indicatorforeground=p.fg, padding=(2, 4))
            style.map(name, background=[("active", bg)], foreground=[("disabled", p.muted)],
                      indicatorbackground=[("selected", p.accent), ("disabled", p.bg)],
                      indicatorforeground=[("selected", p.accent_fg)])

    style.configure("TEntry", fieldbackground=p.field, foreground=p.fg, bordercolor=p.input_border,
                    lightcolor=p.field, darkcolor=p.field, padding=7)
    style.map("TEntry", bordercolor=[("focus", p.accent)], lightcolor=[("focus", p.accent)],
              darkcolor=[("focus", p.accent)])
    style.configure("TCombobox", fieldbackground=p.field, foreground=p.fg, background=p.button,
                    arrowcolor=p.fg, bordercolor=p.input_border, lightcolor=p.field, darkcolor=p.field,
                    padding=7, arrowsize=16)
    style.map("TCombobox", fieldbackground=[("readonly", p.field)], foreground=[("readonly", p.fg)],
              selectbackground=[("readonly", p.field)], selectforeground=[("readonly", p.fg)],
              bordercolor=[("focus", p.accent)])
    root.option_add("*TCombobox*Listbox.background", p.field)
    root.option_add("*TCombobox*Listbox.foreground", p.fg)
    root.option_add("*TCombobox*Listbox.selectBackground", p.accent)
    root.option_add("*TCombobox*Listbox.selectForeground", p.accent_fg)
    root.option_add("*TCombobox*Listbox.font", F["base"])

    style.configure("TSeparator", background=p.border, bordercolor=p.border, lightcolor=p.border,
                    darkcolor=p.border)
    style.configure("Horizontal.TProgressbar", background=p.accent, troughcolor=p.border,
                    bordercolor=p.border, lightcolor=p.accent, darkcolor=p.accent, thickness=6)
    # smukły pasek przewijania bez strzałek (jak w Windows 11)
    style.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("Vertical.TScrollbar", background=p.input_border, troughcolor=p.bg, bordercolor=p.bg,
                    lightcolor=p.input_border, darkcolor=p.input_border, width=10, gripcount=0, relief="flat")
    style.map("Vertical.TScrollbar", background=[("active", p.muted)])

    # --- karty i etykiety ---
    style.configure("Card.TFrame", background=p.card, bordercolor=p.border, relief="solid", borderwidth=1)
    style.configure("CardInner.TFrame", background=p.card)
    style.configure("Card.TLabel", background=p.card, foreground=p.fg)
    style.configure("CardMuted.TLabel", background=p.card, foreground=p.muted, font=F["small"])
    style.configure("CardBold.TLabel", background=p.card, foreground=p.fg, font=F["bold"])
    style.configure("CardH3.TLabel", background=p.card, foreground=p.fg, font=F["h3"])
    style.configure("Card.TSeparator", background=p.border)
    style.configure("Muted.TLabel", foreground=p.muted, font=F["small"])
    style.configure("H1.TLabel", font=F["h1"])
    style.configure("H2.TLabel", font=F["h2"])
    style.configure("Link.TLabel", foreground=p.accent, font=F["link"])
    for kind, color in (("Ok", p.ok), ("Warn", p.warn), ("Err", p.err)):
        style.configure(f"{kind}.Title.TLabel", background=p.card, foreground=color, font=F["h2"])
    style.configure("Title.TLabel", background=p.card, foreground=p.fg, font=F["h2"])
    return p


def set_titlebar(root, dark: bool) -> None:
    """Ciemny pasek tytułu w Windows 10/11."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), 4) == 0:
                break
    except Exception:
        pass
