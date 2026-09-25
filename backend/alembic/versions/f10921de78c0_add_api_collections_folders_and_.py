"""add api_collections/api_folders tables and collection_id/folder_id to saved_api_requests

Sprint 9: restructures the flat `SavedApiRequest` list (Sprint 8) into a
Postman-style Collection -> Folder (optional, one level) -> Request
hierarchy. See `app.domains.api_performer.models`'s module docstring for
the shape this implements.

Steps, in order:

1. Create `api_collections` and `api_folders`.
2. Add `saved_api_requests.collection_id` (nullable=True for now) and
   `folder_id` (nullable=True, permanently - a request can be filed at a
   collection's top level).
3. **Backfill**: for every `project_id` that has at least one pre-existing
   `saved_api_requests` row with `collection_id IS NULL` (i.e. every project
   with data from before this migration), create exactly one `ApiCollection`
   named "My Requests" for that project, then point every such row at it.
   A project with zero existing requests gets no backfill collection - we
   never manufacture a collection nobody asked for.

   `created_by` on the backfill collection reuses the `created_by` of one of
   that project's own pre-existing `saved_api_requests` rows (arbitrarily,
   the one with the lowest `sequence` - i.e. the oldest). That user is
   already guaranteed to be a real row satisfying `users.id` (the existing
   `saved_api_requests.created_by` FK enforces it) and to be tied to this
   project (they created a request in it). This is simpler and just as
   sound as looking up a project admin via `project_members` (which would
   require that the project still *have* an admin at migration time - not
   actually guaranteed - for no real benefit over reusing data this
   migration is already touching).

   Implemented in Python (not a single raw-SQL `INSERT ... SELECT`) so each
   new collection gets an application-generated UUID via `uuid.uuid4()` (the
   same ID generation `ApiCollection.id`'s ORM `default=uuid.uuid4` would
   use), without depending on a Postgres UUID-generating extension
   (`pgcrypto`/`uuid-ossp`) being installed - standard Alembic practice of
   not importing the ORM models themselves into a migration, per the task's
   own instruction, but nothing stops plain Python here.
4. Alter `collection_id` to NOT NULL - safe now that every existing row has
   been backfilled and every new row is created through the API, which
   requires `collection_id`.

Revision ID: f10921de78c0
Revises: 565a86f1744e
Create Date: 2026-09-25 13:40:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f10921de78c0'
down_revision: Union[str, None] = '565a86f1744e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'api_collections',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sequence', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence'),
    )
    op.create_table(
        'api_folders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('collection_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sequence', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.ForeignKeyConstraint(['collection_id'], ['api_collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence'),
    )

    # Added nullable first - tightened to NOT NULL below, once every
    # pre-existing row has been backfilled (step 3/4 in the module
    # docstring).
    op.add_column('saved_api_requests', sa.Column('collection_id', sa.UUID(), nullable=True))
    op.add_column('saved_api_requests', sa.Column('folder_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'saved_api_requests_collection_id_fkey',
        'saved_api_requests', 'api_collections',
        ['collection_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'saved_api_requests_folder_id_fkey',
        'saved_api_requests', 'api_folders',
        ['folder_id'], ['id'], ondelete='SET NULL',
    )

    # --- Data backfill (see module docstring) ---
    bind = op.get_bind()
    projects_needing_backfill = bind.execute(
        sa.text(
            "SELECT DISTINCT ON (project_id) project_id, created_by "
            "FROM saved_api_requests "
            "WHERE collection_id IS NULL "
            "ORDER BY project_id, sequence ASC"
        )
    ).fetchall()

    for project_id, created_by in projects_needing_backfill:
        collection_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO api_collections (id, project_id, name, created_by) "
                "VALUES (:id, :project_id, :name, :created_by)"
            ),
            {
                "id": collection_id,
                "project_id": project_id,
                "name": "My Requests",
                "created_by": created_by,
            },
        )
        bind.execute(
            sa.text(
                "UPDATE saved_api_requests SET collection_id = :collection_id "
                "WHERE project_id = :project_id AND collection_id IS NULL"
            ),
            {"collection_id": collection_id, "project_id": project_id},
        )

    op.alter_column('saved_api_requests', 'collection_id', nullable=False)


def downgrade() -> None:
    op.drop_constraint('saved_api_requests_folder_id_fkey', 'saved_api_requests', type_='foreignkey')
    op.drop_constraint('saved_api_requests_collection_id_fkey', 'saved_api_requests', type_='foreignkey')
    op.drop_column('saved_api_requests', 'folder_id')
    op.drop_column('saved_api_requests', 'collection_id')
    op.drop_table('api_folders')
    op.drop_table('api_collections')
    # No new Postgres ENUM types are introduced by this migration (both new
    # tables' columns are plain UUID/String/DateTime/BigInteger - no
    # sa.Enum(...) columns), so unlike 565a86f1744e's own downgrade() there
    # is nothing here to `sa.Enum(...).drop()` - confirmed by inspecting
    # every column above, not assumed.
