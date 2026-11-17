"""Instalacja pliku APK na urządzeniu (adb install z nadpisaniem) dla bieżącego użytkownika Androida."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable, Optional

from .adb import Adb, AdbError
from .backup import PACKAGE

# Flagi wskazane przez użytkownika (-t -d -f) + -r, by na starszych Androidach też nadpisywać.
INSTALL_FLAGS = ["-r", "-t", "-d", "-f"]

Progress = Callable[[str, Optional[float]], None]
Log = Callable[[str], None]

# fragment komunikatu adb -> klucz podpowiedzi w i18n
HINTS = {
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE": "inst_hint_signature",
    "INSTALL_FAILED_VERSION_DOWNGRADE": "inst_hint_downgrade",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "inst_hint_storage",
    "INSTALL_PARSE_FAILED": "inst_hint_parse",
    "INSTALL_FAILED_OLDER_SDK": "inst_hint_sdk",
    "INSTALL_FAILED_USER_RESTRICTED": "inst_hint_restricted",
}


def command_text(apk_name: str, user: Optional[int] = None) -> str:
    who = "<ID>" if user is None else str(user)
    return "adb install " + " ".join(INSTALL_FLAGS) + f' --user {who} "{apk_name}"'


def current_user(adb: Adb, serial: str) -> int:
    """Identyfikator użytkownika Androida aktywnego na ekranie (0 = Właściciel)."""
    _, out = adb.shell(serial, "am get-current-user", 20)
    m = re.search(r"\d+", out)
    return int(m.group(0)) if m else 0


def installed_for_user(adb: Adb, serial: str, user: int, package: str = PACKAGE) -> bool:
    _, out = adb.shell(serial, f"pm path --user {user} {package}", 20)
    return "package:" in out


def run_install(
    adb: Adb,
    serial: str,
    apk: Path,
    progress: Progress,
    log: Log,
    cancel: threading.Event,
    t: Callable[..., str] = lambda k, **kw: k,
) -> None:
    apk = Path(apk)
    if not apk.is_file() or apk.suffix.lower() != ".apk":
        raise AdbError(t("err_apk"))
    # Bez --user Android potrafi zainstalować aplikację dla innego użytkownika niż ten na ekranie
    # (np. przy kilku kontach na telefonie) – wtedy nie ma jej na liście aplikacji.
    user = current_user(adb, serial)
    log(t("log_install_user", user=user))
    log(command_text(apk.name, user))
    progress(t("p_install", name=apk.name), None)
    lines: list[str] = []

    def on_line(line: str) -> None:
        lines.append(line)
        log(line)

    rc, tail = adb.stream(["install", *INSTALL_FLAGS, "--user", str(user), str(apk)], serial, on_line, cancel)
    output = "\n".join(lines) or tail
    if not (rc == 0 and "Success" in output):
        hint = next((t(key) for frag, key in HINTS.items() if frag in output), "")
        message = t("err_install", out=output.strip() or f"rc={rc}")
        raise AdbError(f"{message}\n\n{hint}" if hint else message)

    # Weryfikacja: pakiet musi być widoczny dla bieżącego użytkownika; jeśli nie – dodaj go dla niego.
    if not installed_for_user(adb, serial, user):
        log(t("log_install_existing", user=user))
        _, out = adb.shell(serial, f"pm install-existing --user {user} {PACKAGE}", 60)
        log(out.strip())
        if not installed_for_user(adb, serial, user):
            raise AdbError(t("err_install_not_visible", user=user))
