"""CLI output renderer: summary table + evidence + directions."""

from __future__ import annotations

import re

from tracelens.types import AnalysisResult


def render_analysis(result: AnalysisResult) -> str:
    sections: list[str] = []

    # === Summary table ===
    summary = _build_summary_table(result)
    if summary:
        sections.append(summary)
        sections.append("")

    # === Conclusion ===
    sections.append(f"📋 {result.conclusion}")
    sections.append("")

    # === Key evidence ===
    sections.append("── 关键证据 " + "─" * 40)
    for item in result.key_evidence:
        sections.append(f"\n▸ {item.title}")
        for line in item.summary.split("\n"):
            sections.append(f"  {line}")
    sections.append("")

    # === Optimization directions ===
    sections.append("── 优化方向 " + "─" * 40)
    for i, d in enumerate(result.optimization_directions, 1):
        sections.append(f"  {i}. {d}")
    sections.append("")

    # === Uncertainties ===
    if result.uncertainties:
        sections.append("── 不确定性 " + "─" * 40)
        for u in result.uncertainties:
            sections.append(f"  ⚠ {u}")
        sections.append("")

    # === Analysis chain (collapsed) ===
    sections.append("── 分析链 " + "─" * 42)
    for step in result.analysis_chain:
        sections.append(f"  · {step}")

    return "\n".join(sections)


def _build_summary_table(result: AnalysisResult) -> str:
    """Extract key metrics from evidence and build a summary table."""
    metrics: list[tuple[str, str]] = []

    for e in result.key_evidence:
        title = e.title
        summary = e.summary.split("\n")[0]  # First line only

        if title == "Process overview":
            metrics.append(("进程概览", summary))

        elif title == "Frame rhythm":
            metrics.append(("帧统计", summary))

        elif title == "Thread state distribution":
            # Parse percentages
            states = dict(re.findall(r"(\w+)=(\d+)ms", summary))
            total = sum(int(v) for v in states.values()) or 1
            running_pct = int(states.get("Running", 0)) * 100 // total
            sleep_pct = int(states.get("S", 0)) * 100 // total
            runnable_pct = int(states.get("R", 0)) * 100 // total
            metrics.append(("主线程状态", f"Running {running_pct}% / Sleep {sleep_pct}% / Runnable {runnable_pct}%"))

        elif title == "Scheduling delay":
            metrics.append(("调度延迟", summary))

        elif title == "Binder transactions":
            metrics.append(("Binder 调用", summary))

        elif title == "Long slices" and "→" not in summary:
            # Only the raw data line, not interpreted
            first_slice = summary.split(";")[0].strip()
            metrics.append(("最长耗时", first_slice))

    if not metrics:
        return ""

    # Find max label width
    max_label = max(len(m[0]) for m in metrics)
    lines = ["┌─ 分析概览 " + "─" * 42 + "┐"]
    for label, value in metrics:
        lines.append(f"│ {label:<{max_label + 2}}{value}")
    lines.append("└" + "─" * 54 + "┘")
    return "\n".join(lines)
