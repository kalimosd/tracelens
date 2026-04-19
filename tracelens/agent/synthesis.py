from __future__ import annotations

import re

from tracelens.llm import LLMClient, LLMMessage
from tracelens.types import AnalysisResult, EvidenceItem

SYNTHESIS_SYSTEM_PROMPT = """You are a performance analysis assistant for Android/Flutter applications.
Given a set of evidence from Perfetto trace analysis, produce:
1. A concise conclusion (1-3 sentences) identifying the main performance issue
2. Actionable optimization directions (2-5 bullet points)
3. Uncertainties — what could not be determined from the evidence

Be specific. Reference thread names, durations, and states from the evidence.
Do NOT fabricate data not present in the evidence.
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

Based on the evidence above, provide your analysis in this exact format:

CONCLUSION: <your conclusion>

DIRECTIONS:
- <direction 1>
- <direction 2>

UNCERTAINTIES:
- <uncertainty 1>"""

    try:
        response = llm.chat([
            LLMMessage(role="system", content=SYNTHESIS_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_msg),
        ])
        return _parse_llm_response(response, evidence, chain)
    except Exception:
        # Fallback to rules if LLM call fails
        return _synthesize_with_rules(evidence, chain)


def _parse_llm_response(
    response: str,
    evidence: list[EvidenceItem],
    chain: list[str],
) -> AnalysisResult:
    conclusion = ""
    directions: list[str] = []
    uncertainties: list[str] = []

    section = ""
    for line in response.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("CONCLUSION:"):
            conclusion = stripped[len("CONCLUSION:"):].strip()
            section = "conclusion"
        elif stripped == "DIRECTIONS:":
            section = "directions"
        elif stripped == "UNCERTAINTIES:":
            section = "uncertainties"
        elif stripped.startswith("- "):
            item = stripped[2:].strip()
            if section == "directions":
                directions.append(item)
            elif section == "uncertainties":
                uncertainties.append(item)
        elif section == "conclusion" and stripped and not conclusion:
            conclusion = stripped

    return AnalysisResult(
        conclusion=conclusion or "Analysis complete (see evidence for details)",
        key_evidence=evidence,
        analysis_chain=chain,
        optimization_directions=directions or ["Review the evidence above for optimization opportunities"],
        uncertainties=uncertainties,
    )


# --- Rule-based fallback (no LLM) ---

def _synthesize_with_rules(
    evidence: list[EvidenceItem],
    chain: list[str],
) -> AnalysisResult:
    conclusion = _build_conclusion(evidence)
    directions = _build_directions(evidence)
    uncertainties = _build_uncertainties(evidence)

    return AnalysisResult(
        conclusion=conclusion,
        key_evidence=evidence,
        analysis_chain=chain,
        optimization_directions=directions,
        uncertainties=uncertainties,
    )


def _build_conclusion(evidence: list[EvidenceItem]) -> str:
    titles = {e.title for e in evidence}
    ev_map = {e.title: e.summary.split("\n")[0] for e in evidence}

    # Build a specific diagnostic summary, not just "存在长耗时操作"
    findings: list[str] = []

    # Frame info
    for title in ("帧节奏", "Frame rhythm"):
        if title in ev_map:
            s = ev_map[title]
            over33 = re.search(r"(\d+) over 33ms", s)
            over16 = re.search(r"(\d+) over 16ms", s)
            frames = re.search(r"(\d+) frames", s)
            if over33 and int(over33.group(1)) > 0:
                findings.append(f"{over33.group(1)} 帧严重掉帧（>33ms）")
            elif over16 and int(over16.group(1)) > 0:
                findings.append(f"{over16.group(1)} 帧掉帧（>16ms）")
            elif frames:
                findings.append(f"{frames.group(1)} 帧均正常")
            break

    # Root cause from long slices
    for title in ("长耗时操作", "Long slices"):
        if title in ev_map:
            s = ev_map[title]
            top_slice = re.search(r"([\w#.]+)=(\d+)ms on (\S+)", s)
            if top_slice:
                name, dur, thread = top_slice.groups()
                # Map slice name to human-readable cause
                if "handleConfigurationChanged" in name:
                    findings.append(f"横竖屏切换触发重建（{dur}ms）")
                elif "handleLaunchActivity" in name or "bindApplication" in name:
                    findings.append(f"Activity 启动耗时（{name}={dur}ms）")
                elif "inflate" in name.lower():
                    findings.append(f"布局加载耗时（{dur}ms）")
                elif "doFrame" in name:
                    findings.append(f"单帧处理超时（{dur}ms）")
                elif "computeFrame" in name or "compute" in name.lower():
                    findings.append(f"计算密集操作（{name}={dur}ms）")
                else:
                    findings.append(f"主要耗时：{name}={dur}ms on {thread}")
            break

    # Thread state
    for title in ("线程状态分布", "Thread state distribution"):
        if title in ev_map:
            s = ev_map[title]
            states = dict(re.findall(r"(\w+)=(\d+)ms", s))
            total = sum(int(v) for v in states.values()) or 1
            sleep_pct = int(states.get("S", 0)) * 100 // total
            runnable_pct = int(states.get("R", 0)) * 100 // total
            if sleep_pct > 40:
                findings.append(f"主线程 {sleep_pct}% 时间被阻塞")
            if runnable_pct > 10:
                findings.append(f"调度竞争严重（Runnable {runnable_pct}%）")
            break

    # Binder
    for title in ("Binder 调用", "Binder transactions"):
        if title in ev_map:
            s = ev_map[title]
            max_match = re.search(r"max=(\d+)ms", s)
            if max_match and int(max_match.group(1)) > 16:
                findings.append(f"Binder 调用最长 {max_match.group(1)}ms")
            break

    if not findings:
        # Fallback to generic
        parts: list[str] = []
        if any(t in titles for t in ("长耗时操作", "Long slices")):
            parts.append("关键线程存在长耗时操作")
        if any(t in titles for t in ("调度延迟", "Scheduling delay")):
            parts.append("存在调度延迟")
        if any(t in titles for t in ("线程阻塞", "Blocked threads")):
            parts.append("线程阻塞")
        if not parts:
            return "初步分析完成"
        return "分析结论：" + "；".join(parts) + "。"

    return "诊断摘要：" + "，".join(findings) + "。"


def _build_directions(evidence: list[EvidenceItem]) -> list[str]:
    titles = {e.title for e in evidence}
    directions: list[str] = []

    if "Long slices" in titles:
        directions.append("排查长耗时操作 — 考虑拆分耗时任务或移到非主线程执行")
    if "Scheduling delay" in titles:
        directions.append("检查 CPU 竞争 — 线程在 Runnable 状态等待说明调度压力大")
    if "Blocked threads" in titles:
        directions.append("排查阻塞原因 — 关注锁竞争、Binder 调用或 I/O 等待")
    if "Frame rhythm" in titles:
        directions.append("检查渲染管线 — 掉帧说明渲染或合成存在瓶颈")
    if "Cross-process dependencies" in titles:
        directions.append("检查跨进程调用 — Binder 或 IPC 延迟可能是卡顿原因")
    if "Binder transactions" in titles:
        directions.append("优化 Binder 调用 — 减少调用频率或数据传输量")

    if not directions:
        directions.append("检查异常窗口中得分最高的区间和目标进程的关键线程")

    return directions


def _build_uncertainties(evidence: list[EvidenceItem]) -> list[str]:
    uncertainties: list[str] = []
    titles = {e.title for e in evidence}

    if "Frame rhythm" not in titles:
        uncertainties.append("缺少帧节奏数据 — trace 中可能没有帧相关的 slice")
    if "Cross-process dependencies" not in titles and "Binder transactions" not in titles:
        uncertainties.append("缺少跨进程依赖数据")

    return uncertainties
