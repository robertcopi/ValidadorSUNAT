"""003_create_procesos_masivos

Revision ID: 003_procesos_masivos
Revises: 002_consultas_cpe
Create Date: 2026-09-29 08:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_procesos_masivos'
down_revision: Union[str, None] = '002_consultas_cpe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabla procesos_masivos
    op.create_table(
        'procesos_masivos',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('nombre_archivo', sa.String(length=255), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('estado', sa.String(length=30), nullable=False, server_default='PENDIENTE'),
        sa.Column('total_registros', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_procesados', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_validos', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_no_validos', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_observados', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_errores', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('porcentaje', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
        sa.Column('mensaje_error', sa.String(length=500), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_procesos_masivos_id'), 'procesos_masivos', ['id'], unique=False)
    op.create_index(op.f('ix_procesos_masivos_empresa_id'), 'procesos_masivos', ['empresa_id'], unique=False)
    op.create_index(op.f('ix_procesos_masivos_usuario_id'), 'procesos_masivos', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_procesos_masivos_estado'), 'procesos_masivos', ['estado'], unique=False)
    op.create_index(op.f('ix_procesos_masivos_idempotency_key'), 'procesos_masivos', ['idempotency_key'], unique=False)
    op.create_index('idx_procesos_masivos_empresa_created', 'procesos_masivos', ['empresa_id', 'created_at'], unique=False)
    op.create_index('idx_procesos_masivos_idempotency', 'procesos_masivos', ['empresa_id', 'idempotency_key'], unique=False)
    op.create_index('idx_procesos_masivos_estado', 'procesos_masivos', ['estado'], unique=False)

    # 2. Tabla proceso_masivo_items
    op.create_table(
        'proceso_masivo_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('proceso_id', sa.String(length=36), nullable=False),
        sa.Column('fila_excel', sa.Integer(), nullable=True),
        sa.Column('num_ruc', sa.String(length=11), nullable=False),
        sa.Column('cod_comp', sa.String(length=2), nullable=False),
        sa.Column('numero_serie', sa.String(length=10), nullable=False),
        sa.Column('numero', sa.String(length=20), nullable=False),
        sa.Column('fecha_emision', sa.Date(), nullable=False),
        sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('razon_social', sa.String(length=255), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False, server_default='PENDIENTE'),
        sa.Column('estado_sunat', sa.String(length=50), nullable=True),
        sa.Column('codigo_sunat', sa.String(length=20), nullable=True),
        sa.Column('mensaje_sunat', sa.String(length=500), nullable=True),
        sa.Column('intentos', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consulta_cpe_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['proceso_id'], ['procesos_masivos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['consulta_cpe_id'], ['consultas_cpe.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proceso_masivo_items_id'), 'proceso_masivo_items', ['id'], unique=False)
    op.create_index(op.f('ix_proceso_masivo_items_proceso_id'), 'proceso_masivo_items', ['proceso_id'], unique=False)
    op.create_index(op.f('ix_proceso_masivo_items_num_ruc'), 'proceso_masivo_items', ['num_ruc'], unique=False)
    op.create_index(op.f('ix_proceso_masivo_items_estado'), 'proceso_masivo_items', ['estado'], unique=False)
    op.create_index('idx_proceso_items_proceso_estado', 'proceso_masivo_items', ['proceso_id', 'estado'], unique=False)
    op.create_index('idx_proceso_items_ruc_comp', 'proceso_masivo_items', ['num_ruc', 'cod_comp', 'numero_serie', 'numero'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_proceso_items_ruc_comp', table_name='proceso_masivo_items')
    op.drop_index('idx_proceso_items_proceso_estado', table_name='proceso_masivo_items')
    op.drop_index(op.f('ix_proceso_masivo_items_estado'), table_name='proceso_masivo_items')
    op.drop_index(op.f('ix_proceso_masivo_items_num_ruc'), table_name='proceso_masivo_items')
    op.drop_index(op.f('ix_proceso_masivo_items_proceso_id'), table_name='proceso_masivo_items')
    op.drop_index(op.f('ix_proceso_masivo_items_id'), table_name='proceso_masivo_items')
    op.drop_table('proceso_masivo_items')

    op.drop_index('idx_procesos_masivos_estado', table_name='procesos_masivos')
    op.drop_index('idx_procesos_masivos_idempotency', table_name='procesos_masivos')
    op.drop_index('idx_procesos_masivos_empresa_created', table_name='procesos_masivos')
    op.drop_index(op.f('ix_procesos_masivos_idempotency_key'), table_name='procesos_masivos')
    op.drop_index(op.f('ix_procesos_masivos_estado'), table_name='procesos_masivos')
    op.drop_index(op.f('ix_procesos_masivos_usuario_id'), table_name='procesos_masivos')
    op.drop_index(op.f('ix_procesos_masivos_empresa_id'), table_name='procesos_masivos')
    op.drop_index(op.f('ix_procesos_masivos_id'), table_name='procesos_masivos')
    op.drop_table('procesos_masivos')
