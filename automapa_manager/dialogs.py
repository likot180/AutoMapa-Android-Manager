"""Okna dialogowe w stylu aplikacji (zamiast systemowych messagebox)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional, Sequence

from . import theme
from .widgets import FButton, px

# glify Segoe Fluent Icons / MDL2
KIND_GLYPH = {"info": "", "warning": "", "error": "", "question": ""}
KIND_FALLBACK = {"info": "i", "warning": "!", "error": "×", "question": "?"}


def make_shell(app, title: str, width: int = 520):
    """Okno modalne: treść na tle karty, pasek przycisków na tle okna (jak ContentDialog w Windows 11)."""
    p = app.pal
    dlg = tk.Toplevel(app.root)
    dlg.withdraw()
    dlg.title(title)
    dlg.configure(background=p.bg)
    dlg.transient(app.root)
    dlg.resizable(False, False)
    body = tk.Frame(dlg, background=p.card)
    body.pack(fill="both", expand=True)
    footer = tk.Frame(dlg, background=p.bg)
    footer.pack(fill="x")
    try:
        if app.root.tk.call("tk", "windowingsystem") == "win32":
            dlg.iconbitmap(default=str(_icon_path()))
    except tk.TclError:
        pass
    return dlg, body, footer


def _icon_path():
    from .adb import ROOT

    return ROOT / "assets" / "app.ico"


def show(app, dlg: tk.Toplevel, on_close_value: Any = None) -> None:
    """Pokazuje okno wyśrodkowane nad aplikacją i czeka na jego zamknięcie."""
    dlg.update_idletasks()
    root = app.root
    x = root.winfo_rootx() + (root.winfo_width() - dlg.winfo_width()) // 2
    y = root.winfo_rooty() + max((root.winfo_height() - dlg.winfo_height()) // 3, 20)
    dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    theme.set_titlebar(dlg, app.pal.name == "dark")
    dlg.deiconify()
    dlg.lift()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    dlg.focus_force()
    root.wait_window(dlg)


class _Result:
    value: Any = None


def _fit_text(text_widget: tk.Text, max_lines: int, text: str) -> bool:
    """Ustawia wysokość pola tekstowego (szacunek z miary czcionki, bo okno nie jest jeszcze widoczne).

    Zwraca True, gdy tekst nie mieści się w ``max_lines`` i potrzebny jest pasek przewijania."""
    font = theme.F["base"]
    width_px = max(text_widget.winfo_reqwidth() - px(6), 1)
    lines = 0
    for line in text.split("\n"):
        lines += max(1, -(-int(font.measure(line) * 1.12) // width_px))  # 12% zapasu na zawijanie słów
    text_widget.configure(height=min(lines, max_lines))
    return lines > max_lines


def dialog(app, kind: str, title: str, text: str, buttons: Sequence[tuple[str, Any]],
           default: int = 0, cancel_value: Any = None, heading: Optional[str] = None) -> Any:
    """kind: info | warning | error | question. buttons: [(etykieta, wartość)], pierwszy domyślnie akcentowany."""
    p = app.pal
    dlg, body, footer = make_shell(app, title)
    result = _Result()
    result.value = cancel_value

    top = tk.Frame(body, background=p.card)
    top.pack(fill="x", padx=px(28), pady=(px(26), px(8)))
    color = {"info": p.accent, "question": p.accent, "warning": p.warn, "error": p.err}[kind]
    if theme.ICON_FAMILY:
        tk.Label(top, text=KIND_GLYPH[kind], font=theme.F["icon"], background=p.card, foreground=color).pack(
            side="left", padx=(0, px(12)))
    else:
        tk.Label(top, text=KIND_FALLBACK[kind], font=theme.F["h3"], background=p.card, foreground=color).pack(
            side="left", padx=(0, px(12)))
    tk.Label(top, text=heading or title, font=theme.F["h3"], background=p.card, foreground=p.fg,
             anchor="w").pack(side="left", fill="x")

    box = tk.Frame(body, background=p.card)
    box.pack(fill="both", expand=True, padx=px(28), pady=(0, px(26)))
    txt = tk.Text(box, width=58, height=3, wrap="word", relief="flat", borderwidth=0, highlightthickness=0,
                  background=p.card, foreground=p.fg, font=theme.F["base"], padx=0, pady=0,
                  selectbackground=p.accent, selectforeground=p.accent_fg, cursor="arrow")
    txt.insert("1.0", text)
    txt.configure(state="disabled")
    txt.pack(side="left", fill="both", expand=True)
    if _fit_text(txt, 14, text):
        sb = ttk.Scrollbar(box, orient="vertical", command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.configure(yscrollcommand=sb.set)

    def choose(value):
        result.value = value
        dlg.destroy()

    btn_row = tk.Frame(footer, background=p.bg)
    btn_row.pack(fill="x", padx=px(24), pady=px(16))
    for i, (label, value) in enumerate(reversed(buttons)):
        idx = len(buttons) - 1 - i
        b = FButton(btn_row, p, label, lambda v=value: choose(v), accent=(idx == default), bg=p.bg, minwidth=110)
        b.pack(side="right", padx=(px(8), 0))
    dlg.bind("<Escape>", lambda e: choose(cancel_value))
    dlg.bind("<Return>", lambda e: choose(buttons[default][1]))
    dlg.protocol("WM_DELETE_WINDOW", lambda: choose(cancel_value))
    show(app, dlg)
    return result.value


def show_text(app, title: str, text: str, close_label: str) -> None:
    """Okno z przewijanym, długim tekstem (np. licencja)."""
    p = app.pal
    dlg, body, footer = make_shell(app, title)
    tk.Label(body, text=title, font=theme.F["h3"], background=p.card, foreground=p.fg, anchor="w").pack(
        fill="x", padx=px(24), pady=(px(22), px(10)))
    box = tk.Frame(body, background=p.card)
    box.pack(fill="both", expand=True, padx=px(24), pady=(0, px(20)))
    txt = tk.Text(box, width=84, height=24, wrap="word", relief="flat", borderwidth=0, highlightthickness=1,
                  highlightbackground=p.border, highlightcolor=p.border, background=p.input_fill, foreground=p.fg,
                  font=theme.F["mono"], padx=px(10), pady=px(8), selectbackground=p.accent,
                  selectforeground=p.accent_fg)
    txt.insert("1.0", text)
    txt.configure(state="disabled")
    sb = ttk.Scrollbar(box, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    txt.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    row = tk.Frame(footer, background=p.bg)
    row.pack(fill="x", padx=px(24), pady=px(16))
    FButton(row, p, close_label, dlg.destroy, accent=True, bg=p.bg, minwidth=110).pack(side="right")
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    show(app, dlg)
