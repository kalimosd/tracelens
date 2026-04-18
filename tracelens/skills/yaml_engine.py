"""YAML Skill engine: load declarative skill definitions and execute them against a TraceSession."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tracelens.trace.processor import TraceSession

SKILLS_DIR = Path(__file__).parent / "definitions"


@dataclass(slots=True)
class SkillStep:
    id: str
    sql: str
    display_level: str = "detail"  # summary | key | detail | hidden


@dataclass(slots=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    category: str  # scrolling | startup | general | ...
    parameters: list[dict[str, str]]  # [{name, type, default?}]
    steps: list[SkillStep]

    @staticmethod
    def from_yaml(path: Path) -> SkillDefinition:
        with open(path) as f:
            raw = yaml.safe_load(f)
        steps = []
        for s in raw.get("steps", []):
            steps.append(SkillStep(
                id=s["id"],
                sql=s["sql"].strip(),
                display_level=s.get("display", {}).get("level", "detail"),
            ))
        return SkillDefinition(
            id=raw["id"],
            name=raw["name"],
            description=raw.get("description", ""),
            category=raw.get("category", "general"),
            parameters=raw.get("parameters", []),
            steps=steps,
        )


@dataclass(slots=True)
class SkillResult:
    skill_id: str
    step_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


_PARAM_RE = re.compile(r"\$\{(\w+)(?:\|([^}]*))?\}")


def _substitute_params(sql: str, params: dict[str, Any]) -> str:
    """Replace ${param} or ${param|default} in SQL."""
    def replacer(m: re.Match) -> str:
        name = m.group(1)
        default = m.group(2)
        val = params.get(name)
        if val is None:
            if default is not None:
                return default
            raise ValueError(f"Missing required parameter: {name}")
        return str(val)
    return _PARAM_RE.sub(replacer, sql)


def execute_skill(
    skill: SkillDefinition,
    session: TraceSession,
    params: dict[str, Any] | None = None,
) -> SkillResult:
    """Execute all steps of a skill against a trace session."""
    params = params or {}
    result = SkillResult(skill_id=skill.id)

    for step in skill.steps:
        try:
            sql = _substitute_params(step.sql, params)
            rows = session.query(sql)
            result.step_results[step.id] = rows
        except Exception as e:
            result.errors.append(f"{step.id}: {e}")

    return result


class SkillRegistry:
    """Loads and indexes all YAML skill definitions."""

    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        self._load_all(skills_dir)

    def _load_all(self, skills_dir: Path) -> None:
        if not skills_dir.exists():
            return
        for path in sorted(skills_dir.glob("*.yaml")):
            try:
                skill = SkillDefinition.from_yaml(path)
                self._skills[skill.id] = skill
            except Exception:
                continue

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def list_skills(self, category: str | None = None) -> list[SkillDefinition]:
        if category:
            return [s for s in self._skills.values() if s.category == category]
        return list(self._skills.values())

    @property
    def count(self) -> int:
        return len(self._skills)
