from fastapi import FastAPI

from tracelens.app.api import create_app


def test_create_app_returns_fastapi_instance():
    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.title == "TraceLens"
