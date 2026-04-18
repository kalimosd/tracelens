from fastapi.testclient import TestClient

from tracelens.app.api import create_app


def test_followup_route_returns_not_found_for_unknown_session():
    client = TestClient(create_app())

    response = client.post("/followup", data={"session_id": "missing", "question": "why"})

    assert response.status_code == 404
    assert response.json() == {"detail": "session not found"}
