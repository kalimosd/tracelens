from tracelens.trace.focused_process import infer_focused_process, select_focused_process


def test_select_focused_process_prefers_explicit_name():
    processes = [
        {"name": "system_server", "pid": 1000},
        {"name": "com.example.app", "pid": 2000},
    ]
    result = select_focused_process(processes, explicit_name="com.example.app")
    assert result == {"name": "com.example.app", "pid": 2000}


def test_infer_focused_process_prefers_non_system_process():
    processes = [
        {"name": "system_server", "pid": 1000},
        {"name": "surfaceflinger", "pid": 1013},
        {"name": "com.example.app", "pid": 2001},
    ]
    result = infer_focused_process(processes)
    assert result == {"name": "com.example.app", "pid": 2001}


def test_infer_skips_kernel_and_system_paths():
    processes = [
        {"name": "/system/bin/init", "pid": 1},
        {"name": "kthreadd", "pid": 2},
        {"name": "ksoftirqd/0", "pid": 3},
        {"name": "/vendor/bin/hw/some.service", "pid": 100},
        {"name": "com.google.android.apps.nexuslauncher", "pid": 1842},
    ]
    result = infer_focused_process(processes)
    assert result["name"] == "com.google.android.apps.nexuslauncher"


def test_infer_prefers_com_prefix():
    processes = [
        {"name": "some_daemon", "pid": 100},
        {"name": "com.android.systemui", "pid": 1664},
    ]
    result = infer_focused_process(processes)
    assert result["name"] == "com.android.systemui"
