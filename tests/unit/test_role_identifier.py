from tracelens.semantics.role_identifier import identify_thread_role


def test_identify_thread_role_recognizes_android_main_thread():
    role = identify_thread_role(thread_name="main", process_name="com.example.app")
    assert role == "app_main"


def test_identify_thread_role_recognizes_flutter_raster_thread():
    role = identify_thread_role(thread_name="1.raster", process_name="com.example.flutter")
    assert role == "flutter_raster"


def test_identify_thread_role_falls_back_to_unknown():
    role = identify_thread_role(thread_name="worker-17", process_name="com.example.app")
    assert role == "unknown"


def test_truncated_main_thread_nexuslauncher():
    # "com.google.android.apps.nexuslauncher" truncated to 15 chars = "s.nexuslauncher"
    role = identify_thread_role(
        thread_name="s.nexuslauncher",
        process_name="com.google.android.apps.nexuslauncher",
    )
    assert role == "app_main"


def test_truncated_main_thread_systemui():
    # "com.android.systemui" truncated to 15 chars = "ndroid.systemui"
    role = identify_thread_role(
        thread_name="ndroid.systemui",
        process_name="com.android.systemui",
    )
    assert role == "app_main"


def test_exact_process_name_match():
    role = identify_thread_role(
        thread_name="com.example.app",
        process_name="com.example.app",
    )
    assert role == "app_main"


def test_renderthread():
    role = identify_thread_role(thread_name="RenderThread", process_name="com.example.app")
    assert role == "render_thread"


def test_flutter_ui():
    role = identify_thread_role(thread_name="1.ui", process_name="com.example.flutter")
    assert role == "flutter_ui"
