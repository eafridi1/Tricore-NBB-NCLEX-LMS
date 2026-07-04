"""make questions category_id nullable

Revision ID: 7c29cf2e2bcc
Revises: fef87edf1c95
Create Date: 2026-07-02 15:25:13.321885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c29cf2e2bcc'
down_revision: Union[str, Sequence[str], None] = 'fef87edf1c95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('questions', 'category_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('questions', 'category_id', existing_type=sa.Integer(), nullable=False)
