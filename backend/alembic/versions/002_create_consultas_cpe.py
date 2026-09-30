"""002_create_consultas_cpe

Revision ID: 002_consultas_cpe
Revises: 001_initial
Create Date: 2026-09-28 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_consultas_cpe'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'consultas_cpe',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('ruc_emisor', sa.String(length=11), nullable=False),
        sa.Column('tipo_comprobante', sa.String(length=2), nullable=False),
        sa.Column('serie', sa.String(length=10), nullable=False),
        sa.Column('numero', sa.String(length=20), nullable=False),
        sa.Column('fecha_emision', sa.Date(), nullable=False),
        sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=False),
        sa.Column('codigo_sunat', sa.String(length=20), nullable=True),
        sa.Column('mensaje_sunat', sa.String(length=500), nullable=True),
        sa.Column('respuesta_sunat', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consultas_cpe_id'), 'consultas_cpe', ['id'], unique=False)
    op.create_index(op.f('ix_consultas_cpe_empresa_id'), 'consultas_cpe', ['empresa_id'], unique=False)
    op.create_index(op.f('ix_consultas_cpe_usuario_id'), 'consultas_cpe', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_consultas_cpe_ruc_emisor'), 'consultas_cpe', ['ruc_emisor'], unique=False)
    op.create_index(op.f('ix_consultas_cpe_fecha_emision'), 'consultas_cpe', ['fecha_emision'], unique=False)
    op.create_index(op.f('ix_consultas_cpe_estado'), 'consultas_cpe', ['estado'], unique=False)
    op.create_index('idx_consultas_cpe_empresa_created', 'consultas_cpe', ['empresa_id', 'created_at'], unique=False)
    op.create_index('idx_consultas_cpe_empresa_emisor', 'consultas_cpe', ['empresa_id', 'ruc_emisor'], unique=False)
    op.create_index('idx_consultas_cpe_emisor_fecha', 'consultas_cpe', ['ruc_emisor', 'fecha_emision'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_consultas_cpe_emisor_fecha', table_name='consultas_cpe')
    op.drop_index('idx_consultas_cpe_empresa_emisor', table_name='consultas_cpe')
    op.drop_index('idx_consultas_cpe_empresa_created', table_name='consultas_cpe')
    op.drop_index(op.f('ix_consultas_cpe_estado'), table_name='consultas_cpe')
    op.drop_index(op.f('ix_consultas_cpe_fecha_emision'), table_name='consultas_cpe')
    op.drop_index(op.f('ix_consultas_cpe_ruc_emisor'), table_name='consultas_cpe')
    op.drop_index(op.f('ix_consultas_cpe_usuario_id'), table_name='consultas_cpe')
    op.drop_index(op.f('ix_consultas_cpe_empresa_id'), table_name='consultas_cpe')
    op.drop_index(op.f('ix_consultas_cpe_id'), table_name='consultas_cpe')
    op.drop_table('consultas_cpe')
