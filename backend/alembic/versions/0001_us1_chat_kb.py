"""US1: conversations, messages, kb_documents, kb_ingest_jobs

Revision ID: 0001_us1
Revises:
Create Date: 2026-09-25

"""
from alembic import op

from core.db import Base
from models import conversation, kb  # noqa: F401

revision = "0001_us1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = [
        Base.metadata.tables["conversations"],
        Base.metadata.tables["messages"],
        Base.metadata.tables["kb_documents"],
        Base.metadata.tables["kb_ingest_jobs"],
    ]
    Base.metadata.create_all(bind, tables=tables)


def downgrade() -> None:
    bind = op.get_bind()
    tables = [
        Base.metadata.tables["kb_ingest_jobs"],
        Base.metadata.tables["kb_documents"],
        Base.metadata.tables["messages"],
        Base.metadata.tables["conversations"],
    ]
    Base.metadata.drop_all(bind, tables=tables)
