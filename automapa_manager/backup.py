"""Logika kopii zapasowej i przywracania danych AutoMapa."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union

from . import archive
from .adb import Adb, AdbError, Cancelled, shq

PACKAGE = "pl.aqurat.automapa"
REMOTE_BASE = f"/sdcard/Android/obb/{PACKAGE}"
REMOTE_DIR = f"{REMOTE_BASE}/AutoMapa"
EXTRA_DATA_DIR = f"/sdcard/Android/data/{PACKAGE}"  # katalog zewnętrzny aplikacji (cache, files)
ARCHIVE_ROOT = "AutoMapa"
ARCHIVE_EXTRA_DATA = "AndroidData"
ARCHIVE_PRIVATE = "AppPrivate"
PRIVATE_TAR = "run_as.tar"
INFO_FILE = "backup_info.json"
EXTRA_NAMES = {ARCHIVE_EXTRA_DATA, ARCHIVE_PRIVATE, INFO_FILE}

Progress = Callable[[str, Optional[float]], None]
Log = Callable[[str], None]
Selection = Union[str, set]  # "all" albo zbiór kluczy pozycji


@dataclass(frozen=True)
class Item:
    key: str
    name: str  # nazwa katalogu/pliku na urządzeniu
    is_dir: bool = True
    aliases: tuple = ()  # inne spotykane nazwy (np. starsze kopie)

    @property
    def all_names(self) -> tuple:
        return (self.name,) + self.aliases


ITEMS = [
    Item("data", "Data"),
    Item("settings", "Settings"),
    Item("colors", "Colors"),
    Item("routes", "Routes"),
    Item("trase", "Trace", True, ("Trase",)),
    Item("sound", "Sound"),
    Item("maps", "Maps"),
    Item("license", "AutoMapa.lic", False),
]
ITEM_BY_KEY = {i.key: i for i in ITEMS}
ITEM_BY_LOWER = {n.lower(): i for i in ITEMS for n in i.all_names}


def human_size(n: Optional[int], decimal_comma: bool = False) -> str:
    if n is None:
        return "?"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            text = f"{int(value)} {unit}" if unit == "B" else f"{value:.2f} {unit}"
            return text.replace(".", ",") if decimal_comma else text
        value /= 1024
    return str(n)


# --------------------------------------------------------------------------
# Skanowanie urządzenia
# --------------------------------------------------------------------------
@dataclass
class ItemInfo:
    exists: bool = False
    size: Optional[int] = None
    actual: str = ""


@dataclass
class ScanResult:
    items: dict = field(default_factory=dict)  # key -> ItemInfo
    total: Optional[int] = None
    dir_exists: bool = False
    extra_size: Optional[int] = None


def _first_int(text: str) -> Optional[int]:
    m = re.search(r"^\s*(\d+)", text, re.M)
    return int(m.group(1)) if m else None


def remote_size(adb: Adb, serial: str, path: str, is_dir: bool) -> Optional[int]:
    if is_dir:
        _, out = adb.shell(serial, f"du -sb {shq(path)} 2>/dev/null", 600)
        n = _first_int(out)
        if n is not None:
            return n
        _, out = adb.shell(serial, f"du -sk {shq(path)} 2>/dev/null", 600)
        n = _first_int(out)
        return n * 1024 if n is not None else None
    _, out = adb.shell(serial, f"stat -c %s {shq(path)} 2>/dev/null", 30)
    return _first_int(out)


def scan(adb: Adb, serial: str) -> ScanResult:
    res = ScanResult()
    _, out = adb.shell(serial, f"[ -d {shq(REMOTE_DIR)} ] && echo YES", 30)
    res.dir_exists = "YES" in out
    names: dict[str, str] = {}
    if res.dir_exists:
        _, out = adb.shell(serial, f"ls -1 {shq(REMOTE_DIR)} 2>/dev/null", 60)
        names = {l.strip().lower(): l.strip() for l in out.splitlines() if l.strip()}
        res.total = remote_size(adb, serial, REMOTE_DIR, True)
    for item in ITEMS:
        actual = next((names[n.lower()] for n in item.all_names if n.lower() in names), None)
        info = ItemInfo()
        if actual:
            info.exists = True
            info.actual = actual
            info.size = remote_size(adb, serial, f"{REMOTE_DIR}/{actual}", item.is_dir)
        res.items[item.key] = info
    _, out = adb.shell(serial, f"[ -d {shq(EXTRA_DATA_DIR)} ] && echo YES", 30)
    if "YES" in out:
        res.extra_size = remote_size(adb, serial, EXTRA_DATA_DIR, True)
    return res


# --------------------------------------------------------------------------
# Pomocnicze
# --------------------------------------------------------------------------
def dir_size(path: Path) -> int:
    total = 0
    for dp, _, files in os.walk(path):
        for f in files:
            try:
                total += (Path(dp) / f).stat().st_size
            except OSError:
                pass
    return total


class _SizeWatcher:
    """Co chwilę mierzy rozmiar katalogu, by pokazać postęp kopiowania."""

    def __init__(self, path: Path, expected: Optional[int], report: Callable[[int], None]):
        self.path, self.expected, self.report = path, expected, report
        self._stop = threading.Event()

    def __enter__(self):
        if self.expected:
            threading.Thread(target=self._loop, daemon=True).start()
        return self

    def _loop(self):
        while not self._stop.wait(1.0):
            self.report(dir_size(self.path))

    def __exit__(self, *exc):
        self._stop.set()


def _mk_tmp(preferred: Path) -> Path:
    try:
        return Path(tempfile.mkdtemp(prefix=".automapa_tmp_", dir=preferred))
    except OSError:
        return Path(tempfile.mkdtemp(prefix="automapa_tmp_"))


def _canonical_rename(parent: Path, actual: str, wanted: str) -> None:
    """Zmienia nazwę na kanoniczną (także gdy różni się tylko wielkością liter)."""
    if actual == wanted or not (parent / actual).exists():
        return
    mid = parent / (wanted + ".__tmp__")
    os.rename(parent / actual, mid)
    os.rename(mid, parent / wanted)


def _adb_transfer(adb, serial, args, cancel, on_line=None):
    rc, tail = adb.stream(args, serial, on_line, cancel)
    if rc != 0:
        raise AdbError(f"adb {args[0]}: {tail or 'błąd'}")


# --------------------------------------------------------------------------
# Kopia zapasowa
# --------------------------------------------------------------------------
def run_backup(
    adb: Adb,
    serial: str,
    selection: Selection,
    dest_dir: Path,
    fmt: str,
    include_extra: bool,
    progress: Progress,
    log: Log,
    cancel: threading.Event,
    device_info: Optional[dict] = None,
    t: Callable[..., str] = lambda k, **kw: k,
) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    progress(t("p_scanning"), None)
    sc = scan(adb, serial)
    if not sc.dir_exists:
        raise AdbError(t("err_no_dir", path=REMOTE_DIR))

    if selection == "all":
        jobs = [("all", REMOTE_DIR, sc.total)]
        kind = "all"
    else:
        jobs = []
        for key in (i.key for i in ITEMS if i.key in selection):
            info = sc.items[key]
            if info.exists:
                jobs.append((key, f"{REMOTE_DIR}/{info.actual}", info.size))
            else:
                log(t("log_item_missing", name=ITEM_BY_KEY[key].name))
        if not jobs:
            raise AdbError(t("err_nothing"))
        kind = "partial"
    total_bytes = sum(j[2] or 0 for j in jobs)
    free = shutil.disk_usage(dest_dir).free
    if total_bytes and free < total_bytes:
        raise AdbError(
            t("err_space", need=human_size(total_bytes), free=human_size(free))
        )

    staging = _mk_tmp(dest_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = dest_dir / f"AutoMapa_{kind}_{stamp}{archive.FORMATS[fmt]}"
    try:
        stage_root = staging / ARCHIVE_ROOT
        stage_root.mkdir()
        done_bytes = 0
        for key, remote, size in jobs:
            name = "AutoMapa" if key == "all" else ITEM_BY_KEY[key].name
            log(t("log_pull", name=name))
            before = done_bytes

            def on_size(cur, before=before, name=name):
                progress(
                    t("p_pull", name=name, done=human_size(before + cur), total=human_size(total_bytes)),
                    min((before + cur) / (total_bytes or 1), 1.0) * 0.5,
                )

            progress(t("p_pull", name=name, done=human_size(done_bytes), total=human_size(total_bytes)), None)
            with _SizeWatcher(staging, total_bytes, lambda cur: on_size(cur - before)):
                if key == "all":
                    _adb_transfer(adb, serial, ["pull", remote, str(staging)], cancel)
                else:
                    # zachowujemy rzeczywistą nazwę z urządzenia (Android rozróżnia wielkość liter)
                    _adb_transfer(adb, serial, ["pull", remote, str(stage_root)], cancel)
            if key != "all" and not (stage_root / remote.rsplit("/", 1)[1]).exists():
                raise AdbError(t("err_pull_failed", name=name))
            done_bytes += size or 0

        extras = []
        if include_extra:
            extras = _backup_extra(adb, serial, staging, log, cancel, t)

        info = {
            "app": "AutoMapa Android Manager",
            "created": datetime.now().isoformat(timespec="seconds"),
            "package": PACKAGE,
            "kind": kind,
            "items": ["AutoMapa"] if kind == "all" else [ITEM_BY_KEY[k].name for k in ITEM_BY_KEY if k in selection],
            "extras": extras,
            "device": device_info or {},
        }
        (staging / INFO_FILE).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

        log(t("log_archiving", fmt=fmt))

        def on_archive(name, frac):
            progress(t("p_archive", name=name), None if frac is None else 0.5 + frac * 0.5)

        archive.create(archive_path, staging, fmt, on_archive, cancel)
        log(t("log_archive_done", path=str(archive_path), size=human_size(archive_path.stat().st_size)))
        return archive_path
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _backup_extra(adb, serial, staging: Path, log, cancel, t) -> list:
    """Dane aplikacji spoza katalogu AutoMapa – tylko jeśli system na to pozwala."""
    got = []
    # 1) /sdcard/Android/data/<pakiet> (cache, files)
    try:
        log(t("log_extra_data"))
        tmp = staging / "_x"
        tmp.mkdir()
        rc, tail = adb.stream(["pull", EXTRA_DATA_DIR, str(tmp)], serial, None, cancel)
        pulled = tmp / PACKAGE
        if rc == 0 and pulled.exists():
            os.rename(pulled, staging / ARCHIVE_EXTRA_DATA)
            got.append(ARCHIVE_EXTRA_DATA)
        else:
            log(t("log_extra_data_fail", why=tail.splitlines()[-1] if tail else ""))
        shutil.rmtree(tmp, ignore_errors=True)
    except AdbError as e:
        log(t("log_extra_data_fail", why=str(e)))
    # 2) prywatne dane (run-as) – działa tylko dla aplikacji debugowalnych
    try:
        log(t("log_extra_private"))
        priv = staging / ARCHIVE_PRIVATE
        priv.mkdir()
        target = priv / PRIVATE_TAR
        adb.pipe_to_file(["exec-out", f"run-as {PACKAGE} tar -cf - ."], serial, target, cancel)
        ok = False
        if target.exists() and target.stat().st_size > 1024:
            with open(target, "rb") as f:
                head = f.read(512)
            ok = head[257:262] == b"ustar"
        if ok:
            got.append(ARCHIVE_PRIVATE)
        else:
            shutil.rmtree(priv, ignore_errors=True)
            log(t("log_extra_private_fail"))
    except AdbError as e:
        log(t("log_extra_private_fail") + f" ({e})")
    return got


# --------------------------------------------------------------------------
# Analiza archiwum i przywracanie
# --------------------------------------------------------------------------
@dataclass
class ArchiveContent:
    prefix: str = ""  # "AutoMapa/" albo ""
    items: dict = field(default_factory=dict)  # key -> rozmiar (None = nieznany)
    others: list = field(default_factory=list)  # nieznane pozycje najwyższego poziomu
    has_android_data: bool = False
    has_private: bool = False
    total: Optional[int] = 0


def _norm(name: str) -> str:
    name = name.replace("\\", "/")
    return re.sub(r"^(\./)+", "", name)


def analyse(path: Path) -> ArchiveContent:
    entries = {_norm(k): v for k, v in archive.list_archive(path).items()}
    content = ArchiveContent()
    if any(n.startswith(ARCHIVE_ROOT + "/") for n in entries):
        content.prefix = ARCHIVE_ROOT + "/"
    tops: dict[str, Optional[int]] = {}
    for name, size in entries.items():
        if content.prefix:
            if name.startswith(ARCHIVE_ROOT + "/"):
                rest = name[len(content.prefix):]
            else:
                if name.split("/", 1)[0] == ARCHIVE_EXTRA_DATA:
                    content.has_android_data = True
                if name.split("/", 1)[0] == ARCHIVE_PRIVATE and name.endswith(PRIVATE_TAR):
                    content.has_private = True
                continue
        else:
            rest = name
            top0 = rest.split("/", 1)[0]
            if top0 in EXTRA_NAMES:
                if top0 == ARCHIVE_EXTRA_DATA:
                    content.has_android_data = True
                if top0 == ARCHIVE_PRIVATE and name.endswith(PRIVATE_TAR):
                    content.has_private = True
                continue
        rest = rest.strip("/")
        if not rest:
            continue
        top = rest.split("/", 1)[0]
        cur = tops.get(top, 0)
        tops[top] = None if (size is None or cur is None) else cur + size
    total: Optional[int] = 0
    for top, size in tops.items():
        item = ITEM_BY_LOWER.get(top.lower())
        if item:
            content.items[item.key] = size
        else:
            content.others.append(top)
        total = None if (size is None or total is None) else total + size
    content.total = total
    return content


def run_restore(
    adb: Adb,
    serial: str,
    archive_path: Path,
    content: ArchiveContent,
    selection: Selection,
    restore_extra: bool,
    replace: bool,
    progress: Progress,
    log: Log,
    cancel: threading.Event,
    t: Callable[..., str] = lambda k, **kw: k,
) -> int:
    """Zwraca liczbę przywróconych pozycji."""
    archive_path = Path(archive_path)
    tmp = _mk_tmp(archive_path.parent)
    try:
        log(t("log_extracting"))
        progress(t("p_extract"), None)
        archive.extract(
            archive_path,
            tmp,
            lambda name, frac: progress(t("p_extract"), None if frac is None else frac * 0.4),
            cancel,
        )
        root = tmp / ARCHIVE_ROOT if content.prefix else tmp
        if not root.exists():
            raise AdbError(t("err_bad_archive"))

        jobs = []  # (lokalna ścieżka, nazwa docelowa, katalog?, rozmiar)
        for entry in sorted(os.listdir(root)):
            if not content.prefix and entry in EXTRA_NAMES:
                continue
            item = ITEM_BY_LOWER.get(entry.lower())
            if selection != "all" and (item is None or item.key not in selection):
                continue
            local = root / entry
            size = dir_size(local) if local.is_dir() else local.stat().st_size
            jobs.append((local, entry, local.is_dir(), size))
        if not jobs and not (restore_extra and (content.has_android_data or content.has_private)):
            raise AdbError(t("err_nothing"))

        total = sum(j[3] for j in jobs) or 1
        log(t("log_force_stop"))
        adb.shell(serial, f"am force-stop {PACKAGE}", 30)
        rc, out = adb.shell(serial, f"mkdir -p {shq(REMOTE_DIR)}", 30)
        if rc != 0:
            raise AdbError(f"mkdir {REMOTE_DIR}: {out.strip()}")

        # nazwy już istniejące na urządzeniu (bez względu na wielkość liter) mają pierwszeństwo
        _, out = adb.shell(serial, f"ls -1 {shq(REMOTE_DIR)} 2>/dev/null", 60)
        existing = {l.strip().lower(): l.strip() for l in out.splitlines() if l.strip()}

        done = 0
        for idx, (local, entry, is_dir, size) in enumerate(jobs, 1):
            item = ITEM_BY_LOWER.get(entry.lower())
            candidates = item.all_names if item else (entry,)
            # nazwa już istniejąca na urządzeniu (też alias, np. Trase/Trace) ma pierwszeństwo
            name = next((existing[n.lower()] for n in candidates if n.lower() in existing), entry)
            if name != entry:  # lokalnie nadaj nazwę taką jak na urządzeniu
                _canonical_rename(local.parent, entry, name)
                local = local.parent / name
            label = t("p_push", name=name, n=idx, count=len(jobs))
            progress(label, 0.4 + 0.6 * done / total)
            log(t("log_push", name=name))
            remote = f"{REMOTE_DIR}/{name}"
            if is_dir:
                if replace:
                    adb.shell(serial, f"rm -rf {shq(remote)}", 600)
                _adb_transfer(adb, serial, ["push", str(local), REMOTE_DIR], cancel)
                adb.shell(serial, f"mkdir -p {shq(remote)}", 30)  # także puste katalogi
            else:
                _adb_transfer(adb, serial, ["push", str(local), remote], cancel)
            done += size

        restored = len(jobs)
        if restore_extra:
            restored += _restore_extra(adb, serial, tmp, content, log, cancel, t)
        progress(t("p_done"), 1.0)
        return restored
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _restore_extra(adb, serial, tmp: Path, content: ArchiveContent, log, cancel, t) -> int:
    n = 0
    data = tmp / ARCHIVE_EXTRA_DATA
    if content.has_android_data and data.exists():
        try:
            log(t("log_restore_extra_data"))
            os.rename(data, tmp / PACKAGE)
            adb.shell(serial, f"mkdir -p {shq('/sdcard/Android/data')}", 30)
            _adb_transfer(adb, serial, ["push", str(tmp / PACKAGE), "/sdcard/Android/data"], cancel)
            n += 1
        except AdbError as e:
            log(t("log_restore_extra_fail", why=str(e)))
    private = tmp / ARCHIVE_PRIVATE / PRIVATE_TAR
    if content.has_private and private.exists():
        try:
            log(t("log_restore_private"))
            remote = "/data/local/tmp/automapa_restore.tar"
            _adb_transfer(adb, serial, ["push", str(private), remote], cancel)
            adb.shell(serial, f"chmod 644 {remote}", 15)
            rc, out = adb.shell(serial, f"run-as {PACKAGE} tar -xf {remote}", 600)
            adb.shell(serial, f"rm -f {remote}", 15)
            if rc == 0:
                n += 1
            else:
                log(t("log_restore_extra_fail", why=out.strip()))
        except AdbError as e:
            log(t("log_restore_extra_fail", why=str(e)))
    return n
