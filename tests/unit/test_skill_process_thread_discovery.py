from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill


def test_process_thread_discovery_filters_threads_for_focused_process():
    skill = ProcessThreadDiscoverySkill()
    threads = [
        {"process_name": "com.example.app", "thread_name": "main"},
        {"process_name": "com.example.app", "thread_name": "RenderThread"},
        {"process_name": "system_server", "thread_name": "binder:100"},
    ]

    result = skill.run(threads=threads, focused_process="com.example.app")

    assert result == [
        {"process_name": "com.example.app", "thread_name": "main"},
        {"process_name": "com.example.app", "thread_name": "RenderThread"},
    ]
