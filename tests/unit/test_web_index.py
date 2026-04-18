from fastapi.testclient import TestClient

from tracelens.app.api import create_app


def test_index_route_returns_trace_lens_page():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "TraceLens" in response.text
    assert "Scenario" in response.text
