from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post("/api/auth/demo-login")
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_demo_user_created() -> None:
    db_path = Path(settings.outputs_dir) / "app.db"
    if db_path.exists():
        db_path.unlink()
    with TestClient(app) as client:
        response = client.post("/api/auth/demo-login")
        assert response.status_code == 200
        assert response.json()["user"]["email"] == "demo@example.com"


def test_register_login_me() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/register",
            json={"email": "user1@example.com", "password": "123", "display_name": "User 1"},
        )
        assert r.status_code == 200
        token = r.json()["access_token"]

        login = client.post("/api/auth/login", json={"email": "user1@example.com", "password": "123"})
        assert login.status_code == 200

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "user1@example.com"


def test_demo_login() -> None:
    with TestClient(app) as client:
        response = client.post("/api/auth/demo-login")
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"


def test_create_chat_and_message() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        chat = client.post("/api/chats", json={"title": "New analysis", "kind": "lab3_chat", "dataset_name": "customers_reviews.csv"}, headers=headers)
        assert chat.status_code == 200
        chat_id = chat.json()["id"]

        msg = client.post(
            f"/api/chats/{chat_id}/messages",
            json={"role": "user", "content": "hello", "blocks": [], "metadata": {}},
            headers=headers,
        )
        assert msg.status_code == 200

        detail = client.get(f"/api/chats/{chat_id}", headers=headers)
        assert detail.status_code == 200
        assert len(detail.json()["messages"]) >= 1


def test_list_builtin_datasets() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get("/api/datasets", headers=headers)
        assert response.status_code == 200
        names = [item["name"] for item in response.json()["items"]]
        assert any(name.endswith(".csv") for name in names)


def test_dataset_preview() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        datasets = client.get("/api/datasets", headers=headers).json()["items"]
        dataset_id = datasets[0]["id"]
        preview = client.get(f"/api/datasets/{dataset_id}/preview", headers=headers)
        assert preview.status_code == 200
        assert "columns" in preview.json()


def test_upload_dataset() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        files = {"file": ("sample_upload.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}
        uploaded = client.post("/api/datasets/upload", files=files, headers=headers)
        assert uploaded.status_code == 200
        dataset_id = uploaded.json()["id"]

        listed = client.get("/api/datasets", headers=headers)
        assert listed.status_code == 200
        assert any(item["id"] == dataset_id for item in listed.json()["items"])

        preview = client.get(f"/api/datasets/{dataset_id}/preview", headers=headers)
        assert preview.status_code == 200


def test_register_artifact_and_download() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        output_file = Path(settings.outputs_dir) / "artifact_test.txt"
        output_file.write_text("hello artifact", encoding="utf-8")

        reg = client.post(
            "/api/artifacts/register",
            json={"kind": "other", "title": "Artifact test", "path": str(output_file), "metadata": {}},
            headers=headers,
        )
        assert reg.status_code == 200
        artifact_id = reg.json()["id"]

        download = client.get(f"/api/artifacts/{artifact_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.content.decode("utf-8") == "hello artifact"


def test_artifact_path_traversal_blocked() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        blocked = client.post(
            "/api/artifacts/register",
            json={"kind": "other", "title": "Bad", "path": "C:/Windows/win.ini", "metadata": {}},
            headers=headers,
        )
        assert blocked.status_code == 400


def test_existing_lab2_status_still_works() -> None:
    with TestClient(app) as client:
        response = client.get("/api/lab2/status")
        assert response.status_code == 200


def test_existing_lab3_status_still_works() -> None:
    with TestClient(app) as client:
        response = client.get("/api/lab3/status")
        assert response.status_code == 200
