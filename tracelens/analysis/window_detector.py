def rank_abnormal_windows(windows: list[dict[str, int]]) -> list[dict[str, int]]:
    ranked: list[dict[str, int]] = []
    for window in windows:
        score = (
            window.get("long_tasks", 0) * 10
            + window.get("blocked_threads", 0) * 7
            + window.get("scheduler_delay_ms", 0)
        )
        ranked.append({**window, "score": score})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)
