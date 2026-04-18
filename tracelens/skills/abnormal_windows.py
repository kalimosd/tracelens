from tracelens.analysis.window_detector import rank_abnormal_windows


class AbnormalWindowsSkill:
    def run(self, windows: list[dict[str, int]]) -> list[dict[str, int]]:
        return rank_abnormal_windows(windows)
