from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Built-in default config — no external file needed
_DEFAULT_CONFIG = r"""
{
  "name": "洛克王国：世界",
  "config": {
    "info":    { "top": ["59","91"],  "left": ["0","12"]   },
    "dialog":  { "top": ["76","87"],  "left": ["33","65.5"] },
    "battle":  { "top": ["14","19"],  "left": ["66","100"]  },
    "banner":  { "top": ["11","18"],  "left": ["35","64"]   }
  },
  "dialog": [
    {"specialty": "无",     "include_content": "一摇一摆"},
    {"specialty": "无",     "include_content": "安静"},
    {"specialty": "无",     "include_content": "歪着头"},
    {"specialty": "奇袭",   "include_content": "背部"},
    {"specialty": "亲密",   "include_content": "亲密"},
    {"specialty": "灵巧",   "include_content": "搜寻"},
    {"specialty": "疾行",   "include_content": "扬起"},
    {"specialty": "同乘",   "include_content": "轻松"},
    {"specialty": "无畏",   "include_content": "无畏"},
    {"specialty": "热心教", "include_content": "热心"},
    {"specialty": "爱分享", "include_content": "分享"},
    {"specialty": "家里蹲", "include_content": "灵感"},
    {"specialty": "慈悲为怀","include_content": "利爪"}
  ],
  "battle": [
    {"specialty": "异色精灵_✔️", "include_content": "异色"},
    {"specialty": "污染精灵_✔️", "include_content": "污染"},
    {"specialty": "混乱精灵_❌", "include_content": "混乱"},
    {"specialty": "奇异精灵_✔️", "include_content": "奇异"},
    {"specialty": "正常精灵_❌", "include_content": "特性"}
  ],
  "banner": [
    {"specialty": "常规",           "include_content": "童话"},
    {"specialty": "不占保底异色精灵","include_content": "绘本"}
  ]
}
"""


def _find_config_file(config_path: str) -> Path | None:
    """Look for check.json: bundled > next to exe > current dir."""
    if getattr(sys, "frozen", False):
        meipass = Path(sys._MEIPASS) / config_path  # type: ignore[attr-defined]
        if meipass.exists():
            return meipass
        exe_dir = Path(sys.executable).parent / config_path
        if exe_dir.exists():
            return exe_dir
    p = Path(config_path)
    if p.exists():
        return p
    return None


class ConfigManager:
    def __init__(self, config_path: str = "check.json") -> None:
        self._config_path = config_path
        self._file_path: Path | None = None
        self._data: dict[str, Any] = {}

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
        # 1. Try external file (dev convenience)
        fp = _find_config_file(self._config_path)
        if fp:
            self._file_path = fp
            self._data = json.loads(fp.read_text(encoding="utf-8"))
            return
        # 2. Use built-in default (always available)
        self._data = json.loads(_DEFAULT_CONFIG)

    def save(self) -> None:
        # Write next to exe (dev: current dir)
        if getattr(sys, "frozen", False):
            save_path = Path(sys.executable).parent / self._config_path
        elif self._file_path:
            save_path = self._file_path
        else:
            save_path = Path(self._config_path)
        save_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
