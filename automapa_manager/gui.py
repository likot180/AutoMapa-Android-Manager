"""Interfejs graficzny (Tkinter) w stylu Ustawień Windows 11."""
from __future__ import annotations

import contextlib
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any, Callable, Optional

from . import __version__, archive, backup, dialogs, install, maps, theme, widgets
from .adb import ROOT, Adb, AdbError, Cancelled, Device
from .config import Config
from .i18n import I18n
from .messages import translate_adb_message
from .widgets import (FButton, FCheck, FEntry, FImageLink, FLine, FLink, FProgress, FRadio, FSelect,
                      NavItem, RoundFrame, px)

ITEM_KEYS = [i.key for i in backup.ITEMS]
LANG_CODES = ["system", "pl", "en"]
THEME_CODES = ["system", "light", "dark"]
CONSOLE_CODES = ["on", "off"]
URL_OFFICIAL = "https://automapa.pl"
URL_OLDER = "https://apkpure.com/pl/automapa-offline-navigation/pl.aqurat.automapa/versions"
URL_MAPS = "https://www.automapa.pl/nawigacja/pobierz"
URL_AUTHOR = "https://likoton.pl"
URL_GITHUB = "https://github.com/likot180/AutoMapa-Android-Manager"
URL_BUYCOFFEE = "https://buycoffee.to/likoton"
URL_REVOLUT = "https://revolut.me/piotr7c5k"

# glify Segoe Fluent Icons / Segoe MDL2 Assets
ICONS = {
    "connection": "", "backup": "", "create": "", "restore": "",
    "install": "", "prog": "", "maps": "", "settings": "", "about": "",
    "chev_down": "", "chev_right": "",
}
PAGE_PARENT = {"create": "backup", "restore": "backup", "prog": "install", "maps": "install"}
PARENT_FIRST = {"backup": "create", "install": "prog"}
PARENT_CHILDREN = {"backup": ["create", "restore"], "install": ["prog", "maps"]}


class ScrollFrame(ttk.Frame):
    """Pionowo przewijana zawartość – nic nie jest ucinane w małym oknie."""

    def __init__(self, parent, bg: str, max_width: Optional[int] = None):
        super().__init__(parent)
        # max_width: treść nie rozciąga się ponad ten próg (jak w Ustawieniach Windows 11) – dzięki temu
        # powiększanie okna ponad próg nie wymaga ponownego układania całej strony.
        self.max_width = max_width
        self._width_job = None
        self._pending_width = 0
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=bg)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)

    def _on_scroll(self, lo, hi) -> None:
        self.vbar.set(lo, hi)
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.vbar.pack_forget()
        elif not self.vbar.winfo_ismapped():
            self.vbar.pack(side="right", fill="y")

    def _on_inner(self, _e=None) -> None:
        self.canvas.configure(scrollregion=(0, 0, self.inner.winfo_reqwidth(), self.inner.winfo_reqheight()))

    def _on_canvas(self, e) -> None:
        """Szerokość treści jest stosowana z opóźnieniem: podczas przeciągania krawędzi okna zdarzeń jest
        dziesiątki na sekundę, a każde wymusza ułożenie od nowa wszystkich kontrolek strony (to powodowało
        lag i artefakty). Treść zachowuje poprzedni układ, a nowy liczymy raz po zakończeniu zmiany."""
        width = min(e.width, self.max_width) if self.max_width else e.width
        self._pending_width = width
        if getattr(self, "_applied_width", None) is None:  # pierwszy układ – od razu
            self._flush_width()
            return
        if self._width_job is not None:
            self.after_cancel(self._width_job)
        self._width_job = self.after(110, self._flush_width)

    def _flush_width(self) -> None:
        self._width_job = None
        if self._pending_width != getattr(self, "_applied_width", None):
            self._applied_width = self._pending_width
            self.canvas.itemconfigure(self._win, width=self._pending_width)

    def can_scroll(self) -> bool:
        return self.inner.winfo_reqheight() > self.canvas.winfo_height()

    def scroll(self, units: int) -> None:
        if self.can_scroll():
            self.canvas.yview_scroll(units, "units")

    def to_top(self) -> None:
        self.canvas.yview_moveto(0)


# ----------------------------------------------------------------------
class App:
    def __init__(self, root: tk.Tk, cfg: Config, adb: Optional[Adb]):
        self.root, self.cfg, self.adb = root, cfg, adb
        self.i18n = I18n(cfg.language)
        self.t = self.i18n.t
        widgets.init_scale(root)

        # --- zmienne (przeżywają przebudowę interfejsu) ---
        self.mode = tk.StringVar(value="all")
        self.item_vars = {k: tk.BooleanVar(value=True) for k in ITEM_KEYS}
        self.size_vars = {k: tk.StringVar() for k in ITEM_KEYS + ["__all__"]}
        self.extra_var = tk.BooleanVar(value=True)
        default_dest = cfg.last_backup_dir or str(
            (Path.home() / "Documents") if (Path.home() / "Documents").exists() else Path.home()
        )
        self.dest_var = tk.StringVar(value=default_dest)
        self.r_file_var = tk.StringVar(value=cfg.last_restore_file)
        self.r_mode = tk.StringVar(value="all")
        self.r_item_vars = {k: tk.BooleanVar(value=True) for k in ITEM_KEYS}
        self.r_size_vars = {k: tk.StringVar() for k in ITEM_KEYS}
        self.r_extra_var = tk.BooleanVar(value=True)
        self.replace_var = tk.BooleanVar(value=True)
        self.apk_var = tk.StringVar(value=cfg.last_apk_file)
        self.map_file_var = tk.StringVar(value=cfg.last_map_file)
        self.map_name_var = tk.StringVar()
        self.restore_info = tk.StringVar()
        self.extra_info = tk.StringVar()
        self.apk_info = tk.StringVar()
        self.map_info = tk.StringVar()
        self.map_target = tk.StringVar()
        self.storage_note = tk.StringVar()

        # --- stan ---
        self.devices: list[Device] = []
        self.serial: Optional[str] = None
        self.dev_error: Optional[str] = None
        self.probe: dict[str, dict] = {}
        self.scan_result: Optional[backup.ScanResult] = None
        self.content: Optional[backup.ArchiveContent] = None
        self.storages: list[maps.Storage] = [maps.Storage("internal", "/sdcard")]
        self.storage_idx = 0
        self.busy = False
        self.cancel_event = threading.Event()
        self.log_lines: list[str] = []  # dziennik bieżącej (lub ostatniej) operacji
        self._op_title = ""
        self._op_status = ""
        self.page = "connection"
        self._wrapping: list = []
        self._wrap_job = None
        self._wrap_target = 0
        self._wrap_applied = None
        self._expanded = {"backup": False, "install": False}
        self._last_key = None
        self._queue: queue.Queue = queue.Queue()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._logo = None
        self._images: list = []
        self.pal = theme.apply(root, cfg.theme)
        theme.set_titlebar(root, self.pal.name == "dark")

        for v in (self.mode, self.extra_var, self.r_mode, *self.item_vars.values()):
            v.trace_add("write", lambda *a: self._refresh_states())
        self.apk_var.trace_add("write", lambda *a: self._on_apk_changed())
        self.map_file_var.trace_add("write", lambda *a: self._on_map_file_changed())
        self.map_name_var.trace_add("write", lambda *a: self._update_map_target())

        self._build()
        self._render_status()
        self._refresh_states()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind_all("<MouseWheel>", lambda e: self._on_wheel(-1 if e.delta > 0 else 1, e))
        root.bind_all("<Button-4>", lambda e: self._on_wheel(-1, e))
        root.bind_all("<Button-5>", lambda e: self._on_wheel(1, e))
        root.after(80, self._pump)
        self._monitor_thread = None
        if self.adb:
            self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
            self._monitor_thread.start()

    # ------------------------------------------------------------------
    # okna komunikatów w stylu aplikacji
    # ------------------------------------------------------------------
    def info(self, text: str, title: Optional[str] = None) -> None:
        dialogs.dialog(self, "info", title or self.t("info"), text, [(self.t("btn_ok"), True)])

    def warn(self, text: str, title: Optional[str] = None) -> None:
        dialogs.dialog(self, "warning", title or self.t("info"), text, [(self.t("btn_ok"), True)])

    def error(self, text: str) -> None:
        dialogs.dialog(self, "error", self.t("error"), text, [(self.t("btn_ok"), True)])

    def ask(self, text: str, title: Optional[str] = None, cancel: bool = False, kind: str = "question") -> Any:
        t = self.t
        buttons = [(t("btn_yes"), True), (t("btn_no"), False)]
        if cancel:
            buttons.append((t("btn_cancel"), None))
        return dialogs.dialog(self, kind, title or t("confirm"), text, buttons,
                              cancel_value=None if cancel else False)

    # ------------------------------------------------------------------
    # wątki -> UI
    # ------------------------------------------------------------------
    def post(self, fn: Callable, *args) -> None:
        self._queue.put((fn, args))

    def _pump(self) -> None:
        try:
            while True:
                fn, args = self._queue.get_nowait()
                try:
                    fn(*args)
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        if not self._stop.is_set():
            self.root.after(80, self._pump)

    def _on_wheel(self, units: int, e) -> None:
        if isinstance(e.widget, (tk.Text, tk.Listbox)):
            return  # własne przewijanie dziennika / listy rozwijanej
        sf = getattr(self, "scroll", None)
        if sf is not None and sf.winfo_exists():
            sf.scroll(units)

    def _on_close(self) -> None:
        t = self.t
        if self.busy and not self.ask(t("confirm_close")):
            return
        stop_adb = False
        if self.adb:
            answer = self.ask(t("confirm_close_adb"), cancel=True)
            if answer is None:
                return
            stop_adb = answer
        self._stop.set()
        self.cancel_event.set()
        self._wake.set()
        if self.adb:
            self.adb.kill_all()
            if stop_adb:
                if self._monitor_thread is not None:
                    self._monitor_thread.join(3)  # żeby monitor nie uruchomił serwera ponownie
                try:
                    self.adb.run(["kill-server"], timeout=10)
                except AdbError:
                    pass
        self.root.destroy()

    # ------------------------------------------------------------------
    # monitorowanie urządzeń
    # ------------------------------------------------------------------
    def _monitor(self) -> None:
        while not self._stop.is_set():
            try:
                devs, err = self.adb.devices(), None
            except AdbError as e:
                devs, err = [], str(e)
            self.post(self._on_devices, devs, err)
            self._wake.wait(2.5)
            self._wake.clear()

    def current_device(self) -> Optional[Device]:
        for d in self.devices:
            if d.serial == self.serial:
                return d
        return None

    def ready_device(self) -> Optional[Device]:
        d = self.current_device()
        return d if d and d.ready else None

    def _on_devices(self, devs: list, err: Optional[str]) -> None:
        self.devices, self.dev_error = devs, err
        serials = [d.serial for d in devs]
        if self.serial not in serials:
            pool = [d for d in devs if d.ready] or devs
            self.serial = pool[0].serial if pool else None
        dev = self.current_device()
        key = (dev.serial, dev.state) if dev else None
        if key != self._last_key:
            self._last_key = key
            self.scan_result = None
            if dev and dev.ready:
                threading.Thread(target=self._probe_worker, args=(dev.serial,), daemon=True).start()
            else:
                self._set_storages([maps.Storage("internal", "/sdcard")])
            self._update_size_labels()
        self._render_status()
        self._refresh_states()

    def _probe_worker(self, serial: str) -> None:
        try:
            info = self.adb.device_info(serial)
        except AdbError:
            info = {}
        self.post(self._on_probe, serial, info)
        self._scan_worker(serial)
        try:
            storages = maps.detect_storages(self.adb, serial)
        except AdbError:
            storages = [maps.Storage("internal", "/sdcard")]
        self.post(self._on_storages, serial, storages)

    def _scan_worker(self, serial: str) -> None:
        try:
            res = backup.scan(self.adb, serial)
        except (AdbError, OSError):
            res = None
        self.post(self._on_scan, serial, res)

    def _on_probe(self, serial: str, info: dict) -> None:
        self.probe[serial] = info
        self._render_status()

    def _on_scan(self, serial: str, res) -> None:
        if serial != self.serial:
            return
        self.scan_result = res
        self._update_size_labels(failed=res is None)
        self._refresh_states()

    def _on_storages(self, serial: str, storages: list) -> None:
        if serial == self.serial:
            self._set_storages(storages)

    def _rescan(self) -> None:
        dev = self.ready_device()
        if not dev or self.busy:
            return
        self.scan_result = None
        self._update_size_labels()
        threading.Thread(target=self._scan_worker, args=(dev.serial,), daemon=True).start()

    def _refresh_now(self) -> None:
        self._wake.set()
        self._rescan()

    # ------------------------------------------------------------------
    # szkielet interfejsu: pasek boczny + strony
    # ------------------------------------------------------------------
    def _build(self) -> None:
        t, p = self.t, self.pal
        for w in self.root.winfo_children():
            w.destroy()
        self._wrapping = []
        self._wrap_applied = None  # nowe etykiety muszą dostać zawijanie przy pierwszym układzie
        self.root.title(t("app_title"))
        for parent, children in PARENT_CHILDREN.items():
            self._expanded[parent] = self.page in children

        body = tk.Frame(self.root, background=p.bg)
        body.pack(fill="both", expand=True)
        self._body = body
        sidebar = tk.Frame(body, background=p.bg, width=px(290))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)
        self._build_sidebar(sidebar)

        self.scroll = ScrollFrame(content, p.bg, max_width=px(1120))
        self.scroll.pack(fill="both", expand=True)
        self._build_footer(content)
        container = ttk.Frame(self.scroll.inner, padding=(px(36), px(26), px(36), px(26)))
        container.pack(fill="both", expand=True)
        container.bind("<Configure>", lambda e: self._on_container_width(e.width))

        self.pages: dict[str, ttk.Frame] = {}
        builders = {
            "connection": self._build_connection,
            "create": self._build_create,
            "restore": self._build_restore,
            "prog": self._build_prog,
            "maps": self._build_maps,
            "settings": self._build_settings,
            "about": self._build_about,
        }
        for key, builder in builders.items():
            frame = ttk.Frame(container)
            self.pages[key] = frame
            builder(frame)
        self._show_page(self.page)
        self._update_size_labels()
        self._update_restore_labels()
        self._on_apk_changed()
        self._on_map_file_changed()
        self._apply_minsize()
        if self.busy:  # przebudowa interfejsu w trakcie operacji (nie powinna się zdarzać) – zachowaj stopkę
            self._show_footer()

    # ------------------------------------------------------------------
    # stopka z bieżącą operacją (widoczna na każdej stronie, gdy coś trwa)
    # ------------------------------------------------------------------
    def _build_footer(self, parent) -> None:
        """Pasek postępu na dole kolumny treści (obok przycisków Ustawienia i O programie w panelu bocznym).
        Pojawia się tylko podczas operacji; dziennik (jeśli włączony) jest w nim, nie na stronach."""
        t, p = self.t, self.pal
        self._footer_job = None
        self.footer = tk.Frame(parent, background=p.bg)
        card = RoundFrame(self.footer, p.card, p.bg, radius=8, pad=16)
        card.pack(fill="x", padx=px(36), pady=(0, px(14)))
        self._footer_card = card
        self._footer_right = -1
        self.footer.bind("<Configure>", lambda e: self._fit_footer())
        self.scroll.canvas.bind("<Configure>", lambda e: self._fit_footer(), add=True)
        inner = card.inner
        inner.columnconfigure(0, weight=1)
        self.footer_title = ttk.Label(inner, style="CardH3.TLabel", text=self._op_title)
        self.footer_title.grid(row=0, column=0, sticky="w")
        self.footer_toggle: Optional[FLink] = None
        self.footer_log: Optional[tk.Text] = None
        self.footer_logbox: Optional[RoundFrame] = None
        if self.cfg.console == "on":
            self.footer_toggle = FLink(inner, p, "", command=self._toggle_log, bg=p.card)
            self.footer_toggle.grid(row=0, column=1, sticky="e")
        self.footer_bar = FProgress(inner, p, bg=p.card)
        self.footer_bar.grid(row=1, column=0, sticky="ew", pady=(px(10), px(4)))
        self.footer_cancel = self._btn(inner, t("btn_cancel"), lambda: self.cancel_event.set(), minwidth=100)
        self.footer_cancel.grid(row=1, column=1, rowspan=2, padx=(px(14), 0))
        st = tk.Frame(inner, background=p.card)
        st.grid(row=2, column=0, sticky="ew")
        self.footer_pct = ttk.Label(st, style="CardMuted.TLabel", width=5, anchor="e")
        self.footer_pct.pack(side="right")
        self.footer_status = ttk.Label(st, style="CardMuted.TLabel", anchor="w", width=1, text=self._op_status)
        self.footer_status.pack(side="left", fill="x", expand=True)
        if self.cfg.console == "on":
            self.footer_logbox = RoundFrame(inner, p.input_fill, p.card, radius=6, pad=8)
            self.footer_logbox.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(10), 0))
            box = self.footer_logbox.inner
            box.columnconfigure(0, weight=1)
            self.footer_log = tk.Text(box, height=7, wrap="word", state="disabled", relief="flat", borderwidth=0,
                                      highlightthickness=0, background=p.input_fill, foreground=p.fg,
                                      insertbackground=p.fg, font=theme.F["mono"], padx=4, pady=2,
                                      selectbackground=p.accent, selectforeground=p.accent_fg)
            self.footer_log.grid(row=0, column=0, sticky="ew")
            sb = ttk.Scrollbar(box, orient="vertical", command=self.footer_log.yview)
            sb.grid(row=0, column=1, sticky="ns")
            self.footer_log.configure(yscrollcommand=sb.set)
            if self.log_lines:
                self.footer_log.configure(state="normal")
                self.footer_log.insert("end", "\n".join(self.log_lines) + "\n")
                self.footer_log.configure(state="disabled")
                self.footer_log.see("end")
            self._apply_log_collapsed()

    def _fit_footer(self) -> None:
        """Pasek ma tę samą szerokość co karty na stronie: bez paska przewijania i nie szerzej niż treść."""
        total = self.footer.winfo_width()
        view = self.scroll.canvas.winfo_width()
        if total <= 1 or view <= 1:
            return
        right = px(36) + max(0, total - min(view, px(1120)))
        if right != self._footer_right:
            self._footer_right = right
            self._footer_card.pack_configure(padx=(px(36), right))

    def _apply_log_collapsed(self) -> None:
        if self.footer_logbox is None or self.footer_toggle is None:
            return
        if self.cfg.console_collapsed == "1":
            self.footer_logbox.grid_remove()
            self.footer_toggle.set_text(self.t("console_show"))
        else:
            self.footer_logbox.grid()
            self.footer_toggle.set_text(self.t("console_hide"))

    def _toggle_log(self) -> None:
        self.cfg.console_collapsed = "0" if self.cfg.console_collapsed == "1" else "1"
        self.cfg.save()
        self._apply_log_collapsed()

    def _schedule_footer(self, title: str) -> None:
        """Pokazuje stopkę dopiero, gdy operacja trwa dłużej niż chwilę (krótkie nie powinny jej migać)."""
        self._op_title = self._op_status = title
        self.footer_title.configure(text=title)
        self.footer_status.configure(text=title)
        self.footer_pct.configure(text="")
        if self._footer_job is not None:
            self.root.after_cancel(self._footer_job)
        self._footer_job = self.root.after(400, self._show_footer)

    def _show_footer(self) -> None:
        self._footer_job = None
        if self.busy and not self.footer.winfo_ismapped():
            self.footer_bar.start()
            self.footer.pack(side="bottom", fill="x", before=self.scroll)

    def _hide_footer(self) -> None:
        if self._footer_job is not None:
            self.root.after_cancel(self._footer_job)
            self._footer_job = None
        self.footer_bar.stop()
        self.footer.pack_forget()

    def _apply_minsize(self) -> None:
        """Minimalna wysokość okna = wysokość paska bocznego przy rozwiniętych wszystkich grupach."""
        self.root.update_idletasks()
        sub_keys = {c for children in PARENT_CHILDREN.values() for c in children}
        gap = 2 * px(1)
        need = self._side_head.winfo_reqheight() + px(22) + px(14)
        for key, wrap in self.nav_wrap.items():
            if key in sub_keys:
                continue  # liczone razem z grupą nadrzędną
            extra = px(1) + px(16) if key == "about" else gap
            need += wrap.winfo_reqheight() + extra
            if key in PARENT_CHILDREN:  # podpozycje liczymy, nawet gdy grupa jest zwinięta
                need += sum(self.nav_wrap[c].winfo_reqheight() + gap for c in PARENT_CHILDREN[key])
        need += px(12)
        min_w = self.root.minsize()[0] or px(980)
        self.root.minsize(min_w, max(need, px(480)))

    def _build_sidebar(self, sb: tk.Frame) -> None:
        t, p = self.t, self.pal
        head = tk.Frame(sb, background=p.bg)
        head.pack(fill="x", padx=px(20), pady=(px(22), px(14)))
        self._side_head = head
        try:
            self._logo = tk.PhotoImage(file=str(ROOT / "assets" / "icon-48.png"))
            tk.Label(head, image=self._logo, background=p.bg).pack(side="left", padx=(0, px(12)))
        except tk.TclError:
            pass
        titles = tk.Frame(head, background=p.bg)
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text=t("app_title"), font=theme.F["h3"], background=p.bg, foreground=p.fg,
                 anchor="w", justify="left", wraplength=px(185)).pack(fill="x")
        status = tk.Frame(titles, background=p.bg)
        status.pack(fill="x", pady=(px(3), 0))
        self.side_dot = tk.Label(status, background=p.bg, borderwidth=0)
        self.side_dot.pack(side="left", padx=(0, px(7)))
        self.side_dev = tk.Label(status, text="", font=theme.F["small"], background=p.bg,
                                 foreground=p.muted, anchor="w")
        self.side_dev.pack(side="left")

        self.nav: dict[str, NavItem] = {}
        self.nav_wrap: dict[str, tk.Frame] = {}
        self.sub_frames: dict[str, tk.Frame] = {}

        def add(parent, key, text_key, command, indent=0, chevron="", side="top", pady=None):
            wrap = tk.Frame(parent, background=p.bg)
            wrap.pack(fill="x", padx=px(10), pady=pady if pady is not None else px(1), side=side)
            item = NavItem(wrap, p, key, t(text_key), command, ICONS.get(key, ""), indent, chevron)
            item.pack(fill="x")
            self.nav[key], self.nav_wrap[key] = item, wrap
            return item

        # na dole (od dołu): O programie, a nad nim Ustawienia; odstęp od dolnej krawędzi okna
        add(sb, "about", "nav_about", lambda: self._show_page("about"), side="bottom", pady=(px(1), px(16)))
        add(sb, "settings", "nav_settings", lambda: self._show_page("settings"), side="bottom")
        add(sb, "connection", "nav_connection", lambda: self._show_page("connection"))
        for parent, children in PARENT_CHILDREN.items():
            chev = ""
            if theme.ICON_FAMILY:
                chev = ICONS["chev_down"] if self._expanded[parent] else ICONS["chev_right"]
            add(sb, parent, f"nav_{parent}", lambda pr=parent: self._toggle_parent(pr), chevron=chev)
            sub = tk.Frame(sb, background=p.bg)
            self.sub_frames[parent] = sub
            for child in children:
                key_text = f"nav_{child}" if parent == "backup" else f"nav_install_{child}"
                add(sub, child, key_text, lambda c=child: self._show_page(c), indent=24)
            if self._expanded[parent]:
                sub.pack(fill="x")

    def _set_parent_state(self, parent: str, expanded: bool) -> None:
        self._expanded[parent] = expanded
        sub = self.sub_frames[parent]
        if expanded:
            sub.pack(fill="x", after=self.nav_wrap[parent])
        else:
            sub.pack_forget()
        if theme.ICON_FAMILY:
            self.nav[parent].set_chevron(ICONS["chev_down"] if expanded else ICONS["chev_right"])

    def _toggle_parent(self, parent: str) -> None:
        if self._expanded[parent] and self.page in PARENT_CHILDREN[parent]:
            self._set_parent_state(parent, False)
        else:
            self._set_parent_state(parent, True)
            if self.page not in PARENT_CHILDREN[parent]:
                self._show_page(PARENT_FIRST[parent])

    def _show_page(self, key: str) -> None:
        self.page = key
        for frame in self.pages.values():
            frame.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for k, item in self.nav.items():
            item.set_selected(k == key)
        parent = PAGE_PARENT.get(key)
        if parent and not self._expanded[parent]:
            self._set_parent_state(parent, True)
        self.scroll.to_top()
        self.root.after(30, lambda: self.scroll.winfo_exists() and self.scroll._on_inner())

    def _on_container_width(self, width: int) -> None:
        """Zawijanie etykiet zależy od szerokości strony. Zdarzeń jest dużo podczas zmiany rozmiaru okna,
        więc łączymy je w jedno przeliczenie wykonywane, gdy kolejka zdarzeń się opróżni."""
        self._wrap_target = max(width - 2 * px(36) - 2 * px(16) - px(6), 320)
        if self._wrap_job is None:
            self._wrap_job = self.root.after_idle(self._apply_wrap)

    def _apply_wrap(self) -> None:
        self._wrap_job = None
        wrap = self._wrap_target
        if wrap == self._wrap_applied:
            return
        self._wrap_applied = wrap
        for lab in self._wrapping:
            try:
                lab.configure(wraplength=wrap)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # pomocnicze budowanie kart i kontrolek
    # ------------------------------------------------------------------
    def _title(self, page, key: str) -> None:
        ttk.Label(page, text=self.t(key), style="H1.TLabel").pack(anchor="w", pady=(0, px(18)))

    def _card(self, parent, pady=(0, 12)) -> tk.Frame:
        rf = RoundFrame(parent, self.pal.card, self.pal.bg, radius=8, pad=16)
        rf.pack(fill="x", pady=(px(pady[0]), px(pady[1])))
        rf.inner.columnconfigure(0, weight=1)
        return rf.inner

    def _wl(self, parent, text="", style="Card.TLabel", **kw) -> ttk.Label:
        lab = ttk.Label(parent, text=text, style=style, justify="left", **kw)
        self._wrapping.append(lab)
        return lab

    def _btn(self, parent, text: str, command: Callable, accent: bool = False, bg: Optional[str] = None,
             minwidth: int = 0) -> FButton:
        return FButton(parent, self.pal, text, command, accent=accent, bg=bg or self.pal.card, minwidth=minwidth)

    def _radio(self, parent, text: str, var: tk.StringVar, value: str) -> FRadio:
        return FRadio(parent, self.pal, text, var, value, bg=self.pal.card)

    def _check(self, parent, text: str, var: tk.BooleanVar) -> FCheck:
        return FCheck(parent, self.pal, text, var, bg=self.pal.card)

    def _path_row(self, parent, row: int, var: tk.StringVar, browse: Callable) -> tk.Frame:
        frame = tk.Frame(parent, background=self.pal.card)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        frame.columnconfigure(0, weight=1)
        FEntry(frame, self.pal, var, bg=self.pal.card).grid(row=0, column=0, sticky="ew")
        self._btn(frame, self.t("btn_browse"), browse).grid(row=0, column=1, padx=(px(8), 0))
        return frame

    def _sep(self, parent, row: int, span: int = 2, pady=(12, 12)) -> None:
        FLine(parent, self.pal).grid(row=row, column=0, columnspan=span, sticky="ew", pady=(px(pady[0]), px(pady[1])))

    # ------------------------------------------------------------------
    # strona: Połączenie
    # ------------------------------------------------------------------
    def _build_connection(self, page) -> None:
        t, p = self.t, self.pal
        self._title(page, "page_connection")
        card = self._card(page)
        self.status_title = ttk.Label(card, style="Title.TLabel")
        self.status_title.grid(row=0, column=0, sticky="w")
        self.status_detail = self._wl(card)
        self.status_detail.grid(row=1, column=0, sticky="w", pady=(px(6), 0))
        self.status_wifi = self._wl(card, style="CardMuted.TLabel")
        self.status_wifi.grid(row=2, column=0, sticky="w", pady=(px(6), 0))
        self.dev_row = tk.Frame(card, background=p.card)
        self.dev_row.grid(row=3, column=0, sticky="ew", pady=(px(10), 0))
        ttk.Label(self.dev_row, text=t("device_label"), style="Card.TLabel").pack(side="left")
        self.dev_select = FSelect(self.dev_row, p, [], 0, on_change=self._on_dev_selected, bg=p.card, width=420)
        self.dev_select.pack(side="left", padx=px(10))
        btns = tk.Frame(card, background=p.card)
        btns.grid(row=4, column=0, sticky="w", pady=(px(16), 0))
        self.btn_refresh = self._btn(btns, t("btn_refresh"), self._refresh_now, accent=True, minwidth=110)
        self.btn_wifi = self._btn(btns, t("btn_wifi"), self._open_wifi)
        self.btn_disable = self._btn(btns, t("btn_disable"), self._open_disable)
        for i, b in enumerate((self.btn_refresh, self.btn_wifi, self.btn_disable)):
            b.pack(side="left", padx=(0 if i == 0 else px(8), 0))

        self.instr_holder = tk.Frame(page, background=p.bg)
        self.instr_card = self._card(self.instr_holder)
        ttk.Label(self.instr_card, text=t("instr_title"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w")
        self._wl(self.instr_card, t("st_nodev_detail")).grid(row=1, column=0, sticky="w", pady=(px(8), px(12)))
        FLine(self.instr_card, p).grid(row=2, column=0, sticky="ew")
        ttk.Label(self.instr_card, text=t("instr_wifi_title"), style="CardH3.TLabel").grid(
            row=3, column=0, sticky="w", pady=(px(12), 0))
        self._wl(self.instr_card, t("st_nodev_wifi")).grid(row=4, column=0, sticky="w", pady=(px(8), 0))

    # ------------------------------------------------------------------
    # strona: Utwórz kopię zapasową
    # ------------------------------------------------------------------
    def _build_create(self, page) -> None:
        t, p = self.t, self.pal
        self._title(page, "page_create")
        card = self._card(page)
        ttk.Label(card, text=t("grp_backup"), style="CardH3.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, px(6)))
        r = 1
        self._radio(card, t("rb_all"), self.mode, "all").grid(row=r, column=0, sticky="w")
        ttk.Label(card, textvariable=self.size_vars["__all__"], style="CardMuted.TLabel").grid(row=r, column=1, sticky="e")
        r += 1
        self._radio(card, t("rb_selected"), self.mode, "selected").grid(row=r, column=0, sticky="w", pady=(px(4), 0))
        self.item_checks = {}
        for item in backup.ITEMS:
            r += 1
            cb = self._check(card, f"{t('item_' + item.key)}   ({item.name})", self.item_vars[item.key])
            cb.grid(row=r, column=0, sticky="w", padx=(px(30), 0))
            ttk.Label(card, textvariable=self.size_vars[item.key], style="CardMuted.TLabel").grid(row=r, column=1, sticky="e")
            self.item_checks[item.key] = cb
        r += 1
        self._sep(card, r)
        r += 1
        self.extra_chk = self._check(card, t("chk_extra"), self.extra_var)
        self.extra_chk.grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._wl(card, style="CardMuted.TLabel", textvariable=self.extra_info).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._wl(card, t("extra_hint"), "CardMuted.TLabel").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._sep(card, r)
        r += 1
        self._wl(card, t("sysprefs_note"), "CardMuted.TLabel").grid(row=r, column=0, columnspan=2, sticky="w")

        dest = self._card(page)
        ttk.Label(dest, text=t("grp_dest"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w", pady=(0, px(8)))
        self._path_row(dest, 1, self.dest_var, self._browse_dest)
        self.format_label = ttk.Label(dest, style="CardMuted.TLabel")
        self.format_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(px(8), 0))
        self._update_format_label()

        bar = tk.Frame(page, background=p.bg)
        bar.pack(fill="x", pady=(px(2), px(14)))
        self.btn_backup = self._btn(bar, t("btn_backup"), self._on_backup, accent=True, bg=p.bg, minwidth=120)
        self.btn_backup.pack(side="left")
        self.btn_rescan = self._btn(bar, t("btn_rescan"), self._rescan, bg=p.bg)
        self.btn_rescan.pack(side="left", padx=px(8))

    # ------------------------------------------------------------------
    # strona: Przywróć kopię zapasową
    # ------------------------------------------------------------------
    def _build_restore(self, page) -> None:
        t, p = self.t, self.pal
        self._title(page, "page_restore")
        card = self._card(page)
        ttk.Label(card, text=t("lbl_archive"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w", pady=(0, px(8)))
        frame = self._path_row(card, 1, self.r_file_var, self._browse_archive)
        self.btn_load = self._btn(frame, t("btn_load"), self._load_archive)
        self.btn_load.grid(row=0, column=2, padx=(px(8), 0))
        self._wl(card, style="CardMuted.TLabel", textvariable=self.restore_info).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(px(10), 0))

        items = self._card(page)
        r = 0
        self._radio(items, t("rb_r_all"), self.r_mode, "all").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._radio(items, t("rb_r_sel"), self.r_mode, "selected").grid(row=r, column=0, columnspan=2, sticky="w", pady=(px(4), 0))
        self.r_checks = {}
        for item in backup.ITEMS:
            r += 1
            cb = self._check(items, f"{t('item_' + item.key)}   ({item.name})", self.r_item_vars[item.key])
            cb.grid(row=r, column=0, sticky="w", padx=(px(30), 0))
            ttk.Label(items, textvariable=self.r_size_vars[item.key], style="CardMuted.TLabel").grid(row=r, column=1, sticky="e")
            self.r_checks[item.key] = cb
        r += 1
        self._sep(items, r)
        r += 1
        self.r_extra_chk = self._check(items, t("chk_r_extra"), self.r_extra_var)
        self.r_extra_chk.grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._check(items, t("chk_replace"), self.replace_var).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._sep(items, r)
        r += 1
        self._wl(items, t("sysprefs_note"), "CardMuted.TLabel").grid(row=r, column=0, columnspan=2, sticky="w")

        bar = tk.Frame(page, background=p.bg)
        bar.pack(fill="x", pady=(px(2), px(14)))
        self.btn_restore = self._btn(bar, t("btn_restore"), self._on_restore, accent=True, bg=p.bg, minwidth=120)
        self.btn_restore.pack(side="left")

    # ------------------------------------------------------------------
    # strona: Instalacja programu (APK)
    # ------------------------------------------------------------------
    def _build_prog(self, page) -> None:
        t, p = self.t, self.pal
        self._title(page, "page_prog")
        info = self._card(page)
        self._wl(info, t("inst_official_text")).grid(row=0, column=0, sticky="w")
        FLink(info, p, "automapa.pl", URL_OFFICIAL, bg=p.card).grid(row=1, column=0, sticky="w", pady=(px(2), px(8)))
        self._wl(info, t("inst_older_text")).grid(row=2, column=0, sticky="w")
        FLink(info, p, "apkpure.com", URL_OLDER, bg=p.card).grid(row=3, column=0, sticky="w", pady=(px(2), px(4)))
        self._wl(info, t("inst_older_warning"), "CardMuted.TLabel").grid(row=4, column=0, sticky="w")

        card = self._card(page)
        ttk.Label(card, text=t("inst_apk"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w", pady=(0, px(8)))
        self._path_row(card, 1, self.apk_var, self._browse_apk)
        self._wl(card, style="CardMuted.TLabel", textvariable=self.apk_info).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(px(10), 0))
        self._wl(card, t("inst_overwrite"), "CardMuted.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(px(6), 0))

        bar = tk.Frame(page, background=p.bg)
        bar.pack(fill="x", pady=(px(2), px(14)))
        self.btn_install = self._btn(bar, t("btn_install"), self._on_install, accent=True, bg=p.bg, minwidth=120)
        self.btn_install.pack(side="left")

    # ------------------------------------------------------------------
    # strona: Wgrywanie map
    # ------------------------------------------------------------------
    def _build_maps(self, page) -> None:
        t, p = self.t, self.pal
        self._title(page, "page_maps")
        info = self._card(page)
        self._wl(info, t("maps_official")).grid(row=0, column=0, sticky="w")
        FLink(info, p, t("maps_link_text"), URL_MAPS, bg=p.card).grid(row=1, column=0, sticky="w", pady=(px(2), 0))
        self._wl(info, t("maps_compat_note"), "CardMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(px(8), 0))

        card = self._card(page)
        ttk.Label(card, text=t("maps_file"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w", pady=(0, px(8)))
        self._path_row(card, 1, self.map_file_var, self._browse_map)
        self._wl(card, style="CardMuted.TLabel", textvariable=self.map_info).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(px(10), 0))

        st = self._card(page)
        ttk.Label(st, text=t("maps_storage"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w", pady=(0, px(8)))
        self.storage_select = FSelect(st, p, self._storage_labels(), self.storage_idx,
                                      on_change=self._on_storage_selected, bg=p.card, width=460)
        self.storage_select.grid(row=1, column=0, sticky="w")
        self._wl(st, style="CardMuted.TLabel", textvariable=self.storage_note).grid(
            row=2, column=0, sticky="w", pady=(px(8), 0))

        dest = self._card(page)
        ttk.Label(dest, text=t("maps_dest"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w", pady=(0, px(8)))
        self._wl(dest, style="Card.TLabel", textvariable=self.map_target).grid(row=1, column=0, sticky="w")
        self._wl(dest, t("maps_replace_warn"), "CardMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(px(6), 0))

        bar = tk.Frame(page, background=p.bg)
        bar.pack(fill="x", pady=(px(2), px(14)))
        self.btn_maps = self._btn(bar, t("btn_maps_install"), self._on_install_map, accent=True, bg=p.bg, minwidth=120)
        self.btn_maps.pack(side="left")

    # ------------------------------------------------------------------
    # strona: Ustawienia
    # ------------------------------------------------------------------
    def _setting_row(self, card, row: int, title: str, desc: str, make_control: Callable, last=False) -> None:
        text = tk.Frame(card, background=self.pal.card)
        text.grid(row=row * 2, column=0, sticky="w", pady=px(6))
        ttk.Label(text, text=title, style="Card.TLabel").pack(anchor="w")
        ttk.Label(text, text=desc, style="CardMuted.TLabel").pack(anchor="w")
        make_control(card).grid(row=row * 2, column=1, sticky="e", padx=(px(16), 0))
        if not last:
            FLine(card, self.pal).grid(row=row * 2 + 1, column=0, columnspan=2, sticky="ew", pady=px(4))

    def _build_settings(self, page) -> None:
        t, p = self.t, self.pal
        self._title(page, "page_settings")
        card = self._card(page)

        def select(values, current, handler):
            return lambda parent: FSelect(parent, p, values, current, on_change=handler, bg=p.card, width=250)

        langs = [t("opt_system"), t("opt_pl"), t("opt_en")]
        themes = [t("opt_system"), t("theme_light"), t("theme_dark")]
        self._fmt_codes = ["auto"] + archive.available_formats()
        fmts = [t("fmt_auto", fmt=archive.resolve_format("auto"))] + archive.available_formats()
        consoles = [t("opt_on"), t("opt_off")]
        idx = lambda codes, value: codes.index(value) if value in codes else 0
        self._setting_row(card, 0, t("lbl_language").rstrip(":"), t("set_language_desc"),
                          select(langs, idx(LANG_CODES, self.cfg.language), self._on_lang))
        self._setting_row(card, 1, t("lbl_theme").rstrip(":"), t("set_theme_desc"),
                          select(themes, idx(THEME_CODES, self.cfg.theme), self._on_theme))
        self._setting_row(card, 2, t("lbl_arch_format").rstrip(":"), t("set_format_desc"),
                          select(fmts, idx(self._fmt_codes, self.cfg.archive_format), self._on_fmt))
        self._setting_row(card, 3, t("set_console"), t("set_console_desc"),
                          select(consoles, idx(CONSOLE_CODES, self.cfg.console), self._on_console), last=True)

        adb_card = self._card(page)
        ttk.Label(adb_card, text=t("grp_adb"), style="CardH3.TLabel").grid(row=0, column=0, sticky="w")
        path = self.adb.path if self.adb else t("adb_not_found")
        ver = self.adb.version() if self.adb else ""
        self._wl(adb_card, f"{path}" + (f"  (v{ver})" if ver else ""), "CardMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(px(6), 0))

    # ------------------------------------------------------------------
    # strona: O programie
    # ------------------------------------------------------------------
    def _build_about(self, page) -> None:
        t, p = self.t, self.pal
        self._title(page, "page_about")
        card = self._card(page)
        head = tk.Frame(card, background=p.card)
        head.grid(row=0, column=0, columnspan=2, sticky="w")
        try:
            img = tk.PhotoImage(file=str(ROOT / "assets" / "icon-48.png"))
            self._images.append(img)
            tk.Label(head, image=img, background=p.card).pack(side="left", padx=(0, px(14)))
        except tk.TclError:
            pass
        names = tk.Frame(head, background=p.card)
        names.pack(side="left")
        ttk.Label(names, text=t("app_title"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(names, text=t("about_third"), style="CardMuted.TLabel").pack(anchor="w")
        self._sep(card, 1, pady=(14, 8))

        ver = self.adb.version() if self.adb else ""
        rows = [
            (t("about_version"), lambda par: ttk.Label(par, text=__version__, style="Card.TLabel")),
            (t("about_adb"), lambda par: ttk.Label(par, text=ver or "–", style="Card.TLabel")),
            (t("about_7zip"), lambda par: ttk.Label(par, text=archive.sevenzip_version() or "–", style="Card.TLabel")),
            (t("about_author"), lambda par: self._author_cell(par)),
            (t("about_license"), lambda par: self._license_cell(par)),
            (t("about_source"), lambda par: FLink(par, p, "github.com/likot180/AutoMapa-Android-Manager", URL_GITHUB, bg=p.card)),
        ]
        for i, (label, make) in enumerate(rows):
            r = 2 + i
            ttk.Label(card, text=label, style="CardMuted.TLabel").grid(row=r, column=0, sticky="w", pady=px(5))
            make(card).grid(row=r, column=1, sticky="e")

        donate = self._card(page)
        self._wl(donate, t("about_donate")).grid(row=0, column=0, sticky="w")
        logos = tk.Frame(donate, background=p.card)
        logos.grid(row=1, column=0, sticky="w", pady=(px(8), px(4)))
        size = 60 if widgets._scale >= 1.4 else 40
        for name, url in (("buycoffee", URL_BUYCOFFEE), ("revolut", URL_REVOLUT)):
            try:
                img = tk.PhotoImage(file=str(ROOT / "assets" / f"{name}-{p.name}-{size}.png"))
            except tk.TclError:
                continue
            self._images.append(img)
            FImageLink(logos, p, img, url, bg=p.card).pack(side="left", padx=(0, px(14)))
        ttk.Label(donate, text=t("about_thanks"), style="CardBold.TLabel").grid(row=2, column=0, sticky="w", pady=(px(4), 0))

    def _author_cell(self, parent):
        f = tk.Frame(parent, background=self.pal.card)
        ttk.Label(f, text="Piotr Deres", style="Card.TLabel").pack(side="left")
        FLink(f, self.pal, "likoton.pl", URL_AUTHOR, bg=self.pal.card).pack(side="left", padx=(px(6), 0))
        return f

    def _license_cell(self, parent):
        f = tk.Frame(parent, background=self.pal.card)
        ttk.Label(f, text=self.t("about_license_name"), style="Card.TLabel").pack(side="left", padx=(0, px(12)))
        self._btn(f, self.t("btn_read_license"), self._show_license).pack(side="left")
        return f

    def _show_license(self) -> None:
        """Jedno okno: licencja aplikacji (AGPL), wykaz składników zewnętrznych i pełne teksty ich licencji."""
        t = self.t
        parts: list[str] = []
        # po spakowaniu licencje leżą obok pliku .exe (jedna kopia), ze źródeł – w folderze aplikacji
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT
        rule = "\n\n" + "=" * 78 + "\n"
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.txt"):
            try:
                parts.append((base / name).read_text(encoding="utf-8").strip("\n"))
            except OSError:
                pass
        folder = base / "licenses"
        if folder.is_dir():
            for f in sorted(folder.iterdir()):
                try:
                    parts.append(f"{f.name}\n{'-' * len(f.name)}\n" + f.read_text(encoding="utf-8", errors="replace").strip("\n"))
                except OSError:
                    pass
        text = rule.join(parts) if parts else t("license_missing")
        dialogs.show_text(self, t("license_title"), text, t("btn_close"))

    # ------------------------------------------------------------------
    # ustawienia – obsługa
    # ------------------------------------------------------------------
    def _on_lang(self, i: int) -> None:
        if LANG_CODES[i] != self.cfg.language:
            self._apply_appearance(lang=LANG_CODES[i])

    def _on_theme(self, i: int) -> None:
        if THEME_CODES[i] != self.cfg.theme:
            self._apply_appearance(theme_=THEME_CODES[i])

    def _on_console(self, i: int) -> None:
        if CONSOLE_CODES[i] != self.cfg.console:
            if CONSOLE_CODES[i] == "on":
                self.cfg.console_collapsed = "1"  # po włączeniu dziennik jest domyślnie ukryty
            self._apply_appearance(console=CONSOLE_CODES[i])

    def _on_fmt(self, i: int) -> None:
        self.cfg.archive_format = self._fmt_codes[i]
        self.cfg.save()
        self._update_format_label()

    def _apply_appearance(self, lang: Optional[str] = None, theme_: Optional[str] = None,
                          console: Optional[str] = None) -> None:
        if self.busy:
            self.info(self.t("err_busy_settings"))
            self.root.after(30, lambda: self._rebuild_frozen())  # przywraca poprzednie wartości w polach
            return
        if lang is not None:
            self.cfg.language = lang
            self.i18n.set_language(lang)
        if theme_ is not None:
            self.cfg.theme = theme_
        if console is not None:
            self.cfg.console = console
        self.cfg.save()

        def rebuild():
            with self._frozen():
                self.pal = theme.apply(self.root, self.cfg.theme)
                theme.set_titlebar(self.root, self.pal.name == "dark")
                self._build_and_render()

        self.root.after(30, rebuild)

    @contextlib.contextmanager
    def _frozen(self):
        """Wstrzymuje rysowanie okna na czas przebudowy interfejsu. Bez tego Windows maluje pośrednie stany
        (stare kontrolki z nowymi kolorami, czarne prostokąty po zniszczonych oknach potomnych)."""
        hwnd = None
        if os.name == "nt":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                if not user32.LockWindowUpdate(hwnd):
                    hwnd = None
            except Exception:  # noqa: BLE001
                hwnd = None
        try:
            yield
            if hwnd:
                self.root.update()  # układ i zdarzenia Configure dokończone, gdy rysowanie jest jeszcze wstrzymane
        finally:
            if hwnd:
                import ctypes

                ctypes.windll.user32.LockWindowUpdate(0)
                # INVALIDATE | ERASE | ALLCHILDREN | UPDATENOW: pełne, jednorazowe odświeżenie okna i kontrolek
                ctypes.windll.user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)

    def _rebuild_frozen(self) -> None:
        with self._frozen():
            self._build_and_render()

    def _build_and_render(self) -> None:
        self._build()
        self._render_status()
        self._refresh_states()

    def _update_format_label(self) -> None:
        if hasattr(self, "format_label"):
            self.format_label.configure(
                text=self.t("lbl_format", fmt=archive.resolve_format(self.cfg.archive_format)))

    # ------------------------------------------------------------------
    # stan urządzenia
    # ------------------------------------------------------------------
    def _on_dev_selected(self, idx: int) -> None:
        if 0 <= idx < len(self.devices):
            self.serial = self.devices[idx].serial
            self._on_devices(self.devices, self.dev_error)

    def _render_status(self) -> None:
        if not hasattr(self, "status_title"):
            return
        t, p = self.t, self.pal
        dev = self.current_device()
        wifi_text = ""
        show_instr = False
        side = (t("sidebar_no_device"), p.err)  # (tekst, kolor wypełnienia kropki)
        if self.adb is None:
            kind, title, detail = "Err", t("st_adb_missing_title"), t("st_adb_missing_detail")
        elif self.dev_error:
            kind, title, detail = "Err", t("st_adb_error_title"), self.dev_error
        elif dev is None:
            kind, title, detail = "Warn", t("st_nodev_title"), t("st_nodev_short")
            show_instr = True
        elif dev.state == "unauthorized":
            kind, title, detail = "Warn", t("st_unauth_title"), t("st_unauth_detail")
            side = (t("st_unauth_title"), p.warn)
        elif dev.state == "offline":
            kind, title, detail = "Warn", t("st_offline_title"), t("st_offline_detail")
        elif dev.state == "no permissions":
            kind, title, detail = "Warn", t("st_perm_title"), t("st_perm_detail")
        elif not dev.ready:
            kind, title, detail = "Warn", t("st_other_title", state=dev.state), ""
        else:
            info = self.probe.get(dev.serial, {})
            name = " ".join(x for x in (info.get("manufacturer", ""), info.get("model", "")) if x) or dev.name
            kind, title = "Ok", t("st_ready_title", name=name)
            detail = t("st_ready_detail", release=info.get("release") or "?", sdk=info.get("sdk") or "?",
                       transport=t("transport_" + dev.transport), serial=dev.serial)
            ip = info.get("ip", "")
            if dev.transport == "wifi" or info.get("wifi_debug") or info.get("tcp_port") not in (None, "", "0"):
                wifi_text = t("wifi_on", ip=ip) if ip else t("wifi_on_noip")
            elif info:
                wifi_text = t("wifi_possible", ip=ip) if ip else t("wifi_none")
            side = (name, p.ok)
        self.status_title.configure(text=title, style=f"{kind}.Title.TLabel")
        self.status_detail.configure(text=detail)
        (self.status_detail.grid if detail else self.status_detail.grid_remove)()
        self.status_wifi.configure(text=wifi_text)
        (self.status_wifi.grid if wifi_text else self.status_wifi.grid_remove)()
        if show_instr:
            if not self.instr_holder.winfo_ismapped():
                self.instr_holder.pack(fill="x")
        else:
            self.instr_holder.pack_forget()
        if dev is not None and not dev.ready and dev.state != "unauthorized":
            side = (title, p.warn)  # offline, brak uprawnień itp.
        self.side_dot.configure(image=widgets.dot_image(side[1]))
        self.side_dev.configure(text=side[0], foreground=p.fg if side[1] != p.err else p.muted)
        if len(self.devices) > 1:
            labels = [f"{d.name} · {d.serial} · {d.state}" for d in self.devices]
            idx = next((i for i, d in enumerate(self.devices) if d.serial == self.serial), 0)
            self.dev_select.set_values(labels, idx)
            self.dev_row.grid()
        else:
            self.dev_row.grid_remove()

    # ------------------------------------------------------------------
    # etykiety rozmiarów i stany kontrolek
    # ------------------------------------------------------------------
    def _hs(self, n: Optional[int]) -> str:
        return backup.human_size(n, self.i18n.decimal_comma)

    def _update_size_labels(self, failed: bool = False) -> None:
        t = self.t
        res = self.scan_result
        ready = self.ready_device() is not None
        for key in ITEM_KEYS + ["__all__"]:
            if res is None:
                self.size_vars[key].set("?" if failed else (t("size_scanning") if ready else ""))
            elif key == "__all__":
                self.size_vars[key].set(self._hs(res.total) if res.dir_exists else t("size_missing"))
            else:
                info = res.items.get(key)
                self.size_vars[key].set(self._hs(info.size) if info and info.exists else t("size_missing"))
        if res is not None and res.extra_size is not None:
            self.extra_info.set(t("lbl_total_extra", size=self._hs(res.extra_size)))
        else:
            self.extra_info.set("")

    def _item_exists(self, key: str) -> bool:
        if self.scan_result is None:
            return True
        info = self.scan_result.items.get(key)
        return bool(info and info.exists)

    def _refresh_states(self) -> None:
        if not hasattr(self, "btn_backup"):
            return
        ready = self.ready_device() is not None
        idle = not self.busy
        on = lambda c: "normal" if c else "disabled"
        self.btn_backup.configure(state=on(ready and idle))
        self.btn_rescan.configure(state=on(ready and idle))
        self.btn_wifi.configure(state=on(self.adb is not None))
        self.btn_disable.configure(state=on(ready and idle))
        self.btn_refresh.configure(state=on(self.adb is not None and idle))
        for key, cb in self.item_checks.items():
            cb.configure(state=on(idle and self.mode.get() == "selected" and self._item_exists(key)))
        data_selected = self.mode.get() == "all" or self.item_vars["data"].get()
        self.extra_chk.configure(state=on(idle and data_selected))
        c = self.content
        self.btn_load.configure(state=on(idle))
        self.btn_restore.configure(state=on(ready and idle and c is not None))
        for key, cb in self.r_checks.items():
            cb.configure(state=on(idle and c is not None and key in c.items and self.r_mode.get() == "selected"))
        has_extra = c is not None and (c.has_android_data or c.has_private)
        self.r_extra_chk.configure(state=on(idle and has_extra))
        self.btn_install.configure(state=on(ready and idle and self._apk_path() is not None))
        self.btn_maps.configure(state=on(ready and idle and self._map_path() is not None and bool(self.map_name_var.get().strip())))
        self.storage_select.configure(state=on(idle))

    # ------------------------------------------------------------------
    # operacje w tle
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.log_lines.append(line)
        if self.footer_log is not None:
            self.footer_log.configure(state="normal")
            self.footer_log.insert("end", line + "\n")
            self.footer_log.configure(state="disabled")
            self.footer_log.see("end")

    def _set_progress(self, text: str, frac: Optional[float]) -> None:
        if not self.busy:
            return
        self._op_status = text
        self.footer_status.configure(text=text)
        if frac is None:
            self.footer_pct.configure(text="")
            if self.footer.winfo_ismapped():
                self.footer_bar.start()
        else:
            self.footer_pct.configure(text=f"{int(frac * 100)}%")
            self.footer_bar.set(frac)

    def _start_op(self, title: str, work: Callable, on_ok: Callable) -> None:
        if self.busy:
            self.info(self.t("err_busy"))
            return
        self.busy = True
        self.cancel_event = threading.Event()
        cancel = self.cancel_event
        dev = self.ready_device()
        serial = dev.serial if dev else None
        self.log_lines = []
        if self.footer_log is not None:
            self.footer_log.configure(state="normal")
            self.footer_log.delete("1.0", "end")
            self.footer_log.configure(state="disabled")
        self._log(title)
        self._schedule_footer(title)
        self._set_progress(title, None)
        self._refresh_states()

        def prog(text, frac=None):
            self.post(self._set_progress, text, frac)

        def log(msg):
            self.post(self._log, msg)

        def runner():
            try:
                result = work(prog, log, cancel)
            except Cancelled:
                self.post(self._op_done, "cancel", None, on_ok)
            except Exception as e:  # noqa: BLE001
                if serial and self._device_gone(serial):
                    self.post(self._op_done, "disconnected", e, on_ok)  # komunikaty adb byłyby tylko szumem
                else:
                    self.post(self._op_done, "error", e, on_ok)
            else:
                self.post(self._op_done, "ok", result, on_ok)

        threading.Thread(target=runner, daemon=True).start()

    def _device_gone(self, serial: str) -> bool:
        """Czy urządzenie, na którym szła operacja, zniknęło lub przestało odpowiadać (wywoływane w wątku)."""
        try:
            devs = self.adb.devices()
        except Exception:  # noqa: BLE001
            return True
        return not any(d.serial == serial and d.ready for d in devs)

    def _op_done(self, status: str, result, on_ok: Callable) -> None:
        t = self.t
        self.busy = False
        self._hide_footer()
        self._refresh_states()
        if status == "cancel":
            self._log(t("log_cancelled"))
        elif status == "disconnected":
            self._log(t("err_disconnected"))
            self.warn(t("err_disconnected"))
            self._refresh_now()
        elif status == "error":
            self._log(t("log_failed", err=str(result).splitlines()[0] if str(result) else ""))
            self.error(str(result))
        else:
            on_ok(result)
        if self.ready_device() and status not in ("cancel", "disconnected"):
            self._rescan()

    # ------------------------------------------------------------------
    # kopia
    # ------------------------------------------------------------------
    def _browse_dest(self) -> None:
        d = filedialog.askdirectory(initialdir=self.dest_var.get() or None, mustexist=False)
        if d:
            self.dest_var.set(os.path.normpath(d))

    def _on_backup(self) -> None:
        t = self.t
        dev = self.ready_device()
        if not dev:
            self.warn(t("err_no_device"))
            return
        dest = self.dest_var.get().strip()
        if not dest:
            self.warn(t("err_no_dest"))
            return
        if self.mode.get() == "all":
            selection: backup.Selection = "all"
        else:
            selection = {k for k in ITEM_KEYS if self.item_vars[k].get() and self._item_exists(k)}
            if not selection:
                self.warn(t("err_no_items"))
                return
        extra = self.extra_var.get() and (selection == "all" or "data" in selection)
        fmt = archive.resolve_format(self.cfg.archive_format)
        self.cfg.last_backup_dir = dest
        self.cfg.save()
        info = dict(self.probe.get(dev.serial, {}))
        info["serial"] = dev.serial
        serial = dev.serial

        def work(prog, log, cancel):
            return backup.run_backup(self.adb, serial, selection, Path(dest), fmt, extra,
                                     prog, log, cancel, info, t)

        def ok(path: Path):
            size = self._hs(path.stat().st_size)
            self.info(t("done_backup", path=str(path), size=size))

        self._start_op(t("op_backup"), work, ok)

    # ------------------------------------------------------------------
    # przywracanie
    # ------------------------------------------------------------------
    def _browse_archive(self) -> None:
        start = self.r_file_var.get()
        path = filedialog.askopenfilename(
            initialdir=os.path.dirname(start) if start else self.dest_var.get() or None,
            filetypes=[("AutoMapa backup", "*.7z *.zip *.tar.gz *.tgz *.tar.xz *.txz"), ("*", "*.*")],
        )
        if path:
            self.r_file_var.set(os.path.normpath(path))
            self._load_archive()

    def _update_restore_labels(self) -> None:
        t = self.t
        c = self.content
        for k in ITEM_KEYS:
            if c is None:
                self.r_size_vars[k].set("")
            else:
                self.r_size_vars[k].set(self._hs(c.items[k]) if k in c.items else t("size_missing"))
        if c is None:
            self.restore_info.set(t("restore_hint"))
            return
        lines = [t("content_summary", size=self._hs(c.total))]
        if c.others:
            lines.append(t("content_others", names=", ".join(c.others[:6])))
        what = [n for n, f in (("Android/data", c.has_android_data), ("run-as", c.has_private)) if f]
        if what:
            lines.append(t("content_extra", what=", ".join(what)))
        if not c.items and not c.others:
            lines = [t("content_empty")]
        self.restore_info.set("\n".join(lines))

    def _load_archive(self) -> None:
        t = self.t
        path = Path(self.r_file_var.get().strip())
        if not path.is_file():
            self.warn(t("err_no_file"))
            return
        self.cfg.last_restore_file = str(path)
        self.cfg.save()

        def work(prog, log, cancel):
            prog(t("p_loading"), None)
            return backup.analyse(path)

        def ok(content):
            self.content = content
            for k in ITEM_KEYS:
                self.r_item_vars[k].set(k in content.items)
            self.r_extra_var.set(content.has_android_data or content.has_private)
            self._update_restore_labels()
            self._refresh_states()

        self.content = None
        self._update_restore_labels()
        self._start_op(t("p_loading"), work, ok)

    def _on_restore(self) -> None:
        t = self.t
        dev = self.ready_device()
        c = self.content
        if not dev:
            self.warn(t("err_no_device"))
            return
        path = Path(self.r_file_var.get().strip())
        if c is None or not path.is_file():
            self.warn(t("err_no_file"))
            return
        if self.r_mode.get() == "all":
            selection: backup.Selection = "all"
            names = t("all_items")
        else:
            selection = {k for k in ITEM_KEYS if self.r_item_vars[k].get() and k in c.items}
            if not selection:
                self.warn(t("err_no_items"))
                return
            names = ", ".join(backup.ITEM_BY_KEY[k].name for k in ITEM_KEYS if k in selection)
        replace = self.replace_var.get()
        extra = self.r_extra_var.get() and (c.has_android_data or c.has_private)
        msg = t("confirm_restore", name=dev.name, items=names,
                replace=t("confirm_replace_yes" if replace else "confirm_replace_no"))
        if not self.ask(msg, kind="warning"):
            return
        serial = dev.serial

        def work(prog, log, cancel):
            return backup.run_restore(self.adb, serial, path, c, selection, extra, replace,
                                      prog, log, cancel, t)

        self._start_op(t("op_restore"), work, lambda n: self.info(t("done_restore", n=n)))

    # ------------------------------------------------------------------
    # instalacja APK
    # ------------------------------------------------------------------
    def _apk_path(self) -> Optional[Path]:
        raw = self.apk_var.get().strip()
        p = Path(raw) if raw else None
        return p if p and p.is_file() and p.suffix.lower() == ".apk" else None

    def _browse_apk(self) -> None:
        start = self.apk_var.get()
        path = filedialog.askopenfilename(
            initialdir=os.path.dirname(start) if start else None,
            filetypes=[("Android package", "*.apk"), ("*", "*.*")],
        )
        if path:
            self.apk_var.set(os.path.normpath(path))

    def _on_apk_changed(self) -> None:
        t = self.t
        p = self._apk_path()
        if p is None:
            self.apk_info.set(t("inst_choose"))
        else:
            self.apk_info.set(
                t("inst_file_info", name=p.name, size=self._hs(p.stat().st_size)) + "\n"
                + t("inst_command", cmd=install.command_text(p.name))
            )
        self._refresh_states()

    def _on_install(self) -> None:
        t = self.t
        dev = self.ready_device()
        if not dev:
            self.warn(t("err_no_device"))
            return
        apk = self._apk_path()
        if apk is None:
            self.warn(t("err_apk"))
            return
        if not self.ask(t("confirm_install", name=apk.name, dev=dev.name), kind="warning"):
            return
        self.cfg.last_apk_file = str(apk)
        self.cfg.save()
        serial = dev.serial

        def work(prog, log, cancel):
            return install.run_install(self.adb, serial, apk, prog, log, cancel, t)

        self._start_op(t("op_install"), work, lambda _: self.info(t("done_install")))

    # ------------------------------------------------------------------
    # wgrywanie map
    # ------------------------------------------------------------------
    def _map_path(self) -> Optional[Path]:
        raw = self.map_file_var.get().strip()
        p = Path(raw) if raw else None
        return p if p and p.is_file() and p.suffix.lower() == ".zip" else None

    def _browse_map(self) -> None:
        start = self.map_file_var.get()
        path = filedialog.askopenfilename(
            initialdir=os.path.dirname(start) if start else None,
            filetypes=[("ZIP", "*.zip"), ("*", "*.*")],
        )
        if path:
            self.map_file_var.set(os.path.normpath(path))

    def _storage(self) -> maps.Storage:
        return self.storages[min(self.storage_idx, len(self.storages) - 1)]

    def _storage_labels(self) -> list[str]:
        t = self.t
        labels = []
        for s in self.storages:
            free = self._hs(s.free) if s.free is not None else "?"
            labels.append(t("storage_internal", free=free) if s.kind == "internal"
                          else t("storage_sd", id=s.ident, free=free))
        return labels

    def _set_storages(self, storages: list) -> None:
        self.storages = storages or [maps.Storage("internal", "/sdcard")]
        self.storage_idx = 0
        if hasattr(self, "storage_select"):
            self.storage_select.set_values(self._storage_labels(), 0)
        self._update_storage_note()
        self._update_map_target()

    def _update_storage_note(self) -> None:
        has_sd = any(s.kind == "sd" for s in self.storages)
        self.storage_note.set(self.t("storage_sd_found") if has_sd else self.t("storage_no_sd"))

    def _on_storage_selected(self, idx: int) -> None:
        self.storage_idx = idx
        self._update_map_target()

    def _on_map_file_changed(self) -> None:
        t = self.t
        p = self._map_path()
        if p is None:
            self.map_info.set(t("maps_choose"))
        else:
            try:
                info = maps.identify_map(p)
            except Exception as e:  # noqa: BLE001
                self.map_name_var.set("")
                self.map_info.set(t("maps_zip_error", err=str(e)))
            else:
                self.map_name_var.set(info.name or "")
                text = t("maps_file_info", count=info.count, size=self._hs(info.size))
                if info.name:
                    text += "\n" + t("maps_recognized", name=info.name, source=t("maps_src_" + info.source))
                else:
                    text += "\n" + t("maps_not_recognized")
                self.map_info.set(text)
        self._update_storage_note()
        self._update_map_target()
        self._refresh_states()

    def _update_map_target(self) -> None:
        name = self.map_name_var.get().strip()
        st = self._storage()
        if name:
            # /sdcard to w Androidzie nazwa pamięci wewnętrznej (nie karty), więc pokazujemy nośnik słownie
            where = (self.t("storage_where_internal") if st.kind == "internal"
                     else self.t("storage_where_sd", id=st.ident))
            path = f"{where} › {maps.MAPS_SUBPATH}/{name}"
        else:
            path = "–"
        self.map_target.set(self.t("maps_target_label") + " " + path)
        self._refresh_states()

    def _on_install_map(self) -> None:
        t = self.t
        dev = self.ready_device()
        if not dev:
            self.warn(t("err_no_device"))
            return
        zpath = self._map_path()
        name = self.map_name_var.get().strip()
        if zpath is None:
            self.warn(t("err_map_zip"))
            return
        if not name:
            self.warn(t("err_map_name"))
            return
        storage = self._storage()
        target = maps.target_dir(storage.root, name)
        if not self.ask(t("confirm_maps", name=zpath.name, dev=dev.name, path=target), kind="warning"):
            return
        self.cfg.last_map_file = str(zpath)
        self.cfg.save()
        serial = dev.serial

        def work(prog, log, cancel):
            return maps.run_install_map(self.adb, serial, zpath, storage, name, prog, log, cancel, t)

        self._start_op(t("op_maps"), work, lambda path: self.info(t("done_maps", path=path)))

    # ------------------------------------------------------------------
    # okna: Wi-Fi i wyłączanie debugowania
    # ------------------------------------------------------------------
    def _open_wifi(self) -> None:
        t, p = self.t, self.pal
        dlg, body, footer = dialogs.make_shell(self, t("wifi_title"))
        pad = tk.Frame(body, background=p.card)
        pad.pack(fill="both", expand=True, padx=px(26), pady=px(22))
        W = px(560)
        usb = next((d for d in self.devices if d.ready and d.transport == "usb"), None)
        info = self.probe.get(usb.serial, {}) if usb else {}
        ip = info.get("ip", "")
        out = tk.StringVar()

        def head(text):
            ttk.Label(pad, text=text, style="CardH3.TLabel").pack(anchor="w")

        def hint(text):
            ttk.Label(pad, text=text, style="CardMuted.TLabel", wraplength=W, justify="left").pack(anchor="w", pady=(px(2), 0))

        head(t("wifi_usb_head"))
        hint(t("wifi_usb_intro"))
        ttk.Label(pad, text=t("wifi_usb_none") if not usb else (t("wifi_usb_ip", ip=ip) if ip else t("wifi_usb_noip")),
                  style="Card.TLabel").pack(anchor="w", pady=(px(6), 0))
        row = tk.Frame(pad, background=p.card)
        row.pack(anchor="w", pady=px(8))
        ttk.Label(row, text=t("wifi_port"), style="Card.TLabel").pack(side="left")
        port = tk.StringVar(value="5555")
        FEntry(row, p, port, width=80, bg=p.card).pack(side="left", padx=px(10))
        btn_enable = self._btn(row, t("wifi_enable"), lambda: None)
        btn_enable.pack(side="left")
        if not (usb and ip):
            btn_enable.configure(state="disabled")

        FLine(pad, p).pack(fill="x", pady=px(12))
        head(t("wifi_conn_head"))
        hint(t("wifi_conn_hint"))
        row2 = tk.Frame(pad, background=p.card)
        row2.pack(anchor="w", pady=px(8))
        addr = tk.StringVar(value=f"{ip}:5555" if ip else "")
        FEntry(row2, p, addr, width=230, bg=p.card).pack(side="left")
        btn_conn = self._btn(row2, t("wifi_connect"), lambda: None)
        btn_conn.pack(side="left", padx=px(8))
        btn_disc = self._btn(row2, t("wifi_disconnect"), lambda: None)
        btn_disc.pack(side="left")

        FLine(pad, p).pack(fill="x", pady=px(12))
        head(t("wifi_pair_head"))
        hint(t("wifi_pair_hint"))
        row3 = tk.Frame(pad, background=p.card)
        row3.pack(anchor="w", pady=px(8))
        paddr, pcode = tk.StringVar(), tk.StringVar()
        ttk.Label(row3, text=t("wifi_pair_addr"), style="Card.TLabel").pack(side="left")
        FEntry(row3, p, paddr, width=200, bg=p.card).pack(side="left", padx=px(8))
        ttk.Label(row3, text=t("wifi_pair_code"), style="Card.TLabel").pack(side="left")
        FEntry(row3, p, pcode, width=90, bg=p.card).pack(side="left", padx=px(8))
        btn_pair = self._btn(row3, t("wifi_pair"), lambda: None)
        btn_pair.pack(side="left")

        ttk.Label(pad, textvariable=out, style="Card.TLabel", wraplength=W, justify="left").pack(anchor="w", pady=(px(10), 0))
        frow = tk.Frame(footer, background=p.bg)
        frow.pack(fill="x", padx=px(24), pady=px(16))
        self._btn(frow, t("btn_close"), dlg.destroy, accent=True, bg=p.bg, minwidth=110).pack(side="right")
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        all_btns = (btn_enable, btn_conn, btn_disc, btn_pair)

        def run(fn: Callable[[], str]) -> None:
            out.set(t("wifi_working"))
            for b in all_btns:
                b.configure(state="disabled")

            def work():
                try:
                    msg = fn()
                except Exception as e:  # noqa: BLE001
                    msg = str(e)

                def fin():
                    if not dlg.winfo_exists():
                        return
                    out.set(translate_adb_message(msg, t))
                    btn_enable.configure(state="normal" if (usb and ip) else "disabled")
                    for b in (btn_conn, btn_disc, btn_pair):
                        b.configure(state="normal")
                    self._wake.set()

                self.post(fin)

            threading.Thread(target=work, daemon=True).start()

        def do_enable():
            try:
                prt = int(port.get())
            except ValueError:
                return t("wifi_need_addr")
            ok, msg = self.adb.tcpip(usb.serial, prt)
            if not ok:
                return msg
            time.sleep(2.5)
            return msg + "\n" + self.adb.connect(f"{ip}:{prt}")[1]

        def valid(a: str) -> bool:
            return ":" in a and a.rsplit(":", 1)[1].isdigit()

        btn_enable.configure(command=lambda: run(do_enable))
        btn_conn.configure(command=lambda: run(lambda: self.adb.connect(addr.get().strip())[1])
                           if valid(addr.get().strip()) else out.set(t("wifi_need_addr")))
        btn_disc.configure(command=lambda: run(lambda: self.adb.disconnect(addr.get().strip())[1]))
        btn_pair.configure(command=lambda: run(lambda: self.adb.pair(paddr.get().strip(), pcode.get().strip())[1])
                           if valid(paddr.get().strip()) else out.set(t("wifi_need_addr")))
        dialogs.show(self, dlg)

    def _open_disable(self) -> None:
        t, p = self.t, self.pal
        dev = self.ready_device()
        if not dev:
            return
        dlg, body, footer = dialogs.make_shell(self, t("dis_title"))
        pad = tk.Frame(body, background=p.card)
        pad.pack(fill="both", expand=True, padx=px(26), pady=px(22))
        ttk.Label(pad, text=t("dis_title"), style="CardH3.TLabel").pack(anchor="w")
        ttk.Label(pad, text=t("dis_intro"), style="CardMuted.TLabel", wraplength=px(500), justify="left").pack(
            anchor="w", pady=(px(4), px(10)))
        opts = [
            ("adb_wifi_enabled", t("dis_wifi"), tk.BooleanVar(value=False)),
            ("development_settings_enabled", t("dis_dev"), tk.BooleanVar(value=False)),
            ("adb_enabled", t("dis_usb"), tk.BooleanVar(value=True)),
        ]
        checks = {}
        for name, label, var in opts:
            checks[name] = self._check(pad, label, var)
            checks[name].pack(anchor="w")
        out = tk.StringVar()
        ttk.Label(pad, textvariable=out, style="Card.TLabel", wraplength=px(500), justify="left").pack(
            anchor="w", pady=(px(10), 0))
        frow = tk.Frame(footer, background=p.bg)
        frow.pack(fill="x", padx=px(24), pady=px(16))
        self._btn(frow, t("btn_close"), dlg.destroy, bg=p.bg, minwidth=110).pack(side="right", padx=(px(8), 0))
        btn = self._btn(frow, t("dis_run"), lambda: None, accent=True, bg=p.bg, minwidth=110)
        btn.pack(side="right")
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        def run():
            chosen = [(n, l) for n, l, v in opts if v.get()]
            if not chosen:
                out.set(t("dis_none"))
                return
            btn.configure(state="disabled")
            serial = dev.serial

            def work():
                lines, done = [], []
                for name, label in chosen:  # adb_enabled jest ostatnie
                    try:
                        ok, msg = self.adb.settings_put(serial, name, 0)
                    except AdbError as e:
                        ok, msg = False, str(e)
                    if ok:
                        done.append(name)
                    lines.append(t("dis_ok", name=label) if ok else t("dis_fail", name=label, err=msg))

                def fin():
                    if dlg.winfo_exists():
                        out.set(t("dis_done", lines="\n".join(lines)))
                        for name in done:  # wykonane pozycje odznaczamy i blokujemy; resztę można od razu wyłączyć
                            for o_name, _, var in opts:
                                if o_name == name:
                                    var.set(False)
                            checks[name].configure(state="disabled")
                        btn.configure(state="normal")
                    self._wake.set()

                self.post(fin)

            threading.Thread(target=work, daemon=True).start()

        btn.configure(command=run)
        dialogs.show(self, dlg)


def _set_app_icon(root: tk.Tk) -> None:
    assets = ROOT / "assets"
    try:
        root._icon_img = tk.PhotoImage(file=str(assets / "icon.png"))  # type: ignore[attr-defined]
        root.iconphoto(True, root._icon_img)  # type: ignore[attr-defined]
    except tk.TclError:
        pass
    if os.name == "nt":
        try:
            root.iconbitmap(default=str(assets / "app.ico"))
        except tk.TclError:
            pass
        _set_window_icons(root, assets / "app.ico")


def _set_window_icons(root: tk.Tk, ico: Path) -> None:
    """Ikona w pasku tytułu i na pasku zadań ustawiona wprost (WM_SETICON) w rozmiarach pasujących do DPI –
    sama iconphoto/iconbitmap potrafi zostawić pasek tytułu z ikoną domyślną."""
    try:
        import ctypes

        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        root.update_idletasks()
        hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
        for kind, metric in ((0, 49), (1, 11)):  # ICON_SMALL / SM_CXSMICON, ICON_BIG / SM_CXICON
            size = u.GetSystemMetrics(metric)
            handle = u.LoadImageW(None, str(ico), 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if handle:
                u.SendMessageW(hwnd, 0x0080, kind, handle)  # WM_SETICON
                root._win_icons = getattr(root, "_win_icons", []) + [handle]  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    from .adb import Adb, locate_adb

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            if not getattr(sys, "frozen", False):
                # uruchomienie ze źródeł: własna ikona na pasku zadań zamiast ikony python.exe.
                # W wersji spakowanej Windows bierze nazwę i ikonę prosto z pliku .exe (informacje o wersji).
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Likoton.AutoMapaAndroidManager")
        except Exception:
            pass
    root = tk.Tk()
    _set_app_icon(root)
    # okno dopasowane do ekranu; zawartość przewija się, gdy okno jest niskie
    w = min(1180, root.winfo_screenwidth() - 60)
    h = min(820, root.winfo_screenheight() - 120)
    root.geometry(f"{w}x{h}+{max((root.winfo_screenwidth() - w) // 2, 0)}+20")
    root.minsize(min(980, w), 480)
    path = locate_adb()
    App(root, Config.load(), Adb(path) if path else None)
    root.mainloop()
