from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tracelens.agent.planner import choose_analysis_strategy
from tracelens.agent.synthesis import synthesize_result
from tracelens.analysis.chain import build_analysis_chain
from tracelens.analysis.evidence import make_top_window_evidence
from tracelens.semantics.role_identifier import identify_thread_role
from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
from tracelens.skills.blocking_chain import BlockingChainSkill
from tracelens.skills.frame_rhythm import FrameRhythmSkill
from tracelens.skills.long_task_detection import LongTaskDetectionSkill
from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill
from tracelens.skills.scheduling_delay import SchedulingDelaySkill
from tracelens.skills.thread_state_distribution import ThreadStateDistributionSkill
from tracelens.trace.focused_process import select_focused_process
from tracelens.trace.processor import TraceSession
from tracelens.trace.queries import (
    get_processes,
    get_slices_for_process,
    get_thread_states_for_process,
    get_threads,
    get_threads_for_process,
)
from tracelens.types import AnalysisResult, EvidenceItem


@dataclass(slots=True)
class Orchestrator:
    window_skill: AbnormalWindowsSkill
    process_thread_skill: ProcessThreadDiscoverySkill

    def analyze(
        self,
        scenario: str,
        focused_process: str | None = None,
        trace_session: TraceSession | None = None,
        windows: list[dict] | None = None,
        threads: list[dict] | None = None,
    ) -> AnalysisResult:
        strategy = choose_analysis_strategy(has_focused_process=focused_process is not None)

        if trace_session is not None:
            return self._analyze_from_trace(trace_session, scenario, focused_process, strategy)

        return self._analyze_from_data(scenario, focused_process, strategy, windows or [], threads or [])

    def _analyze_from_trace(
        self,
        session: TraceSession,
        scenario: str,
        focused_process: str | None,
        strategy: str,
    ) -> AnalysisResult:
        processes = get_processes(session)
        proc = select_focused_process(processes, focused_process)
        if proc is None:
            return synthesize_result(
                evidence=[EvidenceItem(title="No process found", summary="Trace contains no usable processes")],
                chain=build_analysis_chain(strategy=strategy, scenario=scenario, focused_process=focused_process),
            )

        pid = proc["pid"]
        proc_name = proc["name"] or focused_process or "unknown"

        # Thread discovery + role identification
        raw_threads = get_threads_for_process(session, pid)
        threads_with_roles = []
        for t in raw_threads:
            name = t.get("thread_name") or ""
            role = identify_thread_role(name, proc_name)
            threads_with_roles.append({"process_name": proc_name, "thread_name": name, "role": role})
        focused_threads = self.process_thread_skill.run(threads=threads_with_roles, focused_process=proc_name)

        # Slices
        slices = get_slices_for_process(session, pid)

        # Thread states
        thread_states = get_thread_states_for_process(session, pid)
        valid_states = [s for s in thread_states if s.get("dur", 0) > 0]

        # --- Run all skills ---
        windows = self._build_window_signals(slices, valid_states)
        ranked_windows = self.window_skill.run(windows)

        state_dist = ThreadStateDistributionSkill().run(
            [{"state": s["state"], "dur_ms": s["dur"] // 1_000_000} for s in valid_states]
        )
        long_tasks = LongTaskDetectionSkill().run(slices)
        sched_delays = SchedulingDelaySkill().run(valid_states)
        blocking = BlockingChainSkill().run(valid_states)
        frame_rhythm = FrameRhythmSkill().run(slices)

        all_threads = get_threads(session)
        deps = []
        try:
            from tracelens.skills.dependency_summary import DependencySummarySkill
            deps = DependencySummarySkill().run(all_threads, slices, focused_process=proc_name)
        except Exception:
            pass

        # --- Build evidence ---
        evidence: list[EvidenceItem] = []
        chain = build_analysis_chain(strategy=strategy, scenario=scenario, focused_process=proc_name)
        chain.append(f"Process {proc_name} (pid={pid}): {len(raw_threads)} threads, {len(slices)} slices")

        # Window evidence
        top_window = ranked_windows[0] if ranked_windows else {"start": 0, "end": 0, "score": 0}
        primary_role = (
            next((t for t in focused_threads if t.get("role") not in ("unknown", None) and t.get("thread_name")), None)
            or focused_threads[0] if focused_threads
            else {"thread_name": "unknown", "role": "unknown", "process_name": proc_name}
        )
        evidence.append(make_top_window_evidence(top_window=top_window, primary_role=primary_role))
        if ranked_windows:
            chain.append(f"Top window score={top_window['score']}")

        # Thread state distribution
        if state_dist:
            summary = ", ".join(f"{s['state']}={s['dur_ms']}ms" for s in state_dist[:5])
            evidence.append(EvidenceItem(title="Thread state distribution", summary=summary))

        # Long tasks
        if long_tasks:
            top = long_tasks[:5]
            desc = "; ".join(f"{s['name']}={s['dur'] // 1_000_000}ms on {s.get('thread_name', '?')}" for s in top)
            evidence.append(EvidenceItem(title="Long slices", summary=desc))
            chain.append(f"Detected {len(long_tasks)} long slice(s)")

        # Scheduling delay
        if sched_delays:
            desc = "; ".join(f"{s['thread_name']}={s['total_delay_ms']}ms" for s in sched_delays[:3])
            evidence.append(EvidenceItem(title="Scheduling delay", summary=desc))
            chain.append(f"Scheduling delay on {len(sched_delays)} thread(s)")

        # Blocking
        if blocking:
            desc = "; ".join(
                f"{b['thread_name']}: total={b['total_blocked_ms']}ms, max_single={b['max_single_ms']}ms, count={b['block_count']}"
                for b in blocking[:3]
            )
            evidence.append(EvidenceItem(title="Blocked threads", summary=desc))
            chain.append(f"Blocking detected on {len(blocking)} thread(s)")

        # Frame rhythm
        if frame_rhythm.get("frame_count", 0) >= 2:
            jank_count = frame_rhythm["jank_count"]
            avg = frame_rhythm["avg_interval_ms"]
            summary = f"{frame_rhythm['frame_count']} frames, avg interval {avg}ms, {jank_count} jank(s)"
            evidence.append(EvidenceItem(title="Frame rhythm", summary=summary))
            if jank_count > 0:
                chain.append(f"Frame jank detected: {jank_count} frame(s) exceeded threshold")

        # Dependencies
        if deps:
            desc = "; ".join(f"{d['process_name']} ({d['thread_count']} threads)" for d in deps[:3])
            evidence.append(EvidenceItem(title="Cross-process dependencies", summary=desc))

        return synthesize_result(evidence=evidence, chain=chain)

    def _build_window_signals(self, slices: list[dict], thread_states: list[dict]) -> list[dict]:
        if not slices:
            return []
        min_ts = min(s["ts"] for s in slices)
        max_ts = max(s["ts"] + s["dur"] for s in slices)
        window_ns = 100_000_000  # 100ms
        windows: list[dict[str, Any]] = []
        ts = min_ts
        while ts < max_ts:
            end = ts + window_ns
            w_slices = [s for s in slices if s["ts"] < end and s["ts"] + s["dur"] > ts]
            w_states = [s for s in thread_states if s["ts"] < end and s["ts"] + s.get("dur", 0) > ts]
            long_tasks = sum(1 for s in w_slices if s["dur"] > 16_000_000)
            blocked = len({s.get("thread_name") for s in w_states if s.get("state") in ("S", "D")})
            sched_delay = sum(s.get("dur", 0) for s in w_states if s.get("state") == "R") // 1_000_000
            windows.append({
                "start": ts, "end": end,
                "long_tasks": long_tasks,
                "blocked_threads": blocked,
                "scheduler_delay_ms": sched_delay,
            })
            ts = end
        return windows

    def _analyze_from_data(
        self, scenario: str, focused_process: str | None, strategy: str,
        windows: list[dict], threads: list[dict],
    ) -> AnalysisResult:
        ranked_windows = self.window_skill.run(windows)
        focused_threads = self.process_thread_skill.run(threads=threads, focused_process=focused_process)
        top_window = ranked_windows[0] if ranked_windows else {"start": 0, "end": 0, "score": 0}
        primary_role = focused_threads[0] if focused_threads else {"thread_name": "unknown", "role": "unknown", "process_name": focused_process}
        evidence = [make_top_window_evidence(top_window=top_window, primary_role=primary_role)]
        chain = build_analysis_chain(strategy=strategy, scenario=scenario, focused_process=focused_process)
        return synthesize_result(evidence=evidence, chain=chain)
