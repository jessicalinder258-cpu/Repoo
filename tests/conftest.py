import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def make_task(client):
    def _make(**overrides):
        payload = {"title": "Write the report"} | overrides
        response = client.post("/api/tasks", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _make
