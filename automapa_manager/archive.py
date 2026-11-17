"""Tworzenie, listowanie i rozpakowywanie archiwów (7z, zip, tar.gz, tar.xz)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .adb import CREATE_NO_WINDOW, ROOT, Cancelled

Progress = Callable[[str, Optional[float]], None]

FORMATS = {"7z": ".7z", "zip": ".zip", "tar.gz": ".tar.gz", "tar.xz": ".tar.xz"}


def _py7zr():
    try:
        import py7zr  # type: ignore

        return py7zr
    except Exception:
        return None


def find_7z_exe() -> Optional[str]:
    # dołączony do programu (tools/7zr.exe) ma pierwszeństwo
    for exe in ("7zr.exe", "7zr", "7za.exe", "7za"):
        bundled = ROOT / "tools" / exe
        if bundled.is_file():
            return str(bundled)
    for name in ("7z", "7za", "7zz", "7zr"):
        p = shutil.which(name)
        if p:
            return p
    if sys.platform.startswith("win"):
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(var)
            if base:
                cand = Path(base) / "7-Zip" / "7z.exe"
                if cand.exists():
                    return str(cand)
    return None


def sevenzip_version() -> str:
    """Numer wersji używanego 7-Zip (z komunikatu programu) albo py7zr; pusty, gdy brak."""
    exe = find_7z_exe()
    if exe:
        try:
            out = subprocess.run([exe], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            text = (out.stdout + out.stderr).decode("utf-8", "replace")
            m = re.search(r"7-Zip[^\d\n]*(\d+(?:\.\d+)+)", text)
            if m:
                return m.group(1)
        except (OSError, subprocess.SubprocessError):
            pass
    py7zr = _py7zr()
    return f"py7zr {py7zr.__version__}" if py7zr is not None else ""


def has_7z() -> bool:
    return bool(find_7z_exe() or _py7zr())


def available_formats() -> list[str]:
    fmts = ["zip", "tar.gz", "tar.xz"]
    return (["7z"] + fmts) if has_7z() else fmts


def resolve_format(pref: str) -> str:
    avail = available_formats()
    if pref in avail:
        return pref
    return "7z" if "7z" in avail else "zip"


def format_of(path: Path | str) -> str:
    low = str(path).lower()
    if low.endswith(".zip"):
        return "zip"
    if low.endswith((".tar.gz", ".tgz")):
        return "tar.gz"
    if low.endswith((".tar.xz", ".txz")):
        return "tar.xz"
    if low.endswith(".7z"):
        return "7z"
    raise ValueError(f"Nieznany format archiwum: {path}")


def _check(cancel: Optional[threading.Event]) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _run_ext(cmd: list[str], cwd: Optional[Path], cancel) -> int:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )
    while proc.poll() is None:
        if cancel is not None and cancel.is_set():
            proc.kill()
            proc.wait()
            raise Cancelled()
        time.sleep(0.2)
    return proc.returncode


# --------------------------------------------------------------------------
def walk_entries(src: Path):
    """Lista (pełna ścieżka, nazwa w archiwum, czy katalog, rozmiar)."""
    entries = []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames.sort()
        for d in dirnames:
            full = Path(dirpath) / d
            entries.append((full, full.relative_to(src).as_posix(), True, 0))
        for f in sorted(filenames):
            full = Path(dirpath) / f
            try:
                size = full.stat().st_size
            except OSError:
                size = 0
            entries.append((full, full.relative_to(src).as_posix(), False, size))
    return entries


def create(archive_path: Path, src_dir: Path, fmt: str, progress: Progress, cancel=None) -> None:
    """Pakuje zawartość ``src_dir`` do archiwum."""
    entries = walk_entries(src_dir)
    total = sum(e[3] for e in entries) or 1
    done = 0

    def tick(name: str, size: int) -> None:
        nonlocal done
        done += size
        progress(name, min(done / total, 1.0))

    try:
        if fmt == "zip":
            with zipfile.ZipFile(
                archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
            ) as zf:
                for full, arc, is_dir, size in entries:
                    _check(cancel)
                    zf.write(full, arc)
                    tick(arc, size)
        elif fmt in ("tar.gz", "tar.xz"):
            mode = "w:gz" if fmt == "tar.gz" else "w:xz"
            kwargs = {"compresslevel": 6} if fmt == "tar.gz" else {}
            with tarfile.open(archive_path, mode, **kwargs) as tf:
                for full, arc, is_dir, size in entries:
                    _check(cancel)
                    tf.add(full, arc, recursive=False)
                    tick(arc, size)
        elif fmt == "7z":
            exe = find_7z_exe()
            if exe:
                progress("7z", None)
                rc = _run_ext(
                    [exe, "a", "-t7z", "-mx=5", "-y", str(archive_path.resolve()), "*"],
                    src_dir,
                    cancel,
                )
                if rc not in (0, 1):
                    raise RuntimeError(f"7z zakończył się kodem {rc}")
            else:
                py7zr = _py7zr()
                if py7zr is None:
                    raise RuntimeError("Brak obsługi 7z (zainstaluj 7-Zip lub py7zr).")
                with py7zr.SevenZipFile(archive_path, "w") as z:
                    for full, arc, is_dir, size in entries:
                        _check(cancel)
                        z.write(full, arc)
                        tick(arc, size)
        else:
            raise ValueError(fmt)
    except BaseException:
        try:
            archive_path.unlink()
        except OSError:
            pass
        raise


def list_archive(path: Path) -> dict[str, Optional[int]]:
    """Nazwa wpisu -> rozmiar po rozpakowaniu (None, gdy nieznany)."""
    fmt = format_of(path)
    result: dict[str, Optional[int]] = {}
    if fmt == "zip":
        with zipfile.ZipFile(path) as zf:
            for i in zf.infolist():
                result[i.filename] = i.file_size
    elif fmt in ("tar.gz", "tar.xz"):
        with tarfile.open(path, "r:*") as tf:
            for m in tf:
                result[m.name] = m.size if m.isfile() else 0
    else:
        py7zr = _py7zr()
        exe = find_7z_exe()
        if py7zr is not None:
            with py7zr.SevenZipFile(path, "r") as z:
                for f in z.list():
                    result[f.filename] = 0 if f.is_directory else f.uncompressed
        elif exe:
            out = subprocess.run(
                [exe, "l", "-slt", "-ba", str(path)],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
            ).stdout.decode("utf-8", "replace")
            for block in out.replace("\r\n", "\n").split("\n\n"):
                fields = dict(
                    line.split(" = ", 1) for line in block.splitlines() if " = " in line
                )
                if "Path" in fields:
                    size = fields.get("Size", "")
                    result[fields["Path"]] = int(size) if size.isdigit() else None
        else:
            raise RuntimeError("Brak obsługi 7z (zainstaluj 7-Zip lub py7zr).")
    return result


def extract(path: Path, dest: Path, progress: Progress, cancel=None) -> None:
    """Rozpakowuje archiwum do ``dest`` (z postępem 0..1, jeśli to możliwe)."""
    fmt = format_of(path)
    dest.mkdir(parents=True, exist_ok=True)
    if fmt == "zip":
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            total = sum(i.file_size for i in infos) or 1
            done = 0
            for i in infos:
                _check(cancel)
                zf.extract(i, dest)  # zipfile usuwa ".." i ścieżki bezwzględne
                done += i.file_size
                progress(i.filename, min(done / total, 1.0))
    elif fmt in ("tar.gz", "tar.xz"):
        with tarfile.open(path, "r:*") as tf:
            for m in tf:
                _check(cancel)
                try:
                    tf.extract(m, dest, filter="data")
                except TypeError:  # Python < 3.12
                    tf.extract(m, dest)
                progress(m.name, None)
    else:
        exe = find_7z_exe()
        progress("7z", None)
        if exe:
            rc = _run_ext([exe, "x", "-y", f"-o{dest}", str(path)], None, cancel)
            if rc not in (0, 1):
                raise RuntimeError(f"7z zakończył się kodem {rc}")
        else:
            py7zr = _py7zr()
            if py7zr is None:
                raise RuntimeError("Brak obsługi 7z (zainstaluj 7-Zip lub py7zr).")
            with py7zr.SevenZipFile(path, "r") as z:
                z.extractall(dest)
