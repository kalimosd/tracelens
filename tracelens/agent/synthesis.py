from __future__ import annotations

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
    parts: list[str] = []

    if "Long slices" in titles:
        parts.append("long slices detected on critical threads")
    if "Scheduling delay" in titles:
        parts.append("scheduling delays present")
    if "Blocked threads" in titles:
        parts.append("thread blocking observed")
    if "Frame rhythm" in titles:
        for e in evidence:
            if e.title == "Frame rhythm" and "jank" in e.summary and "0 jank" not in e.summary:
                parts.append("frame jank detected")
                break

    if not parts:
        return "initial analysis ready"
    return "Analysis: " + "; ".join(parts) + "."


def _build_directions(evidence: list[EvidenceItem]) -> list[str]:
    titles = {e.title for e in evidence}
    directions: list[str] = []

    if "Long slices" in titles:
        directions.append("Investigate long slices — consider breaking up heavy work or moving it off the main thread")
    if "Scheduling delay" in titles:
        directions.append("Check CPU contention — threads waiting in runnable state suggest scheduling pressure")
    if "Blocked threads" in titles:
        directions.append("Examine blocking causes — look for lock contention, binder calls, or I/O waits")
    if "Frame rhythm" in titles:
        directions.append("Review frame pipeline — jank frames indicate rendering or composition bottlenecks")
    if "Cross-process dependencies" in titles:
        directions.append("Check cross-process calls — binder or IPC latency may contribute to delays")

    if not directions:
        directions.append("Inspect the highest-scoring window and focused process threads first")

    return directions


def _build_uncertainties(evidence: list[EvidenceItem]) -> list[str]:
    uncertainties: list[str] = []
    titles = {e.title for e in evidence}

    if "Frame rhythm" not in titles:
        uncertainties.append("No frame rhythm data — trace may lack frame-related slices")
    if "Cross-process dependencies" not in titles:
        uncertainties.append("No cross-process dependency data available")

    return uncertainties
