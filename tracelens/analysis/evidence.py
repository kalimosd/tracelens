from tracelens.types import EvidenceItem


def make_top_window_evidence(
    top_window: dict[str, int],
    primary_role: dict[str, str | int | None],
) -> EvidenceItem:
    return EvidenceItem(
        title="Top abnormal window",
        summary=(
            f"window {top_window['start']}..{top_window['end']} score={top_window['score']}; "
            f"primary role={primary_role['role']}"
        ),
    )
