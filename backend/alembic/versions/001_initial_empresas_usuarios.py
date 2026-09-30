"""001_initial_empresas_usuarios

Revision ID: 001_initial
Revises: 
Create Date: 2026-09-28 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear tabla empresas
    op.create_table(
        'empresas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ruc', sa.String(length=11), nullable=False),
        sa.Column('razon_social', sa.String(length=255), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_empresas_id'), 'empresas', ['id'], unique=False)
    op.create_index(op.f('ix_empresas_ruc'), 'empresas', ['ruc'], unique=True)

    # 2. Crear tabla usuarios
    op.create_table(
        'usuarios',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('nombre_completo', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('rol', sa.String(length=20), nullable=False, server_default='CONTADOR'),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usuarios_id'), 'usuarios', ['id'], unique=False)
    op.create_index(op.f('ix_usuarios_email'), 'usuarios', ['email'], unique=True)
    op.create_index(op.f('ix_usuarios_empresa_id'), 'usuarios', ['empresa_id'], unique=False)
    op.create_index(op.f('ix_usuarios_rol'), 'usuarios', ['rol'], unique=False)
    op.create_index('idx_usuarios_empresa_rol', 'usuarios', ['empresa_id', 'rol'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_usuarios_empresa_rol', table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_rol'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_empresa_id'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_email'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_id'), table_name='usuarios')
    op.drop_table('usuarios')
    op.drop_index(op.f('ix_empresas_ruc'), table_name='empresas')
    op.drop_index(op.f('ix_empresas_id'), table_name='empresas')
    op.drop_table('empresas')
