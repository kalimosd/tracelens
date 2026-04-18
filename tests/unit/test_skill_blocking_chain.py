from tracelens.skills.blocking_chain import BlockingChainSkill


def test_finds_blocked_threads():
    states = [
        {"thread_name": "main", "state": "S", "dur": 10_000_000},
        {"thread_name": "main", "state": "D", "dur": 5_000_000},
        {"thread_name": "main", "state": "Running", "dur": 20_000_000},
        {"thread_name": "render", "state": "S", "dur": 3_000_000},
    ]
    result = BlockingChainSkill().run(states)
    assert len(result) == 2
    assert result[0]["thread_name"] == "main"
    assert result[0]["total_blocked_ms"] == 15
    assert result[0]["max_single_ms"] == 10
    assert result[0]["block_count"] == 2
    assert result[0]["state_breakdown"]["S"] == 10
    assert result[0]["state_breakdown"]["D"] == 5
    assert result[1]["thread_name"] == "render"


def test_empty_when_no_blocked():
    states = [{"thread_name": "main", "state": "Running", "dur": 10_000_000}]
    assert BlockingChainSkill().run(states) == []
