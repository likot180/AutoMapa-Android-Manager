"""Tłumaczenie komunikatów zwracanych przez adb (connect, disconnect, pair, tcpip) na język interfejsu."""
from __future__ import annotations

import re
from typing import Callable

# (wyrażenie, klucz tłumaczenia, nazwy grup przekazywane do tłumaczenia) – pierwsze dopasowanie wygrywa
_RULES: list[tuple[re.Pattern, str, tuple[str, ...]]] = [
    (re.compile(r"^already connected to (?P<addr>\S+)", re.I), "adbmsg_already", ("addr",)),
    (re.compile(r"^connected to (?P<addr>\S+)", re.I), "adbmsg_connected", ("addr",)),
    (re.compile(r"^disconnected everything", re.I), "adbmsg_disconnected_all", ()),
    (re.compile(r"^disconnected (?P<addr>\S+)", re.I), "adbmsg_disconnected", ("addr",)),
    (re.compile(r"^error: no such device '?(?P<addr>[^'\s]+)'?", re.I), "adbmsg_no_such_device", ("addr",)),
    # „failed to connect to 'IP:port': powód”, „cannot connect to IP:port: powód”, „unable to connect to IP:port: powód”
    (re.compile(r"^(?:failed to|cannot|unable to) connect to '?(?P<addr>[^'\s]+?)'?(?::\s+|\s*$)(?P<reason>.*)$", re.I),
     "adbmsg_connect_failed", ("addr", "reason")),
    (re.compile(r"^failed to authenticate to (?P<addr>\S+)", re.I), "adbmsg_auth", ("addr",)),
    (re.compile(r"^successfully paired to (?P<addr>\S+)", re.I), "adbmsg_paired", ("addr",)),
    (re.compile(r"^failed: wrong password", re.I), "adbmsg_pair_wrong", ()),
    (re.compile(r"^failed:\s*(?P<reason>.*)$", re.I), "adbmsg_pair_failed", ("reason",)),
    (re.compile(r"^restarting in tcp mode port:\s*(?P<port>\d+)", re.I), "adbmsg_tcpip", ("port",)),
    (re.compile(r"^error: device unauthorized", re.I), "adbmsg_unauthorized", ()),
    (re.compile(r"^error: device offline", re.I), "adbmsg_offline", ()),
    (re.compile(r"^error: no devices/emulators found", re.I), "adbmsg_no_devices", ()),
    (re.compile(r"^error: more than one (?:device|emulator)", re.I), "adbmsg_many_devices", ()),
]


def translate_adb_message(text: str, t: Callable[..., str]) -> str:
    """Tłumaczy znane komunikaty adb linia po linii; nieznane zostawia bez zmian."""
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for pattern, key, groups in _RULES:
            m = pattern.match(stripped)
            if m:
                params = {g: (m.group(g) or "").strip() for g in groups}
                if "reason" in params and params["reason"]:
                    params["reason"] = " " + t("adbmsg_reason", reason=params["reason"])
                elif "reason" in params:
                    params["reason"] = ""
                out.append(t(key, **params))
                break
        else:
            out.append(stripped)
    return "\n".join(out)
