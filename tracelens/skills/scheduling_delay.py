from __future__ import annotations

from typing import Any


class SchedulingDelaySkill:
    def run(self, thread_states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find threads with significant time in Runnable (R) state — waiting to be scheduled.

        Returns per-thread scheduling delay summaries, sorted by total delay descending.
        """
        delay_by_thread: dict[str, int] = {}
        for s in thread_states:
            if s.get("state") != "R":
                continue
            dur = s.get("dur", 0)
            if dur <= 0:
                continue
            key = s.get("thread_name") or str(s.get("tid", "?"))
            delay_by_thread[key] = delay_by_thread.get(key, 0) + dur

        return [
            {"thread_name": name, "total_delay_ns": total, "total_delay_ms": total // 1_000_000}
            for name, total in sorted(delay_by_thread.items(), key=lambda x: x[1], reverse=True)
        ]
