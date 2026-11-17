"""Własne kontrolki w stylu Fluent / Windows 11, rysowane na Canvas.

Tk nie ma zaokrągleń ani wygładzania, więc rogi i znaczniki są renderowane do małych
obrazków RGBA (supersampling 4x, czysty Python) i składane na płótnie.
"""
from __future__ import annotations

import base64
import math
import struct
import sys
import tkinter as tk
import webbrowser
import zlib
from typing import Callable, Optional, Sequence

from . import theme

# ----------------------------------------------------------------------
# skalowanie DPI
# ----------------------------------------------------------------------
_scale = 1.0


def init_scale(root: tk.Misc) -> None:
    global _scale
    try:
        _scale = max(root.winfo_fpixels("1i") / 96.0, 1.0)
    except tk.TclError:
        _scale = 1.0


def px(value: float) -> int:
    return max(int(round(value * _scale)), 1)


# ----------------------------------------------------------------------
# mały rasteryzator (RGBA, antyaliasing przez supersampling)
# ----------------------------------------------------------------------
def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _png(w: int, h: int, rgba: bytes) -> bytes:
    raw = bytearray()
    for y in range(h):
        raw += b"\x00" + rgba[y * w * 4:(y + 1) * w * 4]

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


# kształty: funkcje (x, y) -> bool, współrzędne w pikselach obrazka
def _rrect(x0, y0, x1, y1, r):
    def inside(x, y):
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        cx = x0 + r if x < x0 + r else (x1 - r if x > x1 - r else None)
        cy = y0 + r if y < y0 + r else (y1 - r if y > y1 - r else None)
        if cx is None or cy is None:
            return True
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    return inside


def _circle(cx, cy, r):
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _stroke(points, width):
    half = width / 2.0

    def inside(x, y):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            dx, dy = bx - ax, by - ay
            ln = dx * dx + dy * dy
            t = 0.0 if ln == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ln))
            qx, qy = ax + t * dx, ay + t * dy
            if (x - qx) ** 2 + (y - qy) ** 2 <= half * half:
                return True
        return False

    return inside


_img_cache: dict = {}


def render(key, w: int, h: int, shapes: Sequence[tuple[str, Callable]], ox: float = 0, oy: float = 0, ss: int = 4):
    """shapes: lista (kolor, test) rysowana w kolejności; zwraca tk.PhotoImage z alfą (z pamięci podręcznej)."""
    cache_key = (key, w, h, tuple(c for c, _ in shapes), ox, oy)
    if cache_key in _img_cache:
        return _img_cache[cache_key]
    colors = [_rgb(c) for c, _ in shapes]
    tests = [t for _, t in shapes]
    out = bytearray()
    total = ss * ss
    for y in range(h):
        for x in range(w):
            r = g = b = cov = 0
            for sy in range(ss):
                py = y + (sy + 0.5) / ss + oy
                for sx in range(ss):
                    pxx = x + (sx + 0.5) / ss + ox
                    for idx in range(len(tests) - 1, -1, -1):  # od góry
                        if tests[idx](pxx, py):
                            cr, cg, cb = colors[idx]
                            r += cr
                            g += cg
                            b += cb
                            cov += 1
                            break
            if cov:
                out += bytes((r // cov, g // cov, b // cov, int(255 * cov / total)))
            else:
                out += b"\x00\x00\x00\x00"
    img = tk.PhotoImage(data=base64.b64encode(_png(w, h, bytes(out))))
    _img_cache[cache_key] = img
    return img


def dot_image(color: str, size: int = 10) -> tk.PhotoImage:
    """Wypełniona kropka (wskaźnik stanu) z wygładzonymi brzegami."""
    s = px(size)
    return render(("dot", color, s), s, s, [(color, _circle(s / 2.0, s / 2.0, s / 2.0))])


def corner_images(r: int, fill: str, outline: Optional[str], bw: int):
    """Cztery ćwiartki zaokrąglonego prostokąta (nw, ne, sw, se) o rozmiarze r x r."""
    shapes = []
    size = 2 * r
    if outline:
        shapes.append((outline, _rrect(0, 0, size, size, r)))
        shapes.append((fill, _rrect(bw, bw, size - bw, size - bw, max(r - bw, 0))))
    else:
        shapes.append((fill, _rrect(0, 0, size, size, r)))
    key = ("corner", r, fill, outline, bw)
    return {
        "nw": render(key + ("nw",), r, r, shapes, 0, 0),
        "ne": render(key + ("ne",), r, r, shapes, r, 0),
        "sw": render(key + ("sw",), r, r, shapes, 0, r),
        "se": render(key + ("se",), r, r, shapes, r, r),
    }


def draw_round(canvas: tk.Canvas, x0: int, y0: int, x1: int, y1: int, r: int, fill: str,
               outline: Optional[str] = None, bw: int = 1, tag: str = "bg") -> None:
    """Zaokrąglony prostokąt [x0,x1) x [y0,y1) z wygładzonymi rogami."""
    r = max(min(r, (x1 - x0) // 2, (y1 - y0) // 2), 0)
    if r < 1:
        canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline or fill, width=bw if outline else 0, tags=tag)
        return
    imgs = corner_images(r, fill, outline, bw)
    band = outline or fill
    canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=band, outline="", tags=tag)
    canvas.create_rectangle(x0, y0 + r, x0 + r, y1 - r, fill=band, outline="", tags=tag)
    canvas.create_rectangle(x1 - r, y0 + r, x1, y1 - r, fill=band, outline="", tags=tag)
    if outline:
        canvas.create_rectangle(x0 + r, y0 + bw, x1 - r, y1 - bw, fill=fill, outline="", tags=tag)
        canvas.create_rectangle(x0 + bw, y0 + r, x0 + r, y1 - r, fill=fill, outline="", tags=tag)
        canvas.create_rectangle(x1 - r, y0 + r, x1 - bw, y1 - r, fill=fill, outline="", tags=tag)
    canvas.create_image(x0, y0, image=imgs["nw"], anchor="nw", tags=tag)
    canvas.create_image(x1 - r, y0, image=imgs["ne"], anchor="nw", tags=tag)
    canvas.create_image(x0, y1 - r, image=imgs["sw"], anchor="nw", tags=tag)
    canvas.create_image(x1 - r, y1 - r, image=imgs["se"], anchor="nw", tags=tag)


class RoundRect:
    """Zaokrąglony prostokąt jako stały zestaw elementów płótna.

    W odróżnieniu od ``draw_round`` zmiana rozmiaru tylko przesuwa współrzędne istniejących elementów
    (bez kasowania i tworzenia ich od nowa), więc jest tania i nie powoduje migotania podczas
    zmiany rozmiaru okna."""

    def __init__(self, canvas: tk.Canvas, r: int, fill: str, outline: Optional[str] = None, bw: int = 1,
                 tag: str = "bg"):
        self.c, self.r, self.bw, self.has_outline = canvas, max(r, 1), bw, bool(outline)
        imgs = corner_images(self.r, fill, outline, bw)

        def rect(color):
            return canvas.create_rectangle(0, 0, 0, 0, fill=color, outline="", tags=tag)

        self.outer = [rect(outline or fill) for _ in range(3)]
        self.inner = [rect(fill) for _ in range(3)] if outline else []
        self.corners = [canvas.create_image(0, 0, image=imgs[k], anchor="nw", tags=tag) for k in ("nw", "ne", "sw", "se")]
        self._last = None

    def resize(self, w: int, h: int) -> None:
        if (w, h) == self._last or w < 2 * self.r or h < 2 * self.r:
            return
        self._last = (w, h)
        r, bw, c = self.r, self.bw, self.c
        o = self.outer
        c.coords(o[0], r, 0, w - r, h)
        c.coords(o[1], 0, r, r, h - r)
        c.coords(o[2], w - r, r, w, h - r)
        if self.inner:
            i = self.inner
            c.coords(i[0], r, bw, w - r, h - bw)
            c.coords(i[1], bw, r, r, h - r)
            c.coords(i[2], w - r, r, w - bw, h - r)
        for item, (x, y) in zip(self.corners, ((0, 0), (w - r, 0), (0, h - r), (w - r, h - r))):
            c.coords(item, x, y)


# ----------------------------------------------------------------------
# karta (zaokrąglona sekcja)
# ----------------------------------------------------------------------
class RoundFrame(tk.Canvas):
    """Zaokrąglone tło z ramką ``inner`` na dzieci. Wysokość dopasowuje się do zawartości."""

    def __init__(self, parent, fill: str, page_bg: str, radius: float = 8, pad: float = 16,
                 outline: Optional[str] = None):
        # Wysokość startowa musi obejmować punkt wstawienia okna (pad) – inaczej Tk go nie mapuje
        # i nie powstaje zdarzenie <Configure>, od którego zależy dopasowanie wysokości.
        super().__init__(parent, background=page_bg, highlightthickness=0, borderwidth=0,
                         height=2 * px(pad) + px(40))
        self.fill, self.outline, self.radius, self.pad = fill, outline, px(radius), px(pad)
        self._shape = RoundRect(self, self.radius, fill, outline)
        self.inner = tk.Frame(self, background=fill)
        self._win = self.create_window(self.pad, self.pad, anchor="nw", window=self.inner)
        self._width = 0
        self.inner.bind("<Configure>", self._on_inner)
        self.bind("<Configure>", self._on_self)

    def _on_inner(self, e) -> None:
        h = e.height + 2 * self.pad  # wysokość ramki z zdarzenia – bez wymuszania przeliczania geometrii
        if int(self.cget("height")) != h:
            self.configure(height=h)

    def _on_self(self, e) -> None:
        if e.width != self._width:
            self._width = e.width
            self.itemconfigure(self._win, width=max(e.width - 2 * self.pad, 1))
        self._shape.resize(e.width, e.height)


class FLine(tk.Frame):
    """Cienka pozioma linia rozdzielająca (kolor obramowania motywu)."""

    def __init__(self, parent, pal: theme.Palette):
        super().__init__(parent, height=max(px(1), 1), background=pal.border)


# ----------------------------------------------------------------------
# przycisk
# ----------------------------------------------------------------------
class FButton(tk.Canvas):
    def __init__(self, parent, pal: theme.Palette, text: str, command: Optional[Callable] = None,
                 accent: bool = False, bg: Optional[str] = None, minwidth: int = 0, subtle: bool = False):
        self.pal, self.accent, self.command, self.subtle = pal, accent, command, subtle
        self._text, self._state, self._hover, self._down = text, "normal", False, False
        self._font = theme.F["bold"] if accent else theme.F["base"]
        w = max(self._font.measure(text) + px(40), px(minwidth))
        super().__init__(parent, width=w, height=px(34), background=bg or pal.card,
                         highlightthickness=0, borderwidth=0, cursor="hand2")
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<space>", lambda e: self._invoke())
        self.bind("<Return>", lambda e: self._invoke())
        self._paint()

    def _set(self, hover=None, down=None) -> None:
        if hover is not None:
            self._hover = hover
        if down is not None:
            self._down = down
        self._paint()

    def _release(self, e) -> None:
        was = self._down
        self._down = False
        self._paint()
        if was and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self._invoke()

    def _invoke(self) -> None:
        if self._state == "normal" and self.command:
            self.command()

    def _paint(self) -> None:
        p = self.pal
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self.cget("width")), int(self.cget("height"))
        disabled = self._state == "disabled"
        if self.accent:
            fill = p.ctrl_press if disabled else (p.accent_press if self._down else p.accent_hover if self._hover else p.accent)
            fg = p.muted if disabled else p.accent_fg
            outline = None
        elif self.subtle:
            fill = p.card if disabled else (p.ctrl_press if self._down else p.ctrl_hover if self._hover else p.card)
            fg = p.muted if disabled else p.fg
            outline = None
        else:
            fill = p.bg if disabled else (p.ctrl_press if self._down else p.ctrl_hover if self._hover else p.ctrl)
            fg = p.muted if disabled else p.fg
            outline = p.ctrl_border
        draw_round(self, 0, 0, w, h, px(4), fill, outline)
        self.create_text(w // 2, h // 2, text=self._text, fill=fg, font=self._font)
        self.configure(cursor="arrow" if disabled else "hand2")

    def configure(self, cnf=None, **kw):  # type: ignore[override]
        if cnf:
            kw.update(cnf)
        repaint = False
        for name in ("state", "text", "command"):
            if name in kw:
                value = kw.pop(name)
                if name == "state":
                    self._state = "disabled" if value == "disabled" else "normal"
                elif name == "text":
                    self._text = value
                    super().configure(width=max(self._font.measure(value) + px(40), 1))
                else:
                    self.command = value
                repaint = True
        if kw:
            super().configure(**kw)
        if repaint:
            self._paint()

    config = configure


# ----------------------------------------------------------------------
# pole wyboru / opcja
# ----------------------------------------------------------------------
def _check_image(p: theme.Palette, checked: bool, hover: bool, disabled: bool, card_bg: str):
    s = px(20)
    k = s / 20.0
    gap = px(10)  # przezroczysty odstęp między znacznikiem a tekstem
    if checked:
        fill = p.ctrl if disabled else (p.accent_hover if hover else p.accent)
        shapes = [(fill, _rrect(1 * k, 1 * k, 19 * k, 19 * k, 4 * k)),
                  (p.muted if disabled else p.accent_fg,
                   _stroke([(5.6 * k, 10.4 * k), (8.8 * k, 13.6 * k), (14.6 * k, 6.8 * k)], 1.9 * k))]
    else:
        border = p.border if disabled else p.check_border
        inner = p.ctrl_hover if (hover and not disabled) else card_bg
        shapes = [(border, _rrect(1 * k, 1 * k, 19 * k, 19 * k, 4 * k)),
                  (inner, _rrect(2.2 * k, 2.2 * k, 17.8 * k, 17.8 * k, 3 * k))]
    return render(("check", checked, hover, disabled, card_bg, p.name), s + gap, s, shapes)


def _radio_image(p: theme.Palette, checked: bool, hover: bool, disabled: bool, card_bg: str):
    s = px(20)
    k = s / 20.0
    gap = px(10)
    if checked:
        fill = p.ctrl if disabled else (p.accent_hover if hover else p.accent)
        # środek w kolorze tekstu na akcencie – jak w Windows 11
        shapes = [(fill, _circle(10 * k, 10 * k, 9 * k)),
                  (p.muted if disabled else p.accent_fg, _circle(10 * k, 10 * k, 4.6 * k))]
    else:
        border = p.border if disabled else p.check_border
        inner = p.ctrl_hover if (hover and not disabled) else card_bg
        shapes = [(border, _circle(10 * k, 10 * k, 9 * k)), (inner, _circle(10 * k, 10 * k, 8 * k))]
    return render(("radio", checked, hover, disabled, card_bg, p.name), s + gap, s, shapes)


class _Toggle(tk.Label):
    kind = "check"

    def __init__(self, parent, pal: theme.Palette, text: str, bg: Optional[str] = None):
        self.pal, self.card_bg = pal, bg or pal.card
        self._state, self._hover = "normal", False
        super().__init__(parent, text=text, background=self.card_bg, foreground=pal.fg, font=theme.F["base"],
                         compound="left", anchor="w", padx=0, pady=px(3), cursor="hand2", takefocus=1)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self._click())
        self.bind("<space>", lambda e: self._click())

    def _image(self, checked: bool):
        fn = _check_image if self.kind == "check" else _radio_image
        return fn(self.pal, checked, self._hover, self._state == "disabled", self.card_bg)

    def _set_hover(self, v: bool) -> None:
        self._hover = v
        self._refresh()

    def _checked(self) -> bool:  # nadpisywane
        return False

    def _click(self) -> None:
        if self._state != "disabled":
            self._toggle()

    def _toggle(self) -> None:
        pass

    def _refresh(self) -> None:
        disabled = self._state == "disabled"
        super().configure(image=self._image(self._checked()), foreground=self.pal.muted if disabled else self.pal.fg,
                          cursor="arrow" if disabled else "hand2")

    def configure(self, cnf=None, **kw):  # type: ignore[override]
        if cnf:
            kw.update(cnf)
        if "state" in kw:
            self._state = "disabled" if kw.pop("state") == "disabled" else "normal"
            self._refresh()
        if "style" in kw:
            kw.pop("style")
        if kw:
            super().configure(**kw)

    config = configure


class FCheck(_Toggle):
    kind = "check"

    def __init__(self, parent, pal, text: str, variable: tk.BooleanVar, bg: Optional[str] = None):
        super().__init__(parent, pal, text, bg)
        self.variable = variable
        self._trace = variable.trace_add("write", lambda *a: self._safe_refresh())
        self.bind("<Destroy>", lambda e: self._cleanup(e))
        self._refresh()

    def _cleanup(self, e) -> None:
        if e.widget is self:
            try:
                self.variable.trace_remove("write", self._trace)
            except (tk.TclError, ValueError):
                pass

    def _safe_refresh(self) -> None:
        try:
            self._refresh()
        except tk.TclError:
            pass

    def _checked(self) -> bool:
        return bool(self.variable.get())

    def _toggle(self) -> None:
        self.variable.set(not self.variable.get())


class FRadio(_Toggle):
    kind = "radio"

    def __init__(self, parent, pal, text: str, variable: tk.StringVar, value: str, bg: Optional[str] = None):
        super().__init__(parent, pal, text, bg)
        self.variable, self.value = variable, value
        self._trace = variable.trace_add("write", lambda *a: self._safe_refresh())
        self.bind("<Destroy>", lambda e: self._cleanup(e))
        self._refresh()

    def _cleanup(self, e) -> None:
        if e.widget is self:
            try:
                self.variable.trace_remove("write", self._trace)
            except (tk.TclError, ValueError):
                pass

    def _safe_refresh(self) -> None:
        try:
            self._refresh()
        except tk.TclError:
            pass

    def _checked(self) -> bool:
        return self.variable.get() == self.value

    def _toggle(self) -> None:
        self.variable.set(self.value)


# ----------------------------------------------------------------------
# lista wyboru (select) z rozwijanym oknem jak w Windows 11
# ----------------------------------------------------------------------
def app_is_active(widget: tk.Misc) -> bool:
    """Czy okno aktywne w systemie należy do tej aplikacji (Windows: GetForegroundWindow; inaczej fokus Tk)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            import os

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value == os.getpid()
        except Exception:  # noqa: BLE001
            pass
    return widget.focus_displayof() is not None


class _Flyout(tk.Toplevel):
    KEY = "#010203"  # kolor przezroczysty (Windows)

    def __init__(self, owner: "FSelect"):
        super().__init__(owner)
        self.owner, p = owner, owner.pal
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # Tło okna w kolorze obramowania. Zaokrąglenie narożników realizuje system (patrz _round_corners);
        # kolor przezroczysty (-transparentcolor) zostawiał czarne narożniki w jasnym motywie.
        outer_bg = p.flyout_border
        self.configure(background=outer_bg)
        self.item_h, self.margin = px(38), px(6)
        n = len(owner.values)
        self.w = max(owner.winfo_width(), px(160))
        self.h = n * self.item_h + 2 * self.margin + px(2)
        self.canvas = tk.Canvas(self, width=self.w, height=self.h, background=outer_bg, highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.hover = -1
        self._draw()
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(-1))
        self.canvas.bind("<Button-1>", self._click)
        self.bind("<Escape>", lambda e: self.close())
        self._closed = False
        self._binds: list = []
        # Okno bez ramki nie dostaje wiarygodnego <FocusOut>, więc zamykamy je jawnie:
        # kliknięcie poza listą, przesunięcie/zmiana rozmiaru/minimalizacja okna aplikacji
        # oraz utrata fokusu przez całą aplikację (przełączenie do innego programu).
        top = owner.winfo_toplevel()
        for seq, handler in (("<Button-1>", self._on_outside_click), ("<Configure>", self._on_top_change),
                             ("<Unmap>", self._on_top_change)):
            self._binds.append((top, seq, top.bind(seq, handler, add="+")))
        x = owner.winfo_rootx()
        y = owner.winfo_rooty() + owner.winfo_height() + px(2)
        if y + self.h > owner.winfo_screenheight() - px(40):
            y = owner.winfo_rooty() - self.h - px(2)
        self.geometry(f"{self.w}x{self.h}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()
        self._round_corners()
        self.after(300, self._watch_focus)

    def _round_corners(self) -> None:
        """Windows 11: natywne, wygładzone zaokrąglenie okna; starsze systemy: obcięcie regionem okna."""
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes

            self.update_idletasks()
            user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4) == 0:
                return
            region = gdi32.CreateRoundRectRgn(0, 0, self.w + 1, self.h + 1, 2 * px(8), 2 * px(8))
            user32.SetWindowRgn(hwnd, region, True)
        except Exception:  # noqa: BLE001
            pass

    def _on_outside_click(self, e) -> None:
        if self._closed:
            return
        try:
            inside = str(e.widget).startswith(str(self))
        except tk.TclError:
            inside = False
        if not inside:
            self.close()

    def _on_top_change(self, e) -> None:
        try:
            if e.widget is self.owner.winfo_toplevel():
                self.close()
        except tk.TclError:
            self.close()

    def _watch_focus(self) -> None:
        """Gdy użytkownik przeszedł do innej aplikacji – zamknij listę."""
        if self._closed:
            return
        try:
            if not app_is_active(self):
                self.close()
                return
            self.after(150, self._watch_focus)
        except tk.TclError:
            self.close()

    def _draw(self) -> None:
        p, c = self.owner.pal, self.canvas
        c.delete("all")
        draw_round(c, 0, 0, self.w, self.h, px(8), p.flyout, p.flyout_border, tag="bg")
        for i, text in enumerate(self.owner.values):
            y0 = self.margin + px(1) + i * self.item_h
            selected = i == self.owner.index
            if selected or i == self.hover:
                fill = p.nav_sel if selected else p.nav_hover
                draw_round(c, self.margin, y0, self.w - self.margin, y0 + self.item_h - px(2), px(4), fill, tag="row")
            if selected:
                draw_round(c, self.margin, y0 + px(9), self.margin + px(3), y0 + self.item_h - px(11), px(2), p.accent, tag="bar")
            c.create_text(self.margin + px(14), y0 + (self.item_h - px(2)) // 2, text=text, anchor="w",
                          fill=p.fg, font=theme.F["base"])

    def _index_at(self, y: int) -> int:
        i = (y - self.margin - px(1)) // self.item_h
        return int(i) if 0 <= i < len(self.owner.values) else -1

    def _motion(self, e) -> None:
        self._set_hover(self._index_at(e.y))

    def _set_hover(self, i: int) -> None:
        if i != self.hover:
            self.hover = i
            self._draw()

    def _click(self, e) -> None:
        i = self._index_at(e.y)
        if i >= 0:
            self.close()
            self.owner.select(i, notify=True)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.owner._flyout = None
        for widget, seq, funcid in self._binds:
            try:
                widget.unbind(seq, funcid)
            except tk.TclError:
                pass
        try:
            self.destroy()
        except tk.TclError:
            pass


class FSelect(tk.Canvas):
    def __init__(self, parent, pal: theme.Palette, values: Sequence[str], index: int = 0,
                 on_change: Optional[Callable[[int], None]] = None, bg: Optional[str] = None, width: int = 240):
        super().__init__(parent, width=px(width), height=px(34), background=bg or pal.card,
                         highlightthickness=0, borderwidth=0, cursor="hand2")
        self.pal, self.values, self.index, self.on_change = pal, list(values), index, on_change
        self._hover, self._state, self._flyout = False, "normal", None
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.open())
        self.bind("<Configure>", lambda e: self._paint())

    def _set_hover(self, v: bool) -> None:
        self._hover = v
        self._paint()

    def _paint(self) -> None:
        p = self.pal
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self.cget("width")), int(self.cget("height"))
        disabled = self._state == "disabled"
        fill = p.bg if disabled else (p.ctrl_hover if self._hover else p.ctrl)
        draw_round(self, 0, 0, w, h, px(4), fill, p.ctrl_border)
        text = self.values[self.index] if 0 <= self.index < len(self.values) else ""
        fg = p.muted if disabled else p.fg
        self.create_text(px(12), h // 2, text=text, anchor="w", fill=fg, font=theme.F["base"], width=w - px(46))
        cx, cy, d = w - px(18), h // 2, px(4)
        self.create_line(cx - d, cy - d // 2, cx, cy + d // 2 + 1, cx + d, cy - d // 2, fill=fg, width=max(px(1.6), 1),
                         capstyle="round", joinstyle="round")

    def open(self) -> None:
        if self._state == "disabled" or not self.values:
            return
        if self._flyout is not None:
            self._flyout.close()
            return
        self._flyout = _Flyout(self)

    def select(self, i: int, notify: bool = False) -> None:
        changed = i != self.index
        self.index = i
        self._paint()
        if notify and changed and self.on_change:
            self.on_change(i)

    def current(self, i: Optional[int] = None) -> int:
        if i is not None:
            self.select(i)
        return self.index

    def set_values(self, values: Sequence[str], index: int = 0) -> None:
        self.values = list(values)
        self.index = index
        self._paint()

    def configure(self, cnf=None, **kw):  # type: ignore[override]
        if cnf:
            kw.update(cnf)
        if "state" in kw:
            self._state = "disabled" if kw.pop("state") == "disabled" else "normal"
            self._paint()
        if kw:
            super().configure(**kw)

    config = configure


# ----------------------------------------------------------------------
# pole tekstowe
# ----------------------------------------------------------------------
class FEntry(tk.Canvas):
    def __init__(self, parent, pal: theme.Palette, textvariable: Optional[tk.StringVar] = None,
                 width: int = 260, bg: Optional[str] = None, show: str = ""):
        super().__init__(parent, width=px(width), height=px(36), background=bg or pal.card,
                         highlightthickness=0, borderwidth=0)
        self.pal, self._focus = pal, False
        self._shape = RoundRect(self, px(4), pal.input_fill, pal.ctrl_border)
        # linia akcentu przy fokusie – stały element, tylko pokazywany/ukrywany i przesuwany
        self._focus_line = self.create_line(0, 0, 0, 0, fill=pal.accent, width=px(2), state="hidden", tags="bg")
        self.entry = tk.Entry(self, textvariable=textvariable, relief="flat", borderwidth=0, highlightthickness=0,
                              background=pal.input_fill, foreground=pal.fg, insertbackground=pal.fg,
                              selectbackground=pal.accent, selectforeground=pal.accent_fg, font=theme.F["base"], show=show)
        self._win = self.create_window(px(10), px(18), anchor="w", window=self.entry)
        self._width = 0
        self.entry.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.entry.bind("<FocusOut>", lambda e: self._set_focus(False))
        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", lambda e: self.entry.focus_set())

    def _set_focus(self, v: bool) -> None:
        self._focus = v
        self.itemconfigure(self._focus_line, state="normal" if v else "hidden")

    def _on_configure(self, e) -> None:
        if e.width != self._width:
            self._width = e.width
            self.itemconfigure(self._win, width=max(e.width - px(20), 10))
        self._shape.resize(e.width, e.height)
        self.coords(self._focus_line, px(3), e.height - 1, e.width - px(3), e.height - 1)

    def focus_set(self) -> None:  # type: ignore[override]
        self.entry.focus_set()


# ----------------------------------------------------------------------
# pasek postępu
# ----------------------------------------------------------------------
class FProgress(tk.Canvas):
    def __init__(self, parent, pal: theme.Palette, bg: Optional[str] = None):
        super().__init__(parent, height=px(8), background=bg or pal.card, highlightthickness=0, borderwidth=0)
        self.pal, self._value, self._indeterminate, self._pos, self._job = pal, 0.0, False, 0.0, None
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<Destroy>", lambda e: self.stop() if e.widget is self else None)

    def set(self, frac: float) -> None:
        self.stop()
        self._value = max(0.0, min(frac, 1.0))
        self._paint()

    def start(self) -> None:
        if self._job is None:
            self._indeterminate = True
            self._tick()

    def stop(self) -> None:
        self._indeterminate = False
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def is_indeterminate(self) -> bool:
        return self._indeterminate

    def _tick(self) -> None:
        self._pos = (self._pos + 0.018) % 1.4
        self._paint()
        self._job = self.after(25, self._tick)

    def _paint(self) -> None:
        p = self.pal
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        y, t = h // 2, max(px(4), 2)
        self.create_line(t // 2, y, w - t // 2, y, fill=p.track, width=t, capstyle="round")
        if self._indeterminate:
            seg = w * 0.3
            x0 = max((self._pos - 0.3) * w, 0)
            x1 = min(self._pos * w, w)
            if x1 - x0 > t:
                self.create_line(x0 + t // 2, y, x1 - t // 2, y, fill=p.accent, width=t, capstyle="round")
        elif self._value > 0:
            x1 = max(self._value * w, t)
            self.create_line(t // 2, y, x1 - t // 2, y, fill=p.accent, width=t, capstyle="round")


# ----------------------------------------------------------------------
# odnośnik (bez podkreślenia, z zaokrąglonym tłem po najechaniu)
# ----------------------------------------------------------------------
class FLink(tk.Canvas):
    def __init__(self, parent, pal: theme.Palette, text: str, url: Optional[str] = None,
                 command: Optional[Callable] = None, bg: Optional[str] = None):
        self.pal, self.text, self.url, self.command, self._hover = pal, text, url, command, False
        font = theme.F["base"]
        super().__init__(parent, width=font.measure(text) + px(20), height=px(32), background=bg or pal.card,
                         highlightthickness=0, borderwidth=0, cursor="hand2")
        self._font = font
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Button-1>", lambda e: self._open())
        self.bind("<Configure>", lambda e: self._paint())

    def _set(self, v: bool) -> None:
        self._hover = v
        self._paint()

    def set_text(self, text: str) -> None:
        self.text = text
        super().configure(width=self._font.measure(text) + px(20))
        self._paint()

    def _open(self) -> None:
        if self.command:
            self.command()
        elif self.url:
            webbrowser.open(self.url)

    def _paint(self) -> None:
        p = self.pal
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self.cget("width")), int(self.cget("height"))
        if self._hover:
            draw_round(self, 0, 0, w, h, px(4), p.ctrl_hover if p.name == "dark" else p.nav_hover)
        self.create_text(w // 2, h // 2, text=self.text, fill=p.accent, font=self._font)


class FImageLink(tk.Canvas):
    """Klikalny obrazek (np. logo) z zaokrąglonym tłem po najechaniu."""

    def __init__(self, parent, pal: theme.Palette, image: tk.PhotoImage, url: str, bg: Optional[str] = None):
        pad = px(10)
        super().__init__(parent, width=image.width() + 2 * pad, height=image.height() + 2 * pad,
                         background=bg or pal.card, highlightthickness=0, borderwidth=0, cursor="hand2")
        self.pal, self.image, self.url, self.pad, self._hover = pal, image, url, pad, False
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Button-1>", lambda e: webbrowser.open(self.url))
        self.bind("<Configure>", lambda e: self._paint())

    def _set(self, v: bool) -> None:
        self._hover = v
        self._paint()

    def _paint(self) -> None:
        p = self.pal
        self.delete("all")
        w, h = int(self.cget("width")), int(self.cget("height"))
        if self._hover:
            draw_round(self, 0, 0, w, h, px(6), p.ctrl_hover if p.name == "dark" else p.nav_hover)
        self.create_image(w // 2, h // 2, image=self.image)


# ----------------------------------------------------------------------
# pozycja paska bocznego
# ----------------------------------------------------------------------
class NavItem(tk.Canvas):
    def __init__(self, parent, pal: theme.Palette, key: str, text: str, command: Callable,
                 icon: str = "", indent: int = 0, chevron: str = ""):
        super().__init__(parent, height=px(40), background=pal.bg, highlightthickness=0, borderwidth=0, cursor="hand2")
        self.pal, self.key, self.text, self.icon = pal, key, text, icon
        self.indent, self.chevron, self.selected, self._hover = indent, chevron, False, False
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Configure>", lambda e: self._paint())

    def _set(self, v: bool) -> None:
        self._hover = v
        self._paint()

    def set_selected(self, v: bool) -> None:
        self.selected = v
        self._paint()

    def set_chevron(self, text: str) -> None:
        self.chevron = text
        self._paint()

    def _paint(self) -> None:
        p = self.pal
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        if self.selected or self._hover:
            draw_round(self, 0, 0, w, h, px(5), p.nav_sel if self.selected else p.nav_hover)
        if self.selected:
            draw_round(self, 0, h // 2 - px(8), px(3), h // 2 + px(8), px(2), p.accent, tag="bar")
        x = px(16) + px(self.indent)
        if theme.ICON_FAMILY:
            self.create_text(x + px(10), h // 2, text=self.icon, fill=p.fg, font=theme.F["icon"])
        x += px(34)
        self.create_text(x, h // 2, text=self.text, fill=p.fg, font=theme.F["base"], anchor="w")
        if self.chevron:
            self.create_text(w - px(18), h // 2, text=self.chevron, fill=p.muted, font=theme.F["icon"])
