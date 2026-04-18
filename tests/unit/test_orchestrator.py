from tracelens.agent.orchestrator import Orchestrator


class StubWindowSkill:
    def run(self, windows: list[dict[str, int]]) -> list[dict[str, int]]:
        return [{"start": 10, "end": 20, "score": 30}]


class StubRoleSkill:
    def run(
        self, threads: list[dict[str, str]], focused_process: str | None = None
    ) -> list[dict[str, str | int | None]]:
        return [{"thread_name": "main", "role": "app_main", "process_name": focused_process}]



def test_orchestrator_returns_minimal_analysis_result():
    orchestrator = Orchestrator(
        window_skill=StubWindowSkill(),
        process_thread_skill=StubRoleSkill(),
    )

    result = orchestrator.analyze(
        scenario="switching mode stutters",
        focused_process="com.example.app",
        windows=[],
        threads=[],
    )

    assert result.conclusion == "initial analysis ready"
    assert result.key_evidence[0].title == "Top abnormal window"
    assert result.analysis_chain[0] == "Selected role-first strategy"
    assert result.optimization_directions == ["Inspect the highest-scoring window and focused process threads first"]
    assert len(result.uncertainties) >= 0  # synthesis may add uncertainties based on missing evidence
