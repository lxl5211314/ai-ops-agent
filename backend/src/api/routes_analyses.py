import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_db, get_llm
from core.errors import NOT_FOUND, VALIDATION, AppError
from llm.client import LLMClient
from models.analysis import FAILED, PENDING, BugAnalysis
from models.project import STATUS_READY, Project

router = APIRouter(tags=["analyses"])


class CreateAnalysis(BaseModel):
    description: str = Field(min_length=1)


def _out(a: BugAnalysis) -> dict:
    return {
        "id": str(a.id),
        "project_id": str(a.project_id),
        "bug_description": a.bug_description,
        "status": a.status,
        "located_files": a.located_files,
        "root_cause": a.root_cause,
        "fix_suggestion": a.fix_suggestion,
        "patch_text": a.patch_text,
        "patch_applicable": a.patch_applicable,
        "validation_log": a.validation_log,
        "error_message": a.error_message,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "finished_at": a.finished_at.isoformat() if a.finished_at else None,
    }


@router.post("/projects/{project_id}/analyses", status_code=202)
def create_analysis(
    project_id: uuid.UUID,
    body: CreateAnalysis,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    project = db.get(Project, project_id)
    if project is None:
        raise AppError(NOT_FOUND, "项目不存在")
    if project.status != STATUS_READY:
        raise AppError("CONFLICT", "项目尚未就绪，请先完成源码接入")
    description = body.description.strip()
    if not description:
        raise AppError(VALIDATION, "Bug 描述不能为空")

    existing = (
        db.query(BugAnalysis)
        .filter(
            BugAnalysis.project_id == project.id,
            BugAnalysis.bug_description == description,
            BugAnalysis.status.in_([PENDING, "LOCATING", "GENERATING", "VALIDATING"]),
        )
        .first()
    )
    if existing:
        return {
            "analysis_id": str(existing.id),
            "stream_url": f"/api/v1/analyses/{existing.id}/stream",
            "deduplicated": True,
        }

    analysis = BugAnalysis(
        project_id=project.id,
        bug_description=description,
        status=PENDING,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    background.add_task(_launch, analysis.id, llm)
    return {
        "analysis_id": str(analysis.id),
        "stream_url": f"/api/v1/analyses/{analysis.id}/stream",
        "deduplicated": False,
    }


async def _launch(analysis_id: uuid.UUID, llm: LLMClient) -> None:
    from services.bug_analysis import run_analysis

    await run_analysis(analysis_id, llm)


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: uuid.UUID, db: Session = Depends(get_db)):
    row = db.get(BugAnalysis, analysis_id)
    if row is None:
        raise AppError(NOT_FOUND, "分析任务不存在")
    return _out(row)


@router.get("/projects/{project_id}/analyses")
def list_analyses(project_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = (
        db.query(BugAnalysis)
        .filter(BugAnalysis.project_id == project_id)
        .order_by(BugAnalysis.created_at.desc())
        .all()
    )
    return [_out(r) for r in rows]


@router.post("/analyses/{analysis_id}/retry", status_code=202)
def retry_analysis(
    analysis_id: uuid.UUID,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    row = db.get(BugAnalysis, analysis_id)
    if row is None:
        raise AppError(NOT_FOUND, "分析任务不存在")
    if row.status not in (FAILED,):
        raise AppError("CONFLICT", "只有失败的分析任务才能重试")
    row.status = PENDING
    row.error_message = None
    db.commit()
    background.add_task(_launch, row.id, llm)
    return {
        "analysis_id": str(row.id),
        "stream_url": f"/api/v1/analyses/{row.id}/stream",
    }
