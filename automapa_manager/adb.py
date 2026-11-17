"""Cienka warstwa nad programem adb (Android Debug Bridge).

Windows korzysta z dołączonego folderu ``tools/adb-win``. Na Linuksie i macOS
aplikacja rozpakowuje dołączone paczki platform-tools do ``tools/adb-linux`` /
``tools/adb-darwin`` (jeśli nie ma ich w PATH).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# W wersji spakowanej (PyInstaller) dane leżą w katalogu z bibliotekami programu.
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class AdbError(Exception):
    """Błąd komunikacji z adb."""


class Cancelled(Exception):
    """Operacja przerwana przez użytkownika."""


def shq(s: str) -> str:
    """Cytowanie argumentu dla powłoki Androida."""
    return "'" + s.replace("'", "'\\''") + "'"


def _dec(b: bytes) -> str:
    return b.decode("utf-8", "replace").replace("\r\n", "\n")


# --------------------------------------------------------------------------
# Lokalizowanie adb
# --------------------------------------------------------------------------
def _platform_info() -> tuple[str, str, Optional[str]]:
    if sys.platform.startswith("win"):
        return "tools/adb-win", "adb.exe", None
    if sys.platform == "darwin":
        return "tools/adb-darwin", "adb", "platform-tools-latest-darwin.zip"
    return "tools/adb-linux", "adb", "platform-tools-latest-linux.zip"


def _extract_platform_tools(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            parts = info.filename.split("/", 1)
            name = parts[1] if len(parts) > 1 else ""
            if not name:
                continue
            target = (dest / name).resolve()
            if base not in target.parents and target != base:
                continue  # ochrona przed ../
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            if (info.external_attr >> 16) & 0o111:
                target.chmod(0o755)


def locate_adb() -> Optional[Path]:
    folder, exe, archive = _platform_info()
    cand = ROOT / folder / exe
    if cand.exists():
        return cand
    zip_path = next((d / archive for d in (ROOT, ROOT / "tools") if archive and (d / archive).exists()), None)
    if zip_path:
        try:
            _extract_platform_tools(zip_path, ROOT / folder)
        except Exception:
            pass
        if cand.exists():
            return cand
    found = shutil.which("adb")
    return Path(found) if found else None


# --------------------------------------------------------------------------
# Urządzenia
# --------------------------------------------------------------------------
@dataclass
class Device:
    serial: str
    state: str  # device | unauthorized | offline | no permissions | ...
    model: str = ""
    transport: str = "usb"  # usb | wifi

    @property
    def ready(self) -> bool:
        return self.state == "device"

    @property
    def name(self) -> str:
        return self.model.replace("_", " ") if self.model else self.serial


_WIFI_RE = re.compile(r"^[\d.]+:\d+$")


class Adb:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._procs: set[subprocess.Popen] = set()
        self._lock = threading.Lock()

    # ---- podstawowe uruchamianie ------------------------------------------
    def _cmd(self, args, serial) -> list[str]:
        return [self.path] + (["-s", serial] if serial else []) + list(args)

    def run(self, args, serial: Optional[str] = None, timeout: float = 30):
        try:
            p = subprocess.run(
                self._cmd(args, serial),
                capture_output=True,
                timeout=timeout,
                creationflags=CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            raise AdbError(f"Przekroczono czas: adb {' '.join(map(str, args))}")
        except OSError as e:
            raise AdbError(str(e))
        return p.returncode, _dec(p.stdout), _dec(p.stderr)

    def shell(self, serial: str, command: str, timeout: float = 60):
        """Zwraca (kod, stdout)."""
        rc, out, _ = self.run(["shell", command], serial, timeout)
        return rc, out

    def _kill(self, proc: subprocess.Popen) -> None:
        try:
            proc.kill()
        except OSError:
            pass

    def kill_all(self) -> None:
        with self._lock:
            procs = list(self._procs)
        for p in procs:
            self._kill(p)

    def stream(
        self,
        args,
        serial: Optional[str] = None,
        on_line: Optional[Callable[[str], None]] = None,
        cancel: Optional[threading.Event] = None,
    ):
        """Uruchamia adb i przekazuje wyjście linia po linii. Zwraca (kod, ogon)."""
        try:
            proc = subprocess.Popen(
                self._cmd(args, serial),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as e:
            raise AdbError(str(e))
        with self._lock:
            self._procs.add(proc)
        done = threading.Event()

        def watch():
            while not done.wait(0.25):
                if cancel is not None and cancel.is_set():
                    self._kill(proc)
                    return

        threading.Thread(target=watch, daemon=True).start()
        tail: list[str] = []

        def emit(raw: bytes) -> None:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                return
            tail.append(line)
            del tail[:-15]
            if on_line:
                on_line(line)

        try:
            buf = b""
            while True:
                chunk = proc.stdout.read1(4096)
                if not chunk:
                    break
                buf += chunk
                parts = re.split(rb"[\r\n]+", buf)
                buf = parts.pop()
                for part in parts:
                    emit(part)
            emit(buf)
            rc = proc.wait()
        finally:
            done.set()
            with self._lock:
                self._procs.discard(proc)
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        return rc, "\n".join(tail)

    def pipe_to_file(self, args, serial, path: Path, cancel=None) -> int:
        """Zapisuje stdout polecenia (np. exec-out) do pliku."""
        with open(path, "wb") as f:
            try:
                proc = subprocess.Popen(
                    self._cmd(args, serial),
                    stdout=f,
                    stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,
                )
            except OSError as e:
                raise AdbError(str(e))
            with self._lock:
                self._procs.add(proc)
            try:
                while proc.poll() is None:
                    if cancel is not None and cancel.is_set():
                        self._kill(proc)
                        break
                    time.sleep(0.2)
                proc.wait()
            finally:
                with self._lock:
                    self._procs.discard(proc)
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        return proc.returncode

    # ---- informacje -------------------------------------------------------
    def version(self) -> str:
        try:
            rc, out, _ = self.run(["version"], timeout=10)
        except AdbError:
            return ""
        m = re.search(r"Version\s+(\S+)", out)
        return m.group(1) if m else out.splitlines()[0] if out else ""

    def devices(self) -> list[Device]:
        rc, out, err = self.run(["devices", "-l"], timeout=20)
        if rc != 0:
            raise AdbError((err or out).strip() or "adb devices failed")
        result: list[Device] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("List of"):
                continue
            tokens = line.split()
            if len(tokens) < 2:
                continue
            serial, state = tokens[0], tokens[1]
            if state == "no":
                state = "no permissions"
            kv = dict(t.split(":", 1) for t in tokens[2:] if ":" in t)
            wifi = bool(_WIFI_RE.match(serial)) or "_adb-tls-connect" in serial
            result.append(
                Device(serial, state, kv.get("model", ""), "wifi" if wifi else "usb")
            )
        return result

    def device_info(self, serial: str) -> dict:
        cmd = (
            "getprop ro.product.manufacturer; getprop ro.product.model; "
            "getprop ro.build.version.release; getprop ro.build.version.sdk; "
            "getprop service.adb.tcp.port; settings get global adb_wifi_enabled"
        )
        rc, out = self.shell(serial, cmd, 20)
        lines = out.splitlines() + [""] * 6
        info = {
            "manufacturer": lines[0].strip(),
            "model": lines[1].strip(),
            "release": lines[2].strip(),
            "sdk": lines[3].strip(),
            "tcp_port": lines[4].strip(),
            "wifi_debug": lines[5].strip() == "1",
            "ip": self.device_ip(serial),
        }
        return info

    def device_ip(self, serial: str) -> str:
        _, out = self.shell(serial, "ip -f inet addr show wlan0 2>/dev/null", 15)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
        _, out = self.shell(serial, "ip route 2>/dev/null", 15)
        for line in out.splitlines():
            if "wlan" in line:
                m = re.search(r"src (\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    return m.group(1)
        return ""

    # ---- Wi-Fi ------------------------------------------------------------
    def tcpip(self, serial: str, port: int = 5555):
        rc, out, err = self.run(["tcpip", str(port)], serial, 20)
        return rc == 0, (out + err).strip()

    def connect(self, address: str):
        rc, out, err = self.run(["connect", address], timeout=20)
        text = (out + err).strip()
        low = text.lower()
        ok = "connected to" in low and "cannot" not in low and "failed" not in low
        return ok, text

    def disconnect(self, address: str = ""):
        rc, out, err = self.run(["disconnect"] + ([address] if address else []), timeout=15)
        return rc == 0, (out + err).strip()

    def pair(self, address: str, code: str):
        rc, out, err = self.run(["pair", address, code], timeout=30)
        text = (out + err).strip()
        return "successfully paired" in text.lower(), text

    # ---- wyłączanie debugowania -------------------------------------------
    def settings_put(self, serial: str, name: str, value: int):
        rc, out = self.shell(serial, f"settings put global {name} {value}", 15)
        return rc == 0, out.strip()
