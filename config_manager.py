from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _resolve_config(config_path: str) -> Path:
    """Find check.json: bundled > given path > exe directory."""
    # PyInstaller bundle
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS) / config_path  # type: ignore[attr-defined]
        if bundle.exists():
            return bundle
        exe_dir = Path(sys.executable).parent / config_path
        if exe_dir.exists():
            return exe_dir
    # Normal Python
    p = Path(config_path)
    if p.exists():
        return p
    return p  # return unresolved — caller will handle


class ConfigManager:
    def __init__(self, config_path: str = "check.json") -> None:
        self._path = _resolve_config(config_path)
        self._data: dict[str, Any] = {}

    @property
    def path(self) -> Path:
        return self._path

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        self._data["name"] = value

    @property
    def config(self) -> dict[str, Any]:
        return self._data.get("config", {})

    def get_region(self, region_type: str) -> dict[str, list[str]] | None:
        return self.config.get(region_type)

    def get_rules(self, rule_type: str) -> list[dict[str, str]]:
        return self._data.get(rule_type, [])

    def load(self) -> None:
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def save(self) -> None:
        # When frozen, save next to exe (can't write inside bundle)
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
            save_path = exe_dir / self._path.name
        else:
            save_path = self._path
        save_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
