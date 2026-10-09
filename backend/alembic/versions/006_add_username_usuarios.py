"""006_add_username_usuarios

Revision ID: 006_add_username_usuarios
Revises: 005_fase6_seguridad_administracion
Create Date: 2026-10-01 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_username_usuarios'
down_revision: Union[str, None] = '005_fase6_seguridad_administracion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'usuarios',
        sa.Column('username', sa.String(length=50), nullable=False)
    )
    op.create_index(op.f('ix_usuarios_username'), 'usuarios', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_usuarios_username'), table_name='usuarios')
    op.drop_column('usuarios', 'username')
