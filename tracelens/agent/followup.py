"""Follow-up engine: answer questions based on existing analysis results."""

from __future__ import annotations

from tracelens.llm import LLMClient, LLMMessage
from tracelens.types import AnalysisResult

FOLLOWUP_SYSTEM_PROMPT = """You are a performance analysis assistant. The user has already received
an initial analysis of a Perfetto trace. They are now asking follow-up questions.

You have access to the original analysis result below. Answer based ONLY on the
evidence and analysis chain provided. If the answer cannot be determined from the
existing evidence, say so clearly and suggest what additional data would be needed.

Be concise and specific. Reference thread names, durations, and states from the evidence.
Respond in the same language as the user's question."""


def answer_followup(
    question: str,
    result: AnalysisResult,
    llm: LLMClient | None = None,
) -> str:
    if llm is not None:
        return _answer_with_llm(question, result, llm)
    return _answer_with_rules(question, result)


def _answer_with_llm(question: str, result: AnalysisResult, llm: LLMClient) -> str:
    evidence_text = "\n".join(f"- [{e.title}] {e.summary}" for e in result.key_evidence)
    chain_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(result.analysis_chain))
    directions_text = "\n".join(f"- {d}" for d in result.optimization_directions)
    uncertainties_text = "\n".join(f"- {u}" for u in result.uncertainties) if result.uncertainties else "None"

    context = f"""Original analysis:

Conclusion: {result.conclusion}

Evidence:
{evidence_text}

Analysis chain:
{chain_text}

Optimization directions:
{directions_text}

Uncertainties:
{uncertainties_text}"""

    try:
        return llm.chat([
            LLMMessage(role="system", content=FOLLOWUP_SYSTEM_PROMPT),
            LLMMessage(role="user", content=f"{context}\n\nUser question: {question}"),
        ])
    except Exception:
        return _answer_with_rules(question, result)


def _answer_with_rules(question: str, result: AnalysisResult) -> str:
    """Rule-based follow-up: match question keywords to evidence."""
    lower = question.lower()
    matched: list[str] = []

    keyword_map = {
        ("线程", "thread", "role"): "key_evidence",
        ("阻塞", "block", "sleep", "waiting"): "Blocked threads",
        ("调度", "schedule", "delay", "runnable"): "Scheduling delay",
        ("帧", "frame", "jank", "fps", "掉帧"): "Frame rhythm",
        ("长", "long", "slow", "耗时"): "Long slices",
        ("状态", "state", "distribution"): "Thread state distribution",
        ("进程", "process", "binder", "跨进程"): "Cross-process dependencies",
        ("优化", "optimize", "建议", "direction"): "directions",
        ("结论", "conclusion", "总结", "summary"): "conclusion",
    }

    for keywords, target in keyword_map.items():
        if any(kw in lower for kw in keywords):
            if target == "key_evidence":
                for e in result.key_evidence:
                    matched.append(f"[{e.title}] {e.summary}")
            elif target == "directions":
                matched.extend(result.optimization_directions)
            elif target == "conclusion":
                matched.append(result.conclusion)
            else:
                for e in result.key_evidence:
                    if e.title == target:
                        matched.append(f"[{e.title}] {e.summary}")

    if not matched:
        # Return all evidence as context
        matched.append(f"Conclusion: {result.conclusion}")
        for e in result.key_evidence:
            matched.append(f"[{e.title}] {e.summary}")
        matched.append("\n(Tip: configure an LLM API key for more detailed follow-up answers)")

    return "\n".join(matched)
