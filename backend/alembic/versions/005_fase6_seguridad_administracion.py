"""005_fase6_seguridad_administracion

Revision ID: 005_fase6_seguridad_administracion
Revises: 004_add_monto_original_proceso_items
Create Date: 2026-09-29 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_fase6_seguridad_administracion'
down_revision: Union[str, None] = '004_add_monto_original_proceso_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agregar columna must_change_password a la tabla usuarios
    op.add_column(
        'usuarios',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )

    # 2. Crear tabla auditoria_eventos
    op.create_table(
        'auditoria_eventos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('accion', sa.String(length=50), nullable=False),
        sa.Column('entidad', sa.String(length=50), nullable=False),
        sa.Column('entidad_id', sa.String(length=50), nullable=True),
        sa.Column('detalle', sa.JSON(), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auditoria_eventos_id'), 'auditoria_eventos', ['id'], unique=False)
    op.create_index(op.f('ix_auditoria_eventos_usuario_id'), 'auditoria_eventos', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_auditoria_eventos_empresa_id'), 'auditoria_eventos', ['empresa_id'], unique=False)
    op.create_index(op.f('ix_auditoria_eventos_accion'), 'auditoria_eventos', ['accion'], unique=False)
    op.create_index(op.f('ix_auditoria_eventos_entidad'), 'auditoria_eventos', ['entidad'], unique=False)
    op.create_index(op.f('ix_auditoria_eventos_created_at'), 'auditoria_eventos', ['created_at'], unique=False)
    op.create_index('idx_auditoria_empresa_accion', 'auditoria_eventos', ['empresa_id', 'accion'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_auditoria_empresa_accion', table_name='auditoria_eventos')
    op.drop_index(op.f('ix_auditoria_eventos_created_at'), table_name='auditoria_eventos')
    op.drop_index(op.f('ix_auditoria_eventos_entidad'), table_name='auditoria_eventos')
    op.drop_index(op.f('ix_auditoria_eventos_accion'), table_name='auditoria_eventos')
    op.drop_index(op.f('ix_auditoria_eventos_empresa_id'), table_name='auditoria_eventos')
    op.drop_index(op.f('ix_auditoria_eventos_usuario_id'), table_name='auditoria_eventos')
    op.drop_index(op.f('ix_auditoria_eventos_id'), table_name='auditoria_eventos')
    op.drop_table('auditoria_eventos')
    op.drop_column('usuarios', 'must_change_password')
