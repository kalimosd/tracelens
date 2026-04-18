def choose_analysis_strategy(has_focused_process: bool) -> str:
    return "role-first" if has_focused_process else "window-first"
