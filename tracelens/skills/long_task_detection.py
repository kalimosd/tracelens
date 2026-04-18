from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LONG_SLICE_THRESHOLD_NS = 16_000_000  # 16ms


@dataclass(slots=True)
class LongTaskDetectionSkill:
    threshold_ns: int = LONG_SLICE_THRESHOLD_NS

    def run(self, slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return slices longer than threshold, sorted by duration descending."""
        long = [s for s in slices if s.get("dur", 0) > self.threshold_ns]
        return sorted(long, key=lambda s: s["dur"], reverse=True)
