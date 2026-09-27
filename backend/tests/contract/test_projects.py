from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SAMPLE = FIXTURES / "sample-bug-project"


def _folder(client, name="demo"):
    resp = client.post("/api/v1/folders", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_create_folder_and_duplicate(client):
    name = "folder-a"
    client.post("/api/v1/folders", json={"name": name})
    dup = client.post("/api/v1/folders", json={"name": name})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "CONFLICT"


def test_empty_folder_name(client):
    resp = client.post("/api/v1/folders", json={"name": "  "})
    assert resp.status_code == 400


def test_path_outside_allowlist_rejected(client):
    fid = _folder(client, "folder-b")
    resp = client.post(
        "/api/v1/projects",
        json={
            "folder_id": fid,
            "source_type": "path",
            "source_path": str(FIXTURES.parent.parent / "src"),
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION"
    projects = client.get("/api/v1/projects").json()
    assert not any(p["source_path"] == str(FIXTURES.parent.parent / "src") for p in projects)


def test_path_connect_ready_and_duplicate(client):
    fid = _folder(client, "folder-c")
    payload = {
        "folder_id": fid,
        "name": "sample",
        "source_type": "path",
        "source_path": str(SAMPLE),
    }
    resp = client.post("/api/v1/projects", json=payload)
    assert resp.status_code == 201, resp.text
    project = resp.json()
    assert project["status"] == "READY"
    assert project["file_count"] >= 1

    dup = client.post("/api/v1/projects", json=payload)
    assert dup.status_code == 409

    detail = client.get(f"/api/v1/projects/{project['id']}").json()
    assert detail["tree_preview"]
    files = client.get(f"/api/v1/projects/{project['id']}/files").json()
    assert any(f["rel_path"] == "app.py" for f in files)


def test_corrupt_archive_upload_marks_failed(client):
    fid = _folder(client, "folder-d")
    resp = client.post(
        "/api/v1/projects/upload",
        data={"folder_id": fid, "name": "broken"},
        files={"files": ("broken.zip", b"this is not a zip file", "application/zip")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UNPROCESSABLE"
    projects = client.get("/api/v1/projects").json()
    broken = [p for p in projects if p["name"] == "broken"]
    assert broken and broken[0]["status"] == "FAILED"


def test_upload_valid_zip(client):
    import io
    import zipfile

    fid = _folder(client, "folder-e")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("src/main.py", "print('hello')\n")
        zf.writestr("README.md", "# uploaded\n")
    resp = client.post(
        "/api/v1/projects/upload",
        data={"folder_id": fid, "name": "zip-project"},
        files={"files": ("src.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    project = resp.json()
    assert project["status"] == "READY"
    assert project["file_count"] == 2
