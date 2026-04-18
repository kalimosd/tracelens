from __future__ import annotations

from typing import Any

BLOCKED_STATES = {"S", "D", "DK", "I"}


class BlockingChainSkill:
    def run(self, thread_states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find threads with significant blocked/sleeping time.

        Returns per-thread blocking summaries sorted by total blocked duration descending.
        """
        blocked_by_thread: dict[str, dict[str, list[int]]] = {}
        for s in thread_states:
            state = s.get("state", "")
            if state not in BLOCKED_STATES:
                continue
            dur = s.get("dur", 0)
            if dur <= 0:
                continue
            key = s.get("thread_name") or str(s.get("tid", "?"))
            if key not in blocked_by_thread:
                blocked_by_thread[key] = {}
            blocked_by_thread[key].setdefault(state, []).append(dur)

        results = []
        for name, states in blocked_by_thread.items():
            total = sum(d for durs in states.values() for d in durs)
            count = sum(len(durs) for durs in states.values())
            max_single = max((d for durs in states.values() for d in durs), default=0)
            results.append({
                "thread_name": name,
                "total_blocked_ns": total,
                "total_blocked_ms": total // 1_000_000,
                "max_single_ms": max_single // 1_000_000,
                "block_count": count,
                "state_breakdown": {k: sum(v) // 1_000_000 for k, v in states.items()},
            })
        return sorted(results, key=lambda x: x["total_blocked_ns"], reverse=True)
