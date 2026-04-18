from fastapi.testclient import TestClient

from tracelens.app.api import create_app


def test_followup_route_returns_not_found_for_unknown_session():
    client = TestClient(create_app())

    response = client.post("/followup", data={"session_id": "missing", "question": "why"})

    assert response.status_code == 404


def test_followup_route_works_after_analyze():
    client = TestClient(create_app())

    # First do an analysis to get a session_id
    resp = client.post("/analyze", data={"scenario": "test", "process": "com.example.app"})
    assert resp.status_code == 200
    # Extract session_id from the HTML
    import re
    match = re.search(r"Session: ([a-f0-9-]+)", resp.text)
    assert match
    session_id = match.group(1)

    # Now ask a follow-up
    resp2 = client.post("/followup", data={"session_id": session_id, "question": "为什么卡顿？"})
    assert resp2.status_code == 200
    assert "为什么卡顿" in resp2.text
