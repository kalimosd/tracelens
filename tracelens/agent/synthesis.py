from tracelens.types import AnalysisResult, EvidenceItem


def synthesize_result(
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
