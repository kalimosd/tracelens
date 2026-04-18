from tracelens.semantics.vocabulary import (
    THREAD_ROLE_APP_MAIN,
    THREAD_ROLE_FLUTTER_RASTER,
    THREAD_ROLE_FLUTTER_UI,
    THREAD_ROLE_RENDER,
    THREAD_ROLE_UNKNOWN,
)

# Android kernel truncates thread names to 15 chars. The main thread's name
# equals the process name, so "com.google.android.apps.nexuslauncher" becomes
# "s.nexuslauncher". We detect this by checking if the process name ends with
# the thread name (after truncation).
_KERNEL_COMM_MAX = 15


def identify_thread_role(thread_name: str, process_name: str) -> str:
    normalized = thread_name.strip().lower()
    proc_lower = process_name.strip().lower() if process_name else ""

    if not normalized:
        return THREAD_ROLE_UNKNOWN

    # Exact "main"
    if normalized == "main":
        return THREAD_ROLE_APP_MAIN

    # Android: main thread name == process name (possibly truncated to 15 chars)
    if proc_lower and (
        normalized == proc_lower
        or (len(normalized) >= _KERNEL_COMM_MAX and proc_lower.endswith(normalized))
    ):
        return THREAD_ROLE_APP_MAIN

    if "renderthread" in normalized:
        return THREAD_ROLE_RENDER

    # Flutter
    if normalized in {"1.ui", "ui"}:
        return THREAD_ROLE_FLUTTER_UI
    if normalized in {"1.raster", "raster"}:
        return THREAD_ROLE_FLUTTER_RASTER

    return THREAD_ROLE_UNKNOWN
