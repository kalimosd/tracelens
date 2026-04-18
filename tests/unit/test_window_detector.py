from tracelens.analysis.window_detector import rank_abnormal_windows


def test_rank_abnormal_windows_orders_by_highest_score():
    windows = [
        {"start": 0, "end": 16_000_000, "long_tasks": 0, "blocked_threads": 0, "scheduler_delay_ms": 1},
        {"start": 16_000_000, "end": 32_000_000, "long_tasks": 2, "blocked_threads": 1, "scheduler_delay_ms": 5},
        {"start": 32_000_000, "end": 48_000_000, "long_tasks": 1, "blocked_threads": 0, "scheduler_delay_ms": 2},
    ]

    ranked = rank_abnormal_windows(windows)

    assert ranked[0]["start"] == 16_000_000
    assert ranked[0]["score"] > ranked[1]["score"] > ranked[2]["score"]
