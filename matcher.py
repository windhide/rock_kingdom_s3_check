from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MatchStats:
    ball_count: int = 0
    banner_regular: int = 0
    banner_special: int = 0
    dialog: dict[str, int] = field(default_factory=dict)
    battle: dict[str, int] = field(default_factory=dict)


class Matcher:
    def __init__(self, config: Any, debounce_seconds: float = 5.0) -> None:
        self._config = config
        self._debounce = debounce_seconds
        self._last: dict[str, float] = {}
        self.stats = MatchStats()

    def match(self, region_type: str, ocr_text: str) -> list[str]:
        """Return list of matched specialty strings (debounced)."""
        if not ocr_text.strip():
            return []

        rules = self._config.get_rules(region_type)
        if not rules:
            return []

        now = time.time()
        matched: list[str] = []

        for rule in rules:
            keyword = rule["include_content"]
            if keyword not in ocr_text:
                continue

            specialty = rule["specialty"]
            key = f"{region_type}::{specialty}"
            last_ts = self._last.get(key, 0)
            if now - last_ts < self._debounce:
                continue

            self._last[key] = now
            matched.append(specialty)
            self._increment_stats(region_type, specialty)

        return matched

    def _increment_stats(self, region_type: str, specialty: str) -> None:
        if region_type == "dialog":
            self.stats.dialog[specialty] = self.stats.dialog.get(specialty, 0) + 1
        elif region_type == "battle":
            self.stats.battle[specialty] = self.stats.battle.get(specialty, 0) + 1
        elif region_type == "banner":
            if "不占保底" in specialty:
                self.stats.banner_special += 1
            else:
                self.stats.banner_regular += 1
        # Increment ball count on new dialog or battle detection
        if region_type in ("dialog", "battle"):
            self.stats.ball_count += 1

    def reset_stats(self) -> None:
        self.stats = MatchStats()
        self._last.clear()
