"""US2: folders, projects, source_files

Revision ID: 0002_us2
Revises: 0001_us1
Create Date: 2026-09-25

"""
from alembic import op

from core.db import Base
from models import project  # noqa: F401

revision = "0002_us2"
down_revision = "0001_us1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = [
        Base.metadata.tables["folders"],
        Base.metadata.tables["projects"],
        Base.metadata.tables["source_files"],
    ]
    Base.metadata.create_all(bind, tables=tables)


def downgrade() -> None:
    bind = op.get_bind()
    tables = [
        Base.metadata.tables["source_files"],
        Base.metadata.tables["projects"],
        Base.metadata.tables["folders"],
    ]
    Base.metadata.drop_all(bind, tables=tables)
