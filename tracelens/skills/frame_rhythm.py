from __future__ import annotations

from typing import Any

# Primary frame markers (one per frame), ordered by priority
_PRIMARY_FRAME_MARKERS = ("Choreographer#doFrame", "doFrame")
# Secondary markers (also frame-related but may interleave)
_ALL_FRAME_NAMES = {
    "Choreographer#doFrame", "DrawFrame", "performTraversals", "doFrame",
}

EXPECTED_FRAME_NS = 16_666_667  # ~60fps
JANK_THRESHOLD_RATIO = 1.5


class FrameRhythmSkill:
    def run(self, slices: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze frame rhythm using the primary frame marker for intervals."""
        # Pick the best primary marker available in the trace
        frame_slices = self._pick_primary_frames(slices)
        if not frame_slices:
            # Fallback to any frame-related slice
            frame_slices = sorted(
                [s for s in slices if s.get("name") in _ALL_FRAME_NAMES],
                key=lambda s: s["ts"],
            )

        if len(frame_slices) < 2:
            return {"frame_count": len(frame_slices), "janks": [], "intervals_ms": []}

        intervals: list[int] = []
        for i in range(1, len(frame_slices)):
            gap = frame_slices[i]["ts"] - frame_slices[i - 1]["ts"]
            intervals.append(gap)

        jank_threshold = int(EXPECTED_FRAME_NS * JANK_THRESHOLD_RATIO)
        janks = []
        for i, gap in enumerate(intervals):
            if gap > jank_threshold:
                janks.append({
                    "frame_index": i + 1,
                    "interval_ns": gap,
                    "interval_ms": gap // 1_000_000,
                    "ts": frame_slices[i + 1]["ts"],
                })

        intervals_ms = [g // 1_000_000 for g in intervals]
        avg_ms = sum(intervals_ms) // len(intervals_ms) if intervals_ms else 0

        return {
            "frame_count": len(frame_slices),
            "avg_interval_ms": avg_ms,
            "jank_count": len(janks),
            "janks": janks,
            "intervals_ms": intervals_ms,
        }

    def _pick_primary_frames(self, slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for marker in _PRIMARY_FRAME_MARKERS:
            frames = sorted(
                [s for s in slices if s.get("name") == marker],
                key=lambda s: s["ts"],
            )
            if len(frames) >= 2:
                return frames
        return []
