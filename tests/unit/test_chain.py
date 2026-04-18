from tracelens.analysis.chain import build_analysis_chain


def test_build_analysis_chain_includes_strategy_scenario_and_process():
    chain = build_analysis_chain(
        strategy="role-first",
        scenario="switching mode stutters",
        focused_process="com.example.app",
    )

    assert chain == [
        "Selected role-first strategy",
        "Scenario: switching mode stutters",
        "Focused process: com.example.app",
    ]
