from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_config_defaults_to_no_auth():
    client = TestClient(app)
    response = client.get("/app-config")
    assert response.status_code == 200
    assert response.json()["auth_required"] is False
