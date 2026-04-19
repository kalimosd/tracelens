from __future__ import annotations

import re

from tracelens.llm import LLMClient, LLMMessage
from tracelens.types import AnalysisResult, EvidenceItem

SYNTHESIS_SYSTEM_PROMPT = """You are a performance analysis assistant for Android/Flutter applications.
Given evidence from Perfetto trace analysis, produce a report for business developers.
They need to know: what's the problem, what's causing it, and what code to change.

Format:
CONCLUSION:
问题：<what happened, e.g. 掉帧>
根因：
  1. <specific cause with duration and suggestion>
  2. <next cause>

DIRECTIONS:
- 【优先】<most impactful fix with specific function/component name>
- 【建议】<secondary fix>

UNCERTAINTIES:
- <what couldn't be determined>

Be specific. Use function names and durations from evidence. Do NOT fabricate data.
Respond in the same language as the scenario description."""


def synthesize_result(
    evidence: list[EvidenceItem],
    chain: list[str],
    llm: LLMClient | None = None,
    scenario: str = "",
) -> AnalysisResult:
    if llm is not None and evidence:
        return _synthesize_with_llm(llm, evidence, chain, scenario)
    return _synthesize_with_rules(evidence, chain)


def _synthesize_with_llm(
    llm: LLMClient,
    evidence: list[EvidenceItem],
    chain: list[str],
    scenario: str,
) -> AnalysisResult:
    evidence_text = "\n".join(f"- [{e.title}] {e.summary}" for e in evidence)
    chain_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(chain))

    user_msg = f"""Scenario: {scenario}

Evidence:
{evidence_text}

Analysis chain:
{chain_text}

Produce a report for business developers. They need to know what to fix in their code."""

    try:
        response = llm.chat([
            LLMMessage(role="system", content=SYNTHESIS_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_msg),
        ])
        return _parse_llm_response(response, evidence, chain)
    except Exception:
        return _synthesize_with_rules(evidence, chain)


def _parse_llm_response(
    response: str, evidence: list[EvidenceItem], chain: list[str],
) -> AnalysisResult:
    conclusion = ""
    directions: list[str] = []
    uncertainties: list[str] = []

    section = ""
    conclusion_lines: list[str] = []
    for line in response.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("CONCLUSION:"):
            rest = stripped[len("CONCLUSION:"):].strip()
            if rest:
                conclusion_lines.append(rest)
            section = "conclusion"
        elif stripped == "DIRECTIONS:" or stripped.startswith("DIRECTIONS:"):
            section = "directions"
        elif stripped == "UNCERTAINTIES:" or stripped.startswith("UNCERTAINTIES:"):
            section = "uncertainties"
        elif stripped.startswith("- ") or stripped.startswith("- 【"):
            item = stripped[2:].strip()
            if section == "directions":
                directions.append(item)
            elif section == "uncertainties":
                uncertainties.append(item)
        elif section == "conclusion" and stripped:
            conclusion_lines.append(stripped)

    conclusion = "\n".join(conclusion_lines) if conclusion_lines else ""

    return AnalysisResult(
        conclusion=conclusion or "分析完成（详见证据）",
        key_evidence=evidence,
        analysis_chain=chain,
        optimization_directions=directions or ["检查上述证据中的耗时操作"],
        uncertainties=uncertainties,
    )


# --- Rule-based fallback ---

def _synthesize_with_rules(
    evidence: list[EvidenceItem], chain: list[str],
) -> AnalysisResult:
    return AnalysisResult(
        conclusion=_build_conclusion(evidence),
        key_evidence=evidence,
        analysis_chain=chain,
        optimization_directions=_build_directions(evidence),
        uncertainties=_build_uncertainties(evidence),
    )


def _ev_map(evidence: list[EvidenceItem]) -> dict[str, str]:
    return {e.title: e.summary.split("\n")[0] for e in evidence}


def _build_conclusion(evidence: list[EvidenceItem]) -> str:
    em = _ev_map(evidence)
    lines: list[str] = []

    # Problem: frame drops
    problem = ""
    for title in ("帧节奏", "Frame rhythm"):
        if title not in em:
            continue
        s = em[title]
        over33 = re.search(r"(\d+) over 33ms", s)
        over16 = re.search(r"(\d+) over 16ms", s)
        if over33 and int(over33.group(1)) > 0:
            problem = f"{over33.group(1)} 帧严重掉帧（>33ms，用户可感知卡顿）"
        elif over16 and int(over16.group(1)) > 0:
            problem = f"{over16.group(1)} 帧掉帧（>16ms）"
        break

    if problem:
        lines.append(f"问题：{problem}")
    lines.append("根因：")

    # Root causes from long slices
    causes: list[str] = []
    for title in ("长耗时操作", "Long slices"):
        if title not in em:
            continue
        for name, dur, thread in re.findall(r"([\w#.]+)=(\d+)ms on (\S+)", em[title])[:5]:
            lower = name.lower()
            d = int(dur)
            if "handleconfigurationchanged" in lower:
                causes.append(f"横竖屏切换触发 Activity 重建（{dur}ms）")
            elif "handlelaunchactivity" in lower:
                causes.append(f"Activity 启动 onCreate/onResume（{dur}ms）")
            elif "bindapplication" in lower:
                causes.append(f"冷启动 Application 绑定（{dur}ms）")
            elif "inflate" in lower:
                causes.append(f"布局加载 inflate（{dur}ms）← 主要瓶颈")
            elif "loadxmlresource" in lower:
                causes.append(f"XML 资源解析（{dur}ms）")
            elif "measure" in lower:
                causes.append(f"布局测量 measure（{dur}ms）← 嵌套层级过深")
            elif "layout" in lower and d > 16:
                causes.append(f"布局排列 layout（{dur}ms）")
            elif "performtraversals" in lower:
                causes.append(f"视图遍历（{dur}ms）")
            elif "doframe" in lower:
                causes.append(f"单帧处理超时（{dur}ms）")
            elif "gc" in lower or name.startswith("young"):
                causes.append(f"GC 暂停（{dur}ms）← 内存分配过多")
            elif "computeframe" in lower or "compute" in lower:
                causes.append(f"计算密集 {name}（{dur}ms）← 应移到后台线程")
            elif "binder" in lower:
                causes.append(f"Binder 跨进程调用（{dur}ms）")
            elif d > 50:
                causes.append(f"{name}（{dur}ms）")
        break

    # Binder
    for e in evidence:
        if e.title not in ("Binder 调用", "Binder transactions"):
            continue
        first_line = e.summary.split("\n")[0]
        calls_match = re.search(r"(\d+) calls", first_line)
        total_match = re.search(r"total=(\d+)ms", first_line)
        max_match = re.search(r"max=(\d+)ms", first_line)
        if calls_match and total_match:
            header = f"Binder 调用 {calls_match.group(1)} 次共 {total_match.group(1)}ms（最长 {max_match.group(1) if max_match else '?'}ms）"
            # Extract per-call details
            detail_lines = re.findall(r"(\S+)\s*=\s*(\d+)ms\s*\(on\s+(\S+)\)", e.summary)
            if detail_lines:
                details = "，".join(f"{name} {dur}ms" for name, dur, _ in detail_lines[:4])
                causes.append(f"{header}：{details}")
            else:
                causes.append(header)
        break

    # Thread state
    for title in ("线程状态分布", "Thread state distribution"):
        if title not in em:
            continue
        states = dict(re.findall(r"(\w+)=(\d+)ms", em[title]))
        total = sum(int(v) for v in states.values()) or 1
        sleep_pct = int(states.get("S", 0)) * 100 // total
        if sleep_pct > 40:
            causes.append(f"主线程 {sleep_pct}% 时间被阻塞等待（锁/Binder/I/O）")
        break

    if causes:
        for i, c in enumerate(causes, 1):
            lines.append(f"  {i}. {c}")
    else:
        lines.append("  未识别到具体根因，建议查看详细证据")

    return "\n".join(lines)


def _build_directions(evidence: list[EvidenceItem]) -> list[str]:
    em = _ev_map(evidence)
    directions: list[str] = []

    for title in ("长耗时操作", "Long slices"):
        if title not in em:
            continue
        for name, dur in re.findall(r"([\w#.]+)=(\d+)ms", em[title])[:3]:
            lower = name.lower()
            d = int(dur)
            if "inflate" in lower and d > 30:
                directions.append(f"【优先】简化布局 XML 或用 ViewStub 延迟加载非关键区域（当前 inflate {dur}ms）")
            elif "handleconfigurationchanged" in lower:
                directions.append(f"【优先】缓存状态减少重建范围，或用 android:configChanges 避免重建（当前 {dur}ms）")
            elif "bindapplication" in lower:
                directions.append(f"【优先】延迟初始化非关键 SDK，减少 Application.onCreate 耗时（当前 {dur}ms）")
            elif "handlelaunchactivity" in lower:
                directions.append(f"【优先】减少 Activity.onCreate 中的同步操作（当前 {dur}ms）")
            elif "measure" in lower or "layout" in lower:
                directions.append(f"【建议】减少布局嵌套层级（当前 {name} {dur}ms）")
            elif "computeframe" in lower or "compute" in lower:
                directions.append(f"【优先】将 {name} 拆分为小任务或移到后台线程（当前 {dur}ms）")
            elif "gc" in lower or name.startswith("young"):
                directions.append(f"【建议】减少临时对象分配，复用对象池（GC {dur}ms）")
        break

    for title in ("Binder 调用", "Binder transactions"):
        if title not in em:
            continue
        max_ms = re.search(r"max=(\d+)ms", em[title])
        if max_ms and int(max_ms.group(1)) > 16:
            directions.append(f"【建议】将耗时 Binder 调用移到后台线程或预加载（最长 {max_ms.group(1)}ms）")
        break

    for title in ("调度延迟", "Scheduling delay"):
        if title not in em:
            continue
        delay = re.search(r"=(\d+)ms", em[title])
        if delay and int(delay.group(1)) > 30:
            directions.append(f"【建议】降低后台线程优先级，减少与主线程的 CPU 竞争（调度延迟 {delay.group(1)}ms）")
        break

    for title in ("线程状态分布", "Thread state distribution"):
        if title not in em:
            continue
        states = dict(re.findall(r"(\w+)=(\d+)ms", em[title]))
        total = sum(int(v) for v in states.values()) or 1
        sleep_pct = int(states.get("S", 0)) * 100 // total
        if sleep_pct > 40:
            directions.append(f"【建议】排查主线程阻塞源（{sleep_pct}% 时间在等待），检查锁竞争和 I/O 操作")
        break

    if not directions:
        directions.append("检查上述证据中的长耗时操作和阻塞点")

    return directions


def _build_uncertainties(evidence: list[EvidenceItem]) -> list[str]:
    titles = {e.title for e in evidence}
    uncertainties: list[str] = []

    if not any(t in titles for t in ("帧节奏", "Frame rhythm")):
        uncertainties.append("缺少帧节奏数据 — trace 中可能没有帧相关的 slice")
    if not any(t in titles for t in ("跨进程依赖", "Binder 调用", "Cross-process dependencies", "Binder transactions")):
        uncertainties.append("缺少跨进程依赖数据")
    if not any(t in titles for t in ("唤醒链", "Waker chain")):
        uncertainties.append("缺少唤醒链数据 — 无法确定阻塞的具体来源（需要 sched_waking 事件）")

    return uncertainties
