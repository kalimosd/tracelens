from __future__ import annotations

from typing import Any

BINDER_SLICE_PREFIXES = ("binder transaction", "binder reply", "binder async")


class DependencySummarySkill:
    def run(
        self,
        all_threads: list[dict[str, Any]],
        slices: list[dict[str, Any]],
        focused_process: str | None = None,
    ) -> list[dict[str, Any]]:
        """Summarize cross-process dependencies visible in the trace.

        Looks for binder-related slices and threads that indicate IPC between
        the focused process and other processes.
        """
        # Find processes that have threads interacting with focused process
        other_processes: dict[str, int] = {}
        for t in all_threads:
            proc = t.get("process_name") or ""
            if proc == focused_process or not proc:
                continue
            other_processes[proc] = other_processes.get(proc, 0) + 1

        # Count binder-related slices as dependency signals
        binder_count = sum(
            1 for s in slices
            if any(s.get("name", "").lower().startswith(p) for p in BINDER_SLICE_PREFIXES)
        )

        results = []
        for proc, thread_count in sorted(other_processes.items(), key=lambda x: x[1], reverse=True):
            results.append({
                "process_name": proc,
                "thread_count": thread_count,
            })

        if binder_count > 0 and results:
            results[0]["binder_slices"] = binder_count

        return results
