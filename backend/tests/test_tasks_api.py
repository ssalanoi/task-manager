from datetime import date, timedelta


def _future(days: int = 1) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_health_no_auth(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_requires_api_key(client):
    r = client.post("/tasks", json={"title": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Missing or invalid API key"


def test_create_rejects_wrong_api_key(client):
    r = client.post("/tasks", json={"title": "x"}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_create_and_get(client, auth_headers):
    r = client.post(
        "/tasks",
        json={"title": "Buy milk", "priority": "high", "due_date": _future(2), "tags": ["Home", "home", "urgent"]},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] >= 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "todo"
    assert body["priority"] == "high"
    assert body["tags"] == ["home", "urgent"]  # normalised + deduped

    rid = body["id"]
    r2 = client.get(f"/tasks/{rid}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == rid


def test_create_validation_empty_title(client, auth_headers):
    r = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert r.status_code == 422


def test_create_rejects_past_due_date(client, auth_headers):
    past = (date.today() - timedelta(days=1)).isoformat()
    r = client.post("/tasks", json={"title": "old", "due_date": past}, headers=auth_headers)
    assert r.status_code == 422


def test_list_filters_by_status(client, auth_headers):
    client.post("/tasks", json={"title": "a"}, headers=auth_headers)
    r = client.post("/tasks", json={"title": "b"}, headers=auth_headers)
    bid = r.json()["id"]
    client.put(f"/tasks/{bid}", json={"status": "done"}, headers=auth_headers)

    r = client.get("/tasks?status=done", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1 and items[0]["id"] == bid


def test_list_filter_by_tag(client, auth_headers):
    client.post(
        "/tasks",
        json={"title": "x", "tags": ["work"], "due_date": _future(1)},
        headers=auth_headers,
    )
    client.post("/tasks", json={"title": "y", "tags": ["home"]}, headers=auth_headers)
    r = client.get("/tasks?tag=work", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1 and items[0]["title"] == "x"


def test_update_partial(client, auth_headers):
    r = client.post("/tasks", json={"title": "draft"}, headers=auth_headers)
    tid = r.json()["id"]
    r2 = client.put(
        f"/tasks/{tid}",
        json={"status": "in_progress", "priority": "urgent"},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "urgent"
    assert body["title"] == "draft"


def test_update_404(client, auth_headers):
    r = client.put("/tasks/999999", json={"title": "z"}, headers=auth_headers)
    assert r.status_code == 404


def test_delete_and_404(client, auth_headers):
    r = client.post("/tasks", json={"title": "to-go"}, headers=auth_headers)
    tid = r.json()["id"]
    r2 = client.delete(f"/tasks/{tid}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json() == {"deleted": True, "id": tid}
    r3 = client.get(f"/tasks/{tid}", headers=auth_headers)
    assert r3.status_code == 404
