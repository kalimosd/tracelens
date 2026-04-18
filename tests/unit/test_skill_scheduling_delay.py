from tracelens.skills.scheduling_delay import SchedulingDelaySkill


def test_sums_runnable_time_per_thread():
    states = [
        {"thread_name": "main", "state": "R", "dur": 2_000_000},
        {"thread_name": "main", "state": "R", "dur": 3_000_000},
        {"thread_name": "main", "state": "Running", "dur": 10_000_000},
        {"thread_name": "render", "state": "R", "dur": 1_000_000},
    ]
    result = SchedulingDelaySkill().run(states)
    assert len(result) == 2
    assert result[0]["thread_name"] == "main"
    assert result[0]["total_delay_ns"] == 5_000_000
    assert result[0]["total_delay_ms"] == 5
    assert result[1]["thread_name"] == "render"


def test_empty_when_no_runnable():
    states = [{"thread_name": "main", "state": "Running", "dur": 10_000_000}]
    assert SchedulingDelaySkill().run(states) == []


def test_ignores_zero_duration():
    states = [{"thread_name": "main", "state": "R", "dur": 0}]
    assert SchedulingDelaySkill().run(states) == []
