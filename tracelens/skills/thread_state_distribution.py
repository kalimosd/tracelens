class ThreadStateDistributionSkill:
    def run(self, slices: list[dict[str, int | str]]) -> list[dict[str, int | str]]:
        totals: dict[str, int] = {}
        for item in slices:
            state = str(item["state"])
            dur_ms = int(item["dur_ms"])
            totals[state] = totals.get(state, 0) + dur_ms
        return [
            {"state": state, "dur_ms": total}
            for state, total in sorted(totals.items(), key=lambda entry: entry[1], reverse=True)
        ]
