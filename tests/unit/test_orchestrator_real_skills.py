from tracelens.agent.orchestrator import Orchestrator
from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill


def test_orchestrator_uses_real_skills_for_minimal_analysis_result():
    orchestrator = Orchestrator(
        window_skill=AbnormalWindowsSkill(),
        process_thread_skill=ProcessThreadDiscoverySkill(),
    )

    result = orchestrator.analyze(
        scenario="switching mode stutters",
        focused_process="com.example.app",
        windows=[
            {"start": 0, "end": 10, "long_tasks": 0, "blocked_threads": 0, "scheduler_delay_ms": 1},
            {"start": 10, "end": 20, "long_tasks": 2, "blocked_threads": 1, "scheduler_delay_ms": 4},
        ],
        threads=[
            {"process_name": "com.example.app", "thread_name": "main", "role": "app_main"},
            {"process_name": "com.example.app", "thread_name": "RenderThread", "role": "render_thread"},
            {"process_name": "system_server", "thread_name": "binder:100", "role": "unknown"},
        ],
    )

    assert result.key_evidence[0].summary == "window 10..20 score=31; primary role=app_main"
    assert result.analysis_chain == [
        "Selected role-first strategy",
        "Scenario: switching mode stutters",
        "Focused process: com.example.app",
    ]
