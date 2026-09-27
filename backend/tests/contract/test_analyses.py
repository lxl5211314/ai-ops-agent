import uuid
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ALLOWED_ROOT = str(FIXTURES.resolve())


def _ready_project(client) -> str:
    projects = client.get("/api/v1/projects").json()
    for p in projects:
        if p["source_path"] == ALLOWED_ROOT and p["status"] == "READY":
            return p["id"]
    folders = client.get("/api/v1/folders").json()
    fid = next((f["id"] for f in folders if f["name"] == "analysis-folder"), None)
    if fid is None:
        fid = client.post("/api/v1/folders", json={"name": "analysis-folder"}).json()["id"]
    resp = client.post(
        "/api/v1/projects",
        json={
            "folder_id": fid,
            "name": "analysis-sample",
            "source_type": "path",
            "source_path": ALLOWED_ROOT,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "READY"
    return resp.json()["id"]


def _ingesting_project(client) -> str:
    from core.db import SessionLocal
    from models.project import Folder, Project

    db = SessionLocal()
    try:
        folder = db.query(Folder).first()
        if folder is None:
            folder = Folder(name="tmp-folder")
            db.add(folder)
            db.commit()
        project = Project(
            folder_id=folder.id,
            name="not-ready",
            source_type="path",
            source_path=f"/tmp/not-ready-{uuid.uuid4().hex[:6]}",
            storage_dir="",
            status="INGESTING",
        )
        db.add(project)
        db.commit()
        return str(project.id)
    finally:
        db.close()


def test_analysis_requires_ready_project(client):
    pid = _ingesting_project(client)
    resp = client.post(f"/api/v1/projects/{pid}/analyses", json={"description": "some bug"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_analysis_missing_project(client):
    resp = client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/analyses",
        json={"description": "some bug"},
    )
    assert resp.status_code == 404


def test_analysis_empty_description(client):
    pid = _ready_project(client)
    resp = client.post(f"/api/v1/projects/{pid}/analyses", json={"description": ""})
    assert resp.status_code == 400


def test_analysis_full_pipeline(client, wait_until):
    pid = _ready_project(client)
    description = "登录接口报 KeyError: 'token'，用户无法登录，涉及 app.py"

    resp = client.post(f"/api/v1/projects/{pid}/analyses", json={"description": description})
    assert resp.status_code == 202, resp.text
    aid = resp.json()["analysis_id"]
    assert resp.json()["stream_url"].endswith("/stream")

    def finished():
        row = client.get(f"/api/v1/analyses/{aid}").json()
        return row if row["status"] in ("SUCCEEDED", "FAILED") else None

    row = wait_until(finished, timeout=30)
    assert row["status"] == "SUCCEEDED", row
    assert row["located_files"], row
    assert row["root_cause"]
    assert row["fix_suggestion"]
    assert row["patch_text"]
    assert row["patch_applicable"] is True, (
        row["validation_log"],
        repr(row["patch_text"]),
        [f["file"] for f in row["located_files"]],
    )

    listed = client.get(f"/api/v1/projects/{pid}/analyses").json()
    assert any(a["id"] == aid for a in listed)


def test_duplicate_unfinished_description_returns_existing(client):
    import uuid as uuid_mod

    from core.db import SessionLocal
    from models.analysis import PENDING, BugAnalysis

    pid = _ready_project(client)
    description = "并发提交的重复描述：NPE at Handler.dispatch"

    db = SessionLocal()
    try:
        row = BugAnalysis(
            project_id=uuid_mod.UUID(pid),
            bug_description=description,
            status=PENDING,
        )
        db.add(row)
        db.commit()
        existing_id = str(row.id)
    finally:
        db.close()

    resp = client.post(f"/api/v1/projects/{pid}/analyses", json={"description": description})
    assert resp.status_code == 202
    assert resp.json()["deduplicated"] is True
    assert resp.json()["analysis_id"] == existing_id


def test_failed_analysis_retry(client):
    from core.db import SessionLocal
    from models.analysis import FAILED, BugAnalysis

    pid = _ready_project(client)
    db = SessionLocal()
    try:
        row = BugAnalysis(
            project_id=uuid.UUID(pid),
            bug_description="无法定位的描述",
            status=FAILED,
            error_message="未能在项目中找到相关代码",
        )
        db.add(row)
        db.commit()
        aid = str(row.id)
    finally:
        db.close()

    detail = client.get(f"/api/v1/analyses/{aid}").json()
    assert detail["status"] == "FAILED"
    assert detail["error_message"]

    retry = client.post(f"/api/v1/analyses/{aid}/retry")
    assert retry.status_code == 202
    assert retry.json()["analysis_id"] == aid
