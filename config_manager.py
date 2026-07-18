from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ConfigManager:
    def __init__(self, config_path: str = "check.json") -> None:
        self._path = Path(config_path)
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
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
