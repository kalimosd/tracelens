from tracelens.skills.dependency_summary import DependencySummarySkill


def test_finds_other_processes():
    threads = [
        {"process_name": "com.example.app", "thread_name": "main"},
        {"process_name": "system_server", "thread_name": "binder:500_1"},
        {"process_name": "system_server", "thread_name": "binder:500_2"},
        {"process_name": "surfaceflinger", "thread_name": "sf"},
    ]
    result = DependencySummarySkill().run(threads, [], focused_process="com.example.app")
    assert len(result) == 2
    assert result[0]["process_name"] == "system_server"
    assert result[0]["thread_count"] == 2


def test_counts_binder_slices():
    threads = [
        {"process_name": "system_server", "thread_name": "binder"},
    ]
    slices = [
        {"name": "binder transaction", "dur": 1_000_000},
        {"name": "binder reply", "dur": 500_000},
        {"name": "inflate", "dur": 50_000_000},
    ]
    result = DependencySummarySkill().run(threads, slices, focused_process="com.example.app")
    assert result[0]["binder_slices"] == 2


def test_empty_when_only_focused_process():
    threads = [{"process_name": "com.example.app", "thread_name": "main"}]
    result = DependencySummarySkill().run(threads, [], focused_process="com.example.app")
    assert result == []
