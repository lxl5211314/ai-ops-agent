import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from core.db import Base

PENDING = "PENDING"
LOCATING = "LOCATING"
GENERATING = "GENERATING"
VALIDATING = "VALIDATING"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"

STAGES = (PENDING, LOCATING, GENERATING, VALIDATING, SUCCEEDED, FAILED)


class BugAnalysis(Base):
    __tablename__ = "bug_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    bug_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=PENDING)
    located_files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    patch_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    patch_applicable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    validation_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)

    project = relationship("Project")
