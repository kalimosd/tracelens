"""Orchestrator: drives the analysis pipeline using planner + YAML skills + LLM synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tracelens.agent.planner import AnalysisPlan, choose_analysis_strategy, generate_plan
from tracelens.agent.synthesis import synthesize_result
from tracelens.agent.verifier import apply_corrections, verify_result
from tracelens.analysis.chain import build_analysis_chain
from tracelens.analysis.evidence import make_top_window_evidence
from tracelens.analysis.interpreter import interpret_evidence

# Chinese display names for evidence titles
_TITLE_ZH: dict[str, str] = {
    "Process overview": "进程概览",
    "Thread state distribution": "线程状态分布",
    "Long slices": "长耗时操作",
    "Scheduling delay": "调度延迟",
    "Blocked threads": "线程阻塞",
    "Frame rhythm": "帧节奏",
    "Frame causal chain": "帧因果链",
    "Per-frame analysis": "逐帧分析",
    "Frame thread states": "帧内线程状态",
    "Key threads": "关键线程",
    "Binder transactions": "Binder 调用",
    "Waker chain": "唤醒链",
    "Blocked functions": "阻塞函数",
    "Cross-process dependencies": "跨进程依赖",
}


def _zh(title: str) -> str:
    return _TITLE_ZH.get(title, title)
from tracelens.llm import LLMClient
from tracelens.semantics.role_identifier import identify_thread_role
from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill
from tracelens.skills.yaml_engine import SkillRegistry, execute_skill
from tracelens.trace.focused_process import select_focused_process
from tracelens.trace.processor import TraceSession
from tracelens.trace.queries import get_processes, get_threads_for_process
from tracelens.types import AnalysisResult, EvidenceItem


@dataclass(slots=True)
class Orchestrator:
    window_skill: AbnormalWindowsSkill
    process_thread_skill: ProcessThreadDiscoverySkill
    llm: LLMClient | None = None

    def analyze(
        self,
        scenario: str,
        focused_process: str | None = None,
        trace_session: TraceSession | None = None,
        # Legacy params for backward compat
        windows: list[dict] | None = None,
        threads: list[dict] | None = None,
    ) -> AnalysisResult:
        if trace_session is not None:
            return self._analyze_from_trace(trace_session, scenario, focused_process)

        # Legacy path
        strategy = choose_analysis_strategy(has_focused_process=focused_process is not None)
        return self._analyze_from_data(scenario, focused_process, strategy, windows or [], threads or [])

    def _analyze_from_trace(
        self,
        session: TraceSession,
        scenario: str,
        focused_process: str | None,
    ) -> AnalysisResult:
        # 1. Resolve focused process
        processes = get_processes(session)
        proc = select_focused_process(processes, focused_process)
        if proc is None:
            return synthesize_result(
                evidence=[EvidenceItem(title="未找到进程", summary="Trace contains no usable processes")],
                chain=["No usable process found in trace"],
            )

        pid = proc["pid"]
        proc_name = proc["name"] or focused_process or "unknown"

        # 2. Thread discovery + role identification
        raw_threads = get_threads_for_process(session, pid)
        threads_with_roles = []
        for t in raw_threads:
            name = t.get("thread_name") or ""
            role = identify_thread_role(name, proc_name)
            threads_with_roles.append({"process_name": proc_name, "thread_name": name, "role": role})

        primary_role = (
            next((t for t in threads_with_roles if t["role"] not in ("unknown",) and t["thread_name"]), None)
            or {"thread_name": "unknown", "role": "unknown", "process_name": proc_name}
        )

        # 3. Generate analysis plan (LLM or rules)
        registry = SkillRegistry()
        plan = generate_plan(
            scenario=scenario,
            has_focused_process=focused_process is not None,
            registry=registry,
            llm=self.llm,
        )

        # 4. Execute YAML skills according to plan
        evidence: list[EvidenceItem] = []
        chain: list[str] = list(plan.chain_steps)
        chain.append(f"Process {proc_name} (pid={pid}): {len(raw_threads)} threads")
        chain.append(f"Primary role: {primary_role['thread_name']} ({primary_role['role']})")

        for skill_id in plan.skill_ids:
            skill_def = registry.get(skill_id)
            if skill_def is None:
                continue

            result = execute_skill(skill_def, session, {"pid": pid})

            if result.errors:
                chain.append(f"Skill {skill_id}: {len(result.errors)} error(s)")
                continue

            # Convert skill results to evidence
            ev = self._skill_result_to_evidence(skill_id, result.step_results)
            if ev:
                evidence.extend(ev)
                chain.append(f"Skill {skill_id}: {sum(len(rows) for rows in result.step_results.values())} rows")

        # 5. Interpret evidence (add severity, explanation, suggestions)
        evidence = interpret_evidence(evidence)

        # 6. Synthesize
        result = synthesize_result(evidence=evidence, chain=chain, llm=self.llm, scenario=scenario)

        # 6. Verify
        report = verify_result(result)
        if report.has_issues:
            result = apply_corrections(result, report)

        return result

    def _skill_result_to_evidence(
        self, skill_id: str, step_results: dict[str, list[dict[str, Any]]]
    ) -> list[EvidenceItem]:
        """Convert raw skill step results into EvidenceItems."""
        evidence: list[EvidenceItem] = []

        if skill_id == "process_overview":
            for row in step_results.get("overview", []):
                evidence.append(EvidenceItem(
                    title=_zh("Process overview"),
                    summary=f"{row.get('thread_count', 0)} threads, {row.get('slice_count', 0)} slices",
                ))

        elif skill_id == "thread_state_distribution":
            rows = step_results.get("state_distribution", [])
            if rows:
                summary = ", ".join(f"{r['state']}={r['total_ms']}ms" for r in rows[:5])
                evidence.append(EvidenceItem(title=_zh("Thread state distribution"), summary=summary))

        elif skill_id == "long_task_detection":
            rows = step_results.get("long_slices", [])
            if rows:
                desc = "; ".join(
                    f"{r['name']}={r['dur_ms']}ms on {r.get('thread_name', '?')}" for r in rows[:5]
                )
                evidence.append(EvidenceItem(title=_zh("Long slices"), summary=desc))

        elif skill_id == "scheduling_delay":
            rows = step_results.get("delay_by_thread", [])
            if rows:
                desc = "; ".join(f"{r['thread_name']}={r['total_delay_ms']}ms" for r in rows[:3])
                evidence.append(EvidenceItem(title=_zh("Scheduling delay"), summary=desc))

        elif skill_id == "blocking_chain":
            rows = step_results.get("blocked_by_thread", [])
            if rows:
                # Aggregate by thread
                by_thread: dict[str, dict] = {}
                for r in rows:
                    name = r["thread_name"]
                    if name not in by_thread:
                        by_thread[name] = {"total_ms": 0, "max_ms": 0, "count": 0}
                    by_thread[name]["total_ms"] += r["total_ms"]
                    by_thread[name]["max_ms"] = max(by_thread[name]["max_ms"], r["max_single_ms"])
                    by_thread[name]["count"] += r["count"]
                top = sorted(by_thread.items(), key=lambda x: x[1]["total_ms"], reverse=True)[:3]
                desc = "; ".join(
                    f"{name}: total={d['total_ms']}ms, max_single={d['max_ms']}ms, count={d['count']}"
                    for name, d in top
                )
                evidence.append(EvidenceItem(title=_zh("Blocked threads"), summary=desc))

        elif skill_id == "frame_rhythm":
            summary_rows = step_results.get("frame_summary", [])
            if summary_rows:
                r = summary_rows[0]
                fc = r.get("frame_count") or 0
                if fc == 0:
                    return evidence
                avg = round(r.get("avg_dur_ms") or 0, 1)
                over16 = r.get("over_16ms") or 0
                over33 = r.get("over_33ms") or 0
                evidence.append(EvidenceItem(
                    title=_zh("Frame rhythm"),
                    summary=f"{fc} frames, avg {avg}ms, {over16} over 16ms, {over33} over 33ms",
                ))

        elif skill_id == "process_thread_discovery":
            rows = step_results.get("threads", [])
            if rows:
                top = rows[:5]
                desc = "; ".join(f"{r['thread_name']} ({r['slice_count']} slices)" for r in top)
                evidence.append(EvidenceItem(title=_zh("Key threads"), summary=desc))

        elif skill_id == "per_frame_analysis":
            frames = step_results.get("frame_list", [])
            states = step_results.get("frame_thread_state", [])
            if frames:
                top = frames[:5]
                desc = "; ".join(f"{r['frame_name']}={r['dur_ms']}ms on {r.get('thread_name', '?')}" for r in top)
                evidence.append(EvidenceItem(title=_zh("Per-frame analysis"), summary=f"{len(frames)} frames analyzed: {desc}"))
            if states:
                # Group by frame, show state breakdown for worst frames
                by_frame: dict[int, list[str]] = {}
                for s in states[:15]:
                    ft = s["frame_ts"]
                    by_frame.setdefault(ft, []).append(f"{s['state']}={s['state_dur_ms']}ms")
                parts = []
                for ft, breakdown in list(by_frame.items())[:3]:
                    parts.append(f"frame@{ft}: {', '.join(breakdown)}")
                if parts:
                    evidence.append(EvidenceItem(title=_zh("Frame thread states"), summary="; ".join(parts)))

        elif skill_id == "waker_chain":
            wakers = step_results.get("waker_summary", [])
            blocked_fns = step_results.get("top_blocked_functions", [])
            if wakers:
                desc = "; ".join(
                    f"{r['blocked_thread']} woken by {r['waker_thread']}({r.get('waker_process','?')}) {r['wake_count']}x, blocked {r['total_blocked_ms']}ms"
                    for r in wakers[:5]
                )
                evidence.append(EvidenceItem(title=_zh("Waker chain"), summary=desc))
            if blocked_fns:
                desc = "; ".join(f"{r['thread_name']}: {r['blocked_function']} ({r['total_ms']}ms, {r['count']}x)" for r in blocked_fns[:5])
                evidence.append(EvidenceItem(title=_zh("Blocked functions"), summary=desc))

        elif skill_id == "binder_analysis":
            summary = step_results.get("binder_summary", [])
            if summary:
                desc = "; ".join(f"{r['thread_name']}: {r['call_count']} calls, total={r['total_ms']}ms, max={r['max_ms']}ms" for r in summary[:3])
                evidence.append(EvidenceItem(title=_zh("Binder transactions"), summary=desc))

        elif skill_id == "frame_causal_chain":
            frames = step_results.get("jank_frames", [])
            states = step_results.get("frame_state_breakdown", [])
            child_slices = step_results.get("frame_slices", [])
            if frames:
                for f in frames[:5]:
                    frame_ts = f["frame_ts"]
                    dur_ms = f["dur_ms"]
                    thread = f.get("thread_name", "?")

                    # Find state breakdown for this frame
                    frame_states = [s for s in states if s["frame_ts"] == frame_ts]
                    state_desc = ", ".join(f"{s['state']}={s['state_ms']}ms({s['state_pct']}%)" for s in frame_states) if frame_states else "无状态数据"

                    # Find child slices for this frame
                    frame_children = [c for c in child_slices if c["frame_ts"] == frame_ts]
                    if frame_children:
                        top_children = sorted(frame_children, key=lambda c: c["dur_ms"], reverse=True)[:3]
                        children_desc = ", ".join(f"{c['slice_name']}={c['dur_ms']}ms" for c in top_children)
                    else:
                        children_desc = "无子 slice"

                    evidence.append(EvidenceItem(
                        title=_zh("Frame causal chain"),
                        summary=f"帧 {thread}@{frame_ts}: {dur_ms}ms\n  状态: {state_desc}\n  耗时操作: {children_desc}",
                    ))

        return evidence

    # --- Legacy path (no trace session) ---

    def _analyze_from_data(
        self, scenario: str, focused_process: str | None, strategy: str,
        windows: list[dict], threads: list[dict],
    ) -> AnalysisResult:
        ranked_windows = self.window_skill.run(windows)
        focused_threads = self.process_thread_skill.run(threads=threads, focused_process=focused_process)
        top_window = ranked_windows[0] if ranked_windows else {"start": 0, "end": 0, "score": 0}
        primary_role = focused_threads[0] if focused_threads else {
            "thread_name": "unknown", "role": "unknown", "process_name": focused_process,
        }
        evidence = [make_top_window_evidence(top_window=top_window, primary_role=primary_role)]
        chain = build_analysis_chain(strategy=strategy, scenario=scenario, focused_process=focused_process)
        return synthesize_result(evidence=evidence, chain=chain)
