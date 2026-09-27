"""US3: bug_analyses

Revision ID: 0003_us3
Revises: 0002_us2
Create Date: 2026-09-25

"""
from alembic import op

from core.db import Base
from models import analysis  # noqa: F401

revision = "0003_us3"
down_revision = "0002_us2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind, tables=[Base.metadata.tables["bug_analyses"]])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind, tables=[Base.metadata.tables["bug_analyses"]])
