from fastapi.testclient import TestClient

from tracelens.app.api import create_app


def test_analyze_route_renders_result_page():
    client = TestClient(create_app())

    response = client.post(
        "/analyze",
        data={"scenario": "switching mode stutters", "process": "com.example.app"},
    )

    assert response.status_code == 200
    assert "initial analysis ready" in response.text
    assert "Top abnormal window" in response.text
