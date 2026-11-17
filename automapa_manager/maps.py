"""Wgrywanie map AutoMapa (archiwum ZIP) na pamięć wewnętrzną lub kartę pamięci."""
from __future__ import annotations

import os
import re
import shutil
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import archive
from .adb import Adb, AdbError, shq
from .backup import PACKAGE, _mk_tmp, human_size, remote_size

MAPS_SUBPATH = f"Android/obb/{PACKAGE}/AutoMapa/Maps"
# aAM_Polska_2609_6.1774.zip  ->  nazwa "Polska", wersja "2609_6.1774"
MAP_NAME_RE = re.compile(r"^aAM_([^_]+)_(.+)\.zip$", re.IGNORECASE)

Progress = Callable[[str, Optional[float]], None]
Log = Callable[[str], None]


@dataclass
class Storage:
    kind: str  # internal | sd
    root: str  # /sdcard albo /storage/XXXX-XXXX
    ident: str = ""
    free_kb: Optional[int] = None

    @property
    def free(self) -> Optional[int]:
        return self.free_kb * 1024 if self.free_kb is not None else None


def parse_map_name(filename: str) -> Optional[tuple[str, str]]:
    m = MAP_NAME_RE.match(Path(filename).name)
    return (m.group(1), m.group(2)) if m else None


def target_dir(storage_root: str, name: str) -> str:
    return f"{storage_root}/{MAPS_SUBPATH}/{name}"


def _free_kb(adb: Adb, serial: str, path: str) -> Optional[int]:
    _, out = adb.shell(serial, f"df -k {shq(path)} 2>/dev/null", 30)
    for line in reversed(out.strip().splitlines()):
        m = re.search(r"\s(\d+)\s+(\d+)\s+(\d+)\s+\d+%", line)
        if m:
            return int(m.group(3))
    return None


def detect_storages(adb: Adb, serial: str) -> list[Storage]:
    """Pamięć wewnętrzna (zawsze) oraz karty pamięci widoczne w /storage."""
    result = [Storage("internal", "/sdcard", "", _free_kb(adb, serial, "/sdcard"))]
    _, out = adb.shell(serial, "ls -1 /storage 2>/dev/null", 30)
    for name in (l.strip() for l in out.splitlines()):
        if not name or name in ("emulated", "self") or name.startswith("."):
            continue
        path = f"/storage/{name}"
        _, ok = adb.shell(serial, f"[ -d {shq(path + '/Android')} ] && echo YES", 30)
        if "YES" in ok:
            result.append(Storage("sd", path, name, _free_kb(adb, serial, path)))
    return result


def _top_level_root(tmp: Path) -> Path:
    """Jeśli ZIP zawiera jeden katalog nadrzędny – zawartością mapy są jego pliki."""
    entries = os.listdir(tmp)
    if len(entries) == 1 and (tmp / entries[0]).is_dir():
        return tmp / entries[0]
    return tmp


class _RemoteWatcher:
    """Co chwilę mierzy rozmiar katalogu na urządzeniu, by pokazać postęp wysyłania."""

    def __init__(self, adb: Adb, serial: str, path: str, report: Callable[[int], None]):
        self.adb, self.serial, self.path, self.report = adb, serial, path, report
        self._stop = threading.Event()

    def __enter__(self):
        threading.Thread(target=self._loop, daemon=True).start()
        return self

    def _loop(self):
        while not self._stop.wait(2.0):
            try:
                size = remote_size(self.adb, self.serial, self.path, True)
            except AdbError:
                continue
            if size is not None:
                self.report(size)

    def __exit__(self, *exc):
        self._stop.set()


# Rozpoznawanie rodzaju mapy: najpierw version.info, potem zawartość (pliki XX.all.c), na końcu nazwa pliku.
# Mapa Polski ma jeden plik PL.all.c, mapa Europy – wiele plików z kodami krajów.
ALL_C_RE = re.compile(r"^([A-Za-z]{2,3})\.all\.c$", re.IGNORECASE)
COUNTRY_CODES = {"PL": "Polska"}


@dataclass
class MapInfo:
    name: Optional[str]  # Polska | Europe | None (nie rozpoznano)
    source: str  # version | files | filename | ""
    count: int
    size: int


def name_from_text(text: str) -> Optional[str]:
    low = text.lower()
    for word in ("europe", "europa"):  # Europa najpierw: jej opis może wymieniać Polskę
        if re.search(rf"\b{word}\b", low):
            return "Europe"
    for word in ("polska", "poland"):
        if re.search(rf"\b{word}\b", low):
            return "Polska"
    return None


def name_from_files(names: list[str]) -> Optional[str]:
    codes = set()
    for n in names:
        m = ALL_C_RE.match(n.replace("\\", "/").rsplit("/", 1)[-1])
        if m:
            codes.add(m.group(1).upper())
    if len(codes) > 1:
        return "Europe"
    if len(codes) == 1:
        return COUNTRY_CODES.get(next(iter(codes)))
    return None


def name_from_filename(filename: str) -> Optional[str]:
    parsed = parse_map_name(filename)
    return name_from_text(parsed[0]) if parsed else None


def _read_version_info(zf: zipfile.ZipFile) -> Optional[str]:
    for info in zf.infolist():
        if not info.is_dir() and info.filename.replace("\\", "/").rsplit("/", 1)[-1].lower() == "version.info":
            data = zf.read(info)[:65536]
            for enc in ("utf-8-sig", "cp1250", "latin-1"):
                try:
                    return data.decode(enc)
                except UnicodeDecodeError:
                    continue
    return None


def identify_map(path: Path) -> MapInfo:
    """Rozpoznaje rodzaj mapy w archiwum ZIP (bez rozpakowywania całości)."""
    with zipfile.ZipFile(path) as zf:
        files = [i for i in zf.infolist() if not i.is_dir()]
        count, size = len(files), sum(i.file_size for i in files)
        text = _read_version_info(zf)
        name = name_from_text(text) if text else None
        if name:
            return MapInfo(name, "version", count, size)
        name = name_from_files([i.filename for i in files])
        if name:
            return MapInfo(name, "files", count, size)
    name = name_from_filename(Path(path).name)
    return MapInfo(name, "filename" if name else "", count, size)


def inspect_zip(path: Path) -> tuple[int, int]:
    """(liczba plików, rozmiar po rozpakowaniu) – tylko pliki."""
    entries = archive.list_archive(path)
    files = [(n, s) for n, s in entries.items() if not n.endswith("/")]
    return len(files), sum(s or 0 for _, s in files)


def run_install_map(
    adb: Adb,
    serial: str,
    zip_path: Path,
    storage: Storage,
    name: str,
    progress: Progress,
    log: Log,
    cancel: threading.Event,
    t: Callable[..., str] = lambda k, **kw: k,
) -> str:
    zip_path = Path(zip_path)
    name = name.strip().strip("/\\")
    if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
        raise AdbError(t("err_map_zip"))
    if not name or any(c in name for c in '/\\:*?"<>|'):
        raise AdbError(t("err_map_name"))
    count, total = inspect_zip(zip_path)
    if count == 0:
        raise AdbError(t("err_map_empty"))

    maps_dir = f"{storage.root}/{MAPS_SUBPATH}"
    target = f"{maps_dir}/{name}"
    old = remote_size(adb, serial, target, True) or 0
    free_kb = _free_kb(adb, serial, storage.root)
    if free_kb is not None and free_kb * 1024 + old < total:
        raise AdbError(t("err_map_space_dev", need=human_size(total), free=human_size(free_kb * 1024 + old)))
    pc_free = shutil.disk_usage(zip_path.parent).free
    if pc_free < total:
        raise AdbError(t("err_space", need=human_size(total), free=human_size(pc_free)))

    tmp = _mk_tmp(zip_path.parent)
    try:
        log(t("log_extracting"))
        progress(t("p_map_extract"), None)
        archive.extract(zip_path, tmp, lambda n, f: progress(t("p_map_extract"), None if f is None else f * 0.3), cancel)
        src = _top_level_root(tmp)
        stage = tmp / "_stage"
        stage.mkdir()
        local = stage / name
        if src == tmp:
            local.mkdir()
            for entry in os.listdir(tmp):
                if entry != "_stage":
                    os.rename(tmp / entry, local / entry)
        else:
            os.rename(src, local)

        log(t("log_force_stop"))
        adb.shell(serial, f"am force-stop {PACKAGE}", 30)
        rc, out = adb.shell(serial, f"mkdir -p {shq(maps_dir)}", 30)
        if rc != 0 or "denied" in out.lower() or "error" in out.lower():
            raise AdbError(t("err_map_storage", err=out.strip() or f"rc={rc}"))
        if old:
            log(t("log_map_remove", path=target))
        adb.shell(serial, f"rm -rf {shq(target)}", 1200)
        log(t("log_map_push", path=target))

        def on_size(cur: int) -> None:
            progress(t("p_map_push", done=human_size(cur), total=human_size(total)),
                     0.3 + 0.7 * min(cur / (total or 1), 1.0))

        progress(t("p_map_push", done=human_size(0), total=human_size(total)), 0.3)
        with _RemoteWatcher(adb, serial, target, on_size):
            rc, tail = adb.stream(["push", str(local), maps_dir], serial, None, cancel)
        if rc != 0:
            raise AdbError(f"adb push: {tail or 'błąd'}")
        got = remote_size(adb, serial, target, True) or 0
        log(t("log_map_done", size=human_size(got), count=count))
        if got < total * 0.98:
            raise AdbError(t("err_map_verify", got=human_size(got), need=human_size(total)))
        progress(t("p_done"), 1.0)
        return target
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
