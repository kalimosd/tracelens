class ProcessThreadDiscoverySkill:
    def run(
        self, threads: list[dict[str, str]], focused_process: str | None = None
    ) -> list[dict[str, str]]:
        if focused_process is None:
            return threads
        return [thread for thread in threads if thread.get("process_name") == focused_process]
