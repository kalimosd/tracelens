from tracelens.skills.thread_state_distribution import ThreadStateDistributionSkill


def test_thread_state_distribution_summarizes_total_duration_per_state():
    skill = ThreadStateDistributionSkill()
    slices = [
        {"state": "Running", "dur_ms": 5},
        {"state": "Running", "dur_ms": 3},
        {"state": "Runnable", "dur_ms": 2},
    ]

    result = skill.run(slices)

    assert result == [
        {"state": "Running", "dur_ms": 8},
        {"state": "Runnable", "dur_ms": 2},
    ]
