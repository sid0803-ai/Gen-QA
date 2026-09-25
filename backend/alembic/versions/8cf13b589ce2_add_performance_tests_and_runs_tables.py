"""add performance_tests and performance_test_runs tables

Sprint 10: "Performance Testing" domain (module `performance`) - k6-backed
load testing built on top of one already-saved `api_performer` request. See
`app.domains.performance.models`'s module docstring for the full shape and
scope cuts this implements.

Brand-new tables, no backfill required.

Revision ID: 8cf13b589ce2
Revises: f10921de78c0
Create Date: 2026-09-25 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8cf13b589ce2'
down_revision: Union[str, None] = 'f10921de78c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'performance_tests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('saved_request_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('vus', sa.Integer(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sequence', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['saved_request_id'], ['saved_api_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence'),
    )
    op.create_table(
        'performance_test_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('performance_test_id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('queued', 'running', 'completed', 'failed', name='performance_test_run_status'),
            nullable=False,
        ),
        sa.Column('vus', sa.Integer(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('request_count', sa.Integer(), nullable=True),
        sa.Column('failed_count', sa.Integer(), nullable=True),
        sa.Column('error_rate', sa.Float(), nullable=True),
        sa.Column('avg_duration_ms', sa.Float(), nullable=True),
        sa.Column('p95_duration_ms', sa.Float(), nullable=True),
        sa.Column('min_duration_ms', sa.Float(), nullable=True),
        sa.Column('max_duration_ms', sa.Float(), nullable=True),
        sa.Column('requests_per_second', sa.Float(), nullable=True),
        sa.Column('raw_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('sequence', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['performance_test_id'], ['performance_tests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence'),
    )


def downgrade() -> None:
    op.drop_table('performance_test_runs')
    op.drop_table('performance_tests')
    sa.Enum(name='performance_test_run_status').drop(op.get_bind(), checkfirst=True)
