"""Zapis ustawień użytkownika (JSON w katalogu konfiguracyjnym systemu)."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "AutoMapaManager"


@dataclass
class Config:
    language: str = "system"  # system | pl | en
    theme: str = "system"  # system | light | dark
    archive_format: str = "auto"  # auto | 7z | zip | tar.gz | tar.xz
    last_backup_dir: str = ""
    last_restore_file: str = ""
    last_apk_file: str = ""
    last_map_file: str = ""
    console: str = "off"  # on | off – konsola (dziennik operacji)
    console_collapsed: str = "1"  # 1 = ukryta w panelu postępu

    @staticmethod
    def path() -> Path:
        return config_dir() / "config.json"

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        try:
            data = json.loads(cls.path().read_text(encoding="utf-8"))
            for f in fields(cls):
                if f.name in data and isinstance(data[f.name], str):
                    setattr(cfg, f.name, data[f.name])
        except (OSError, ValueError):
            pass
        return cfg

    def save(self) -> None:
        try:
            self.path().parent.mkdir(parents=True, exist_ok=True)
            self.path().write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass
