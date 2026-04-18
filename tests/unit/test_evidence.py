from tracelens.analysis.evidence import make_top_window_evidence


def test_make_top_window_evidence_summarizes_window_and_role():
    evidence = make_top_window_evidence(
        top_window={"start": 10, "end": 20, "score": 30},
        primary_role={"thread_name": "main", "role": "app_main", "process_name": "com.example.app"},
    )

    assert evidence.title == "Top abnormal window"
    assert evidence.summary == "window 10..20 score=30; primary role=app_main"
