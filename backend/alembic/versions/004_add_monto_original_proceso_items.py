"""004_add_monto_original_proceso_items

Revision ID: 004_add_monto_original_proceso_items
Revises: 003_procesos_masivos
Create Date: 2026-09-29 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_monto_original_proceso_items'
down_revision: Union[str, None] = '003_procesos_masivos'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ampliar tamaño de version_num en alembic_version para permitir identificadores descriptivos
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    # 2. Agregar columna monto_original para preservar signo contable original (ej. notas de crédito)
    op.add_column(
        'proceso_masivo_items',
        sa.Column('monto_original', sa.Numeric(precision=12, scale=2), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('proceso_masivo_items', 'monto_original')
