from tracelens.agent.planner import choose_analysis_strategy


def test_choose_analysis_strategy_prefers_window_first_without_process():
    strategy = choose_analysis_strategy(has_focused_process=False)

    assert strategy == "window-first"


def test_choose_analysis_strategy_prefers_role_first_with_process():
    strategy = choose_analysis_strategy(has_focused_process=True)

    assert strategy == "role-first"
