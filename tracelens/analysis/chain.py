def build_analysis_chain(
    strategy: str,
    scenario: str,
    focused_process: str | None,
) -> list[str]:
    return [
        f"Selected {strategy} strategy",
        f"Scenario: {scenario}",
        f"Focused process: {focused_process or 'auto-detect'}",
    ]
