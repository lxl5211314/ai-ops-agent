import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db
from core.errors import NOT_FOUND, VALIDATION, AppError
from models.project import Folder, Project, SourceFile
from services.project_ingest import ingest_path, ingest_upload

router = APIRouter(tags=["projects"])


class PathConnect(BaseModel):
    folder_id: uuid.UUID
    name: str = ""
    source_type: str = "path"
    source_path: str


def _folder_out(f: Folder, projects: list[Project] | None = None) -> dict:
    return {
        "id": str(f.id),
        "name": f.name,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "projects": [_project_out(p) for p in (projects if projects is not None else f.projects)],
    }


def _project_out(p: Project) -> dict:
    return {
        "id": str(p.id),
        "folder_id": str(p.folder_id),
        "name": p.name,
        "source_type": p.source_type,
        "source_path": p.source_path,
        "file_count": p.file_count,
        "status": p.status,
        "error_message": p.error_message,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _cleanup_storage(project: Project) -> None:
    if project.source_type == "upload" and project.storage_dir:
        path = Path(project.storage_dir)
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)


@router.post("/projects", status_code=201)
def connect_path(body: PathConnect, db: Session = Depends(get_db)):
    if body.source_type != "path":
        raise AppError(VALIDATION, "source_type 必须为 path")
    project = ingest_path(db, body.folder_id, body.name, body.source_path)
    return _project_out(project)


@router.post("/projects/upload", status_code=201)
async def upload_project(
    folder_id: str = Form(...),
    name: str = Form(""),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    try:
        fid = uuid.UUID(folder_id)
    except ValueError as err:
        raise AppError(VALIDATION, "folder_id 非法") from err
    payload: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read()
        payload.append((f.filename or "file", data))
    project = ingest_upload(db, fid, name, payload)
    return _project_out(project)


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [_project_out(p) for p in projects]


def _load_project(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise AppError(NOT_FOUND, "项目不存在")
    return project


@router.get("/projects/{project_id}")
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = _load_project(db, project_id)
    out = _project_out(project)
    root = Path(project.storage_dir) if project.storage_dir else None
    preview: list[str] = []
    if root and root.exists():
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        preview = [p.name + ("/" if p.is_dir() else "") for p in entries[:50]]
    out["tree_preview"] = preview
    out["files_count"] = project.file_count
    return out


@router.get("/projects/{project_id}/files")
def list_files(project_id: uuid.UUID, page: int = 1, size: int = 50, db: Session = Depends(get_db)):
    project = _load_project(db, project_id)
    page = max(1, page)
    size = min(max(1, size), 200)
    rows = (
        db.query(SourceFile)
        .filter(SourceFile.project_id == project.id)
        .order_by(SourceFile.rel_path)
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return [
        {
            "id": f.id,
            "project_id": str(f.project_id),
            "rel_path": f.rel_path,
            "size_bytes": f.size_bytes,
            "is_text": f.is_text,
        }
        for f in rows
    ]


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = _load_project(db, project_id)
    _cleanup_storage(project)
    db.delete(project)
    db.commit()
