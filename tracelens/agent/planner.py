"""Analysis planner: generates a skill execution plan based on scenario and available data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from tracelens.llm import LLMClient, LLMMessage
from tracelens.skills.yaml_engine import SkillRegistry

PLAN_SYSTEM_PROMPT = """You are a performance analysis planner for Android/Flutter applications.
Given a scenario description and available analysis skills, output a JSON plan.

The plan is a JSON object with:
- "strategy": one of "window-first", "role-first", "frame-first"
- "skills": ordered list of skill IDs to execute
- "reasoning": one sentence explaining why this order

Available skills will be provided. Pick only the relevant ones for the scenario.
Output ONLY valid JSON, no markdown fences."""


@dataclass(slots=True)
class AnalysisPlan:
    strategy: str
    skill_ids: list[str]
    reasoning: str
    chain_steps: list[str] = field(default_factory=list)


def generate_plan(
    scenario: str,
    has_focused_process: bool,
    registry: SkillRegistry,
    llm: LLMClient | None = None,
) -> AnalysisPlan:
    if llm is not None:
        try:
            return _plan_with_llm(scenario, has_focused_process, registry, llm)
        except Exception:
            pass
    return _plan_with_rules(scenario, has_focused_process, registry)


def _plan_with_llm(
    scenario: str,
    has_focused_process: bool,
    registry: SkillRegistry,
    llm: LLMClient,
) -> AnalysisPlan:
    skills_desc = "\n".join(
        f"- {s.id}: {s.description} [category: {s.category}]"
        for s in registry.list_skills()
    )
    user_msg = (
        f"Scenario: {scenario}\n"
        f"Focused process specified: {has_focused_process}\n\n"
        f"Available skills:\n{skills_desc}\n\n"
        f"Output your plan as JSON."
    )

    response = llm.chat([
        LLMMessage(role="system", content=PLAN_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_msg),
    ])

    # Strip markdown fences if present
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    data = json.loads(text)
    skill_ids = data.get("skills", [])
    # Validate skill IDs exist
    valid_ids = [sid for sid in skill_ids if registry.get(sid) is not None]

    return AnalysisPlan(
        strategy=data.get("strategy", "window-first"),
        skill_ids=valid_ids or _default_skill_ids(registry),
        reasoning=data.get("reasoning", "LLM-generated plan"),
        chain_steps=[f"Plan: {data.get('reasoning', '')}"],
    )


def _plan_with_rules(
    scenario: str,
    has_focused_process: bool,
    registry: SkillRegistry,
) -> AnalysisPlan:
    lower = scenario.lower()

    # Scene classification by keywords
    if any(kw in lower for kw in ("滑动", "scroll", "jank", "掉帧", "fps", "帧率", "卡顿")):
        strategy = "frame-first"
        skill_ids = [
            "process_overview",
            "frame_rhythm",
            "per_frame_analysis",
            "long_task_detection",
            "thread_state_distribution",
            "scheduling_delay",
            "blocking_chain",
            "waker_chain",
            "binder_analysis",
            "process_thread_discovery",
        ]
    elif any(kw in lower for kw in ("启动", "startup", "launch", "cold start", "冷启动")):
        strategy = "window-first"
        skill_ids = [
            "process_overview",
            "long_task_detection",
            "thread_state_distribution",
            "blocking_chain",
            "waker_chain",
            "binder_analysis",
            "scheduling_delay",
            "process_thread_discovery",
        ]
    elif has_focused_process:
        strategy = "role-first"
        skill_ids = _default_skill_ids(registry)
    else:
        strategy = "window-first"
        skill_ids = _default_skill_ids(registry)

    # Filter to only skills that exist in registry
    valid_ids = [sid for sid in skill_ids if registry.get(sid) is not None]

    return AnalysisPlan(
        strategy=strategy,
        skill_ids=valid_ids,
        reasoning=f"Rule-based: {strategy} strategy for scenario '{scenario[:50]}'",
        chain_steps=[f"Selected {strategy} strategy"],
    )


def _default_skill_ids(registry: SkillRegistry) -> list[str]:
    return [s.id for s in registry.list_skills()]


# Backward compat
def choose_analysis_strategy(has_focused_process: bool) -> str:
    return "role-first" if has_focused_process else "window-first"
