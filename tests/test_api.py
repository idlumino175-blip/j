from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_config_returns_public_auth_shape():
    client = TestClient(app)
    response = client.get("/app-config")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["auth_enabled"], bool)
    assert "firebase_config" in data
    assert "daily_free_renders" in data
