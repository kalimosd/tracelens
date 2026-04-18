SYSTEM_PROCESS_NAMES = {
    "system_server",
    "surfaceflinger",
    "android.hardware.graphics.composer3-service",
    "zygote",
    "zygote64",
    "servicemanager",
    "hwservicemanager",
    "vold",
    "logd",
    "lmkd",
    "installd",
    "netd",
    "adbd",
    "debuggerd",
    "healthd",
    "audioserver",
    "cameraserver",
    "mediaserver",
    "mediadrmserver",
    "drmserver",
    "gatekeeperd",
    "keystore",
    "tombstoned",
    "incidentd",
    "statsd",
    "traced",
    "traced_probes",
    "perfetto",
}

# Prefixes that indicate system/kernel/vendor processes
_SYSTEM_PREFIXES = (
    "/system/", "/vendor/", "/apex/", "/init",
    "kworker/", "ksoftirqd/", "migration/", "watchdog/",
    "rcuop/", "rcuos/", "rcuob/", "rcu_",
    "kthreadd", "kswapd", "kcompactd", "khungtaskd",
    "irq/", "ion/",
)


def select_focused_process(
    processes: list[dict[str, object]], explicit_name: str | None = None
) -> dict[str, object] | None:
    if explicit_name:
        for process in processes:
            if process.get("name") == explicit_name:
                return process
    return infer_focused_process(processes)


def infer_focused_process(processes: list[dict[str, object]]) -> dict[str, object] | None:
    """Prefer app processes (com.xxx) over system processes."""
    # First pass: look for com.* app processes (most likely the user's app)
    for process in processes:
        name = process.get("name")
        if isinstance(name, str) and name.startswith("com.") and name not in SYSTEM_PROCESS_NAMES:
            return process

    # Second pass: any non-system, non-kernel process
    for process in processes:
        name = process.get("name")
        if not isinstance(name, str) or not name:
            continue
        if name in SYSTEM_PROCESS_NAMES:
            continue
        if any(name.startswith(p) or name.lower().startswith(p) for p in _SYSTEM_PREFIXES):
            continue
        return process

    return processes[0] if processes else None
