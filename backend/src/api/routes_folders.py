import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db
from api.routes_projects import _cleanup_storage, _folder_out
from core.errors import NOT_FOUND, AppError
from models.project import Folder
from services.project_ingest import create_folder

router = APIRouter(prefix="/folders", tags=["folders"])


class CreateFolder(BaseModel):
    name: str


@router.post("", status_code=201)
def post_folder(body: CreateFolder, db: Session = Depends(get_db)):
    return _folder_out(create_folder(db, body.name), [])


@router.get("")
def list_folders(db: Session = Depends(get_db)):
    folders = db.query(Folder).order_by(Folder.created_at.desc()).all()
    return [_folder_out(f) for f in folders]


@router.delete("/{folder_id}", status_code=204)
def delete_folder(folder_id: uuid.UUID, db: Session = Depends(get_db)):
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise AppError(NOT_FOUND, "文件夹不存在")
    for project in list(folder.projects):
        _cleanup_storage(project)
    db.delete(folder)
    db.commit()
