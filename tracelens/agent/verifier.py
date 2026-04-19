"""Verification layer: catch common LLM misdiagnosis patterns before output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tracelens.types import AnalysisResult, EvidenceItem


@dataclass(slots=True)
class VerificationFinding:
    level: str  # "warning" | "correction"
    rule: str
    message: str


@dataclass(slots=True)
class VerificationReport:
    findings: list[VerificationFinding] = field(default_factory=list)
    corrected: bool = False

    @property
    def has_issues(self) -> bool:
        return len(self.findings) > 0


# ============================================================
# Layer 1: Heuristic checks — known misdiagnosis patterns
# ============================================================

_HEURISTIC_RULES: list[tuple[str, callable]] = []


def _register(rule_name: str):
    def decorator(fn):
        _HEURISTIC_RULES.append((rule_name, fn))
        return fn
    return decorator


@_register("single_frame_critical")
def _check_single_frame_critical(result: AnalysisResult) -> VerificationFinding | None:
    """Single isolated frame anomaly should not be CRITICAL."""
    text = result.conclusion.lower()
    if ("1 frame" in text or "single frame" in text or "单帧" in text) and (
        "critical" in text or "严重" in text
    ):
        return VerificationFinding(
            level="correction",
            rule="single_frame_critical",
            message="Single frame anomaly marked as CRITICAL — isolated single-frame issues don't constitute a pattern. Should be MEDIUM at most.",
        )
    return None


@_register("buffer_stuffing_as_app_jank")
def _check_buffer_stuffing(result: AnalysisResult) -> VerificationFinding | None:
    """Buffer Stuffing is not an App-side jank — it's a composition queue issue."""
    for e in result.key_evidence:
        lower = e.summary.lower()
        if "buffer stuffing" in lower and ("app" in lower and ("jank" in lower or "掉帧" in lower)):
            return VerificationFinding(
                level="correction",
                rule="buffer_stuffing_as_app_jank",
                message="Buffer Stuffing counted as App jank — Buffer Stuffing means App finished on time but BufferQueue was full. Not an App logic issue.",
            )
    return None


@_register("vsync_offset_critical")
def _check_vsync_offset(result: AnalysisResult) -> VerificationFinding | None:
    """VSync alignment offset on high-refresh devices is normal, not CRITICAL."""
    text = result.conclusion.lower()
    for e in result.key_evidence:
        lower = e.summary.lower()
        if ("vsync" in lower and "offset" in lower) or ("vsync" in lower and "偏移" in lower):
            if "critical" in text or "严重" in text:
                return VerificationFinding(
                    level="correction",
                    rule="vsync_offset_critical",
                    message="VSync offset marked as CRITICAL — modern high-refresh devices have normal ±0.5ms VSync jitter. Should not be flagged as critical.",
                )
    return None


@_register("sleeping_severity")
def _check_sleeping_severity(result: AnalysisResult) -> VerificationFinding | None:
    """Main thread sleeping > 30% of trace duration should be at least MEDIUM."""
    for e in result.key_evidence:
        if e.title != "Thread state distribution":
            continue
        # Parse "S=XXXms" from summary
        match = re.search(r"S=(\d+)ms", e.summary)
        if not match:
            continue
        sleeping_ms = int(match.group(1))
        # Parse total from all states
        total = sum(int(m.group(1)) for m in re.finditer(r"=(\d+)ms", e.summary))
        if total > 0 and sleeping_ms / total > 0.3:
            text = result.conclusion.lower()
            if "low" in text or "minor" in text or "轻微" in text:
                return VerificationFinding(
                    level="warning",
                    rule="sleeping_severity",
                    message=f"Main thread sleeping {sleeping_ms}ms ({sleeping_ms*100//total}% of total) marked as LOW — this ratio suggests at least MEDIUM severity.",
                )
    return None


@_register("no_evidence_for_claim")
def _check_hallucinated_data(result: AnalysisResult) -> VerificationFinding | None:
    """Check if conclusion references specific numbers not found in evidence."""
    # Extract numbers from conclusion
    conclusion_numbers = set(re.findall(r"\b(\d{2,})\b", result.conclusion))
    if not conclusion_numbers:
        return None
    # Extract numbers from all evidence
    evidence_text = " ".join(e.summary for e in result.key_evidence)
    evidence_numbers = set(re.findall(r"\b(\d{2,})\b", evidence_text))
    # Numbers in conclusion but not in evidence
    hallucinated = conclusion_numbers - evidence_numbers
    # Filter out common non-data numbers
    hallucinated = {n for n in hallucinated if int(n) > 1 and int(n) != 16 and int(n) != 100}
    if hallucinated:
        return VerificationFinding(
            level="warning",
            rule="no_evidence_for_claim",
            message=f"Conclusion references numbers {hallucinated} not found in evidence — possible hallucination.",
        )
    return None


# ============================================================
# Layer 2: Evidence consistency checks
# ============================================================

@_register("empty_evidence_with_conclusion")
def _check_empty_evidence(result: AnalysisResult) -> VerificationFinding | None:
    """Conclusion should not make strong claims with no evidence."""
    if len(result.key_evidence) == 0 and result.conclusion and result.conclusion != "initial analysis ready":
        return VerificationFinding(
            level="correction",
            rule="empty_evidence_with_conclusion",
            message="Conclusion generated with no evidence — cannot make claims without data.",
        )
    return None


@_register("directions_without_evidence")
def _check_directions_match_evidence(result: AnalysisResult) -> VerificationFinding | None:
    """Optimization directions should relate to actual evidence found."""
    evidence_titles = {e.title.lower() for e in result.key_evidence}
    if not evidence_titles:
        return None
    # Check if directions mention things not in evidence
    has_binder_direction = any("binder" in d.lower() or "cross-process" in d.lower() for d in result.optimization_directions)
    has_binder_evidence = any("binder" in t or "cross-process" in t or "dependencies" in t for t in evidence_titles)
    if has_binder_direction and not has_binder_evidence:
        return VerificationFinding(
            level="warning",
            rule="directions_without_evidence",
            message="Optimization direction mentions binder/cross-process but no binder evidence was found.",
        )
    return None


# ============================================================
# Public API
# ============================================================

def verify_result(result: AnalysisResult) -> VerificationReport:
    """Run all verification rules against an analysis result."""
    report = VerificationReport()
    for rule_name, check_fn in _HEURISTIC_RULES:
        finding = check_fn(result)
        if finding is not None:
            report.findings.append(finding)
    return report


def apply_corrections(result: AnalysisResult, report: VerificationReport) -> AnalysisResult:
    """Apply corrections from verification findings to the result."""
    if not report.has_issues:
        return result

    warnings = [f.message for f in report.findings]
    # Add verification warnings to uncertainties
    new_uncertainties = list(result.uncertainties) + [f"[Verification] {w}" for w in warnings]

    return AnalysisResult(
        conclusion=result.conclusion,
        key_evidence=result.key_evidence,
        analysis_chain=result.analysis_chain + ["Verification: " + "; ".join(f.rule for f in report.findings)],
        optimization_directions=result.optimization_directions,
        uncertainties=new_uncertainties,
    )
