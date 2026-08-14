def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Tasks</title>" in response.text


def test_create_task_applies_defaults(make_task):
    task = make_task(title="  Buy milk  ")
    assert task["title"] == "Buy milk"
    assert task["priority"] == "medium"
    assert task["notes"] == ""
    assert task["due_date"] is None
    assert task["completed"] is False
    assert task["completed_at"] is None


def test_create_task_with_all_fields(make_task):
    task = make_task(
        title="Ship release",
        notes="Tag the commit first",
        priority="high",
        due_date="2030-01-15",
    )
    assert task["notes"] == "Tag the commit first"
    assert task["priority"] == "high"
    assert task["due_date"] == "2030-01-15"


def test_blank_title_is_rejected(client):
    response = client.post("/api/tasks", json={"title": "   "})
    assert response.status_code == 422


def test_invalid_priority_is_rejected(client):
    response = client.post("/api/tasks", json={"title": "x", "priority": "urgent"})
    assert response.status_code == 422


def test_get_task(client, make_task):
    created = make_task()
    response = client.get(f"/api/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_task_returns_404(client):
    assert client.get("/api/tasks/999").status_code == 404


def test_completing_a_task_sets_completed_at(client, make_task):
    task = make_task()
    response = client.patch(f"/api/tasks/{task['id']}", json={"completed": True})
    assert response.status_code == 200
    assert response.json()["completed"] is True
    assert response.json()["completed_at"] is not None

    reopened = client.patch(f"/api/tasks/{task['id']}", json={"completed": False})
    assert reopened.json()["completed_at"] is None


def test_partial_update_leaves_other_fields_alone(client, make_task):
    task = make_task(notes="keep me", priority="high", due_date="2030-02-01")
    response = client.patch(f"/api/tasks/{task['id']}", json={"title": "Renamed"})
    updated = response.json()

    assert updated["title"] == "Renamed"
    assert updated["notes"] == "keep me"
    assert updated["priority"] == "high"
    assert updated["due_date"] == "2030-02-01"


def test_due_date_can_be_cleared(client, make_task):
    task = make_task(due_date="2030-02-01")
    response = client.patch(f"/api/tasks/{task['id']}", json={"due_date": None})
    assert response.json()["due_date"] is None


def test_update_missing_task_returns_404(client):
    assert client.patch("/api/tasks/999", json={"title": "x"}).status_code == 404


def test_delete_task(client, make_task):
    task = make_task()
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 404


def test_list_filters_by_status(client, make_task):
    active = make_task(title="Active one")
    done = make_task(title="Done one")
    client.patch(f"/api/tasks/{done['id']}", json={"completed": True})

    def titles(status):
        return [t["title"] for t in client.get(f"/api/tasks?status={status}").json()]

    assert titles("all") == ["Active one", "Done one"]
    assert titles("active") == [active["title"]]
    assert titles("completed") == [done["title"]]


def test_list_orders_unfinished_and_urgent_first(client, make_task):
    make_task(title="Low", priority="low")
    make_task(title="High", priority="high")
    medium = make_task(title="Medium", priority="medium")
    client.patch(f"/api/tasks/{medium['id']}", json={"completed": True})

    titles = [t["title"] for t in client.get("/api/tasks").json()]
    assert titles == ["High", "Low", "Medium"]


def test_earlier_due_dates_come_first(client, make_task):
    make_task(title="Later", due_date="2030-06-01")
    make_task(title="Sooner", due_date="2030-01-01")
    make_task(title="Undated")

    titles = [t["title"] for t in client.get("/api/tasks").json()]
    assert titles == ["Sooner", "Later", "Undated"]


def test_clear_completed_only_removes_finished_tasks(client, make_task):
    keep = make_task(title="Keep")
    done = make_task(title="Remove")
    client.patch(f"/api/tasks/{done['id']}", json={"completed": True})

    response = client.delete("/api/tasks/completed")
    assert response.status_code == 200
    assert response.json() == {"deleted": 1}

    remaining = [t["title"] for t in client.get("/api/tasks").json()]
    assert remaining == [keep["title"]]


def test_stats(client, make_task):
    assert client.get("/api/stats").json() == {"total": 0, "active": 0, "completed": 0}

    make_task(title="One")
    done = make_task(title="Two")
    client.patch(f"/api/tasks/{done['id']}", json={"completed": True})

    assert client.get("/api/stats").json() == {"total": 2, "active": 1, "completed": 1}


def test_data_survives_a_restart(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    db_path = tmp_path / "persist.db"

    with TestClient(create_app(db_path)) as first:
        first.post("/api/tasks", json={"title": "Persisted"})

    with TestClient(create_app(db_path)) as second:
        assert [t["title"] for t in second.get("/api/tasks").json()] == ["Persisted"]
