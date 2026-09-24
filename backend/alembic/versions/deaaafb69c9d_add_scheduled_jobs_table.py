"""add scheduled_jobs table

Revision ID: deaaafb69c9d
Revises: 57e6f76344ad
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'deaaafb69c9d'
down_revision: Union[str, None] = '57e6f76344ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('test_case_id', sa.UUID(), nullable=False),
        sa.Column('environment_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('cron_expression', sa.String(length=255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sequence', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['environment_id'], ['environments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence'),
    )
    # Hot query path for the Celery Beat periodic task
    # (app.domains.schedules.tasks): `WHERE enabled = true AND next_run_at
    # <= now()`, always scoped per-project in the read/write API too.
    op.create_index(
        'ix_scheduled_jobs_due',
        'scheduled_jobs',
        ['project_id', 'enabled', 'next_run_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_scheduled_jobs_due', table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')
    # scheduled_jobs has no enum-typed columns of its own, so there's no
    # `sa.Enum(...).drop()` needed here (unlike e.g. 57e6f76344ad's
    # downgrade(), which drops the enum types its tables introduced).
