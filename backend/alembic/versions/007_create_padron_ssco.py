"""007_create_padron_ssco

Revision ID: 007_create_padron_ssco
Revises: 006_add_username_usuarios
Create Date: 2026-10-09 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_create_padron_ssco'
down_revision: Union[str, None] = '006_add_username_usuarios'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabla global padron_ssco
    op.create_table(
        'padron_ssco',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ruc', sa.String(length=11), nullable=False),
        sa.Column('razon_social', sa.String(length=255), nullable=False),
        sa.Column('domicilio_fiscal', sa.Text(), nullable=True),
        sa.Column('resolucion_atribucion', sa.String(length=255), nullable=False),
        sa.Column('fecha_emision_resolucion', sa.Date(), nullable=False),
        sa.Column('fecha_firmeza', sa.Date(), nullable=False),
        sa.Column('doc_representante', sa.String(length=20), nullable=True),
        sa.Column('nombre_representante', sa.String(length=255), nullable=True),
        sa.Column('fecha_publicacion', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ruc', name='uq_padron_ssco_ruc')
    )
    op.create_index(op.f('ix_padron_ssco_id'), 'padron_ssco', ['id'], unique=False)

    # 2. Tabla historial de sincronizaciones
    op.create_table(
        'padron_ssco_sincronizaciones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('origen', sa.String(length=20), nullable=False),
        sa.Column('total_registros', sa.Integer(), nullable=False),
        sa.Column('fecha_padron_sunat', sa.String(length=50), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False),
        sa.Column('mensaje', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_padron_ssco_sincronizaciones_id'), 'padron_ssco_sincronizaciones', ['id'], unique=False)

    # 3. Tabla trazabilidad de consultas de usuarios (Multiempresa)
    op.create_table(
        'consultas_ssco',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('ruc_consultado', sa.String(length=11), nullable=False),
        sa.Column('es_ssco', sa.Boolean(), nullable=False),
        sa.Column('detalle_ssco', sa.JSON(), nullable=True),
        sa.Column('fecha_padron_consultado', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consultas_ssco_id'), 'consultas_ssco', ['id'], unique=False)
    op.create_index(op.f('ix_consultas_ssco_empresa_id'), 'consultas_ssco', ['empresa_id'], unique=False)
    op.create_index(op.f('ix_consultas_ssco_usuario_id'), 'consultas_ssco', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_consultas_ssco_ruc_consultado'), 'consultas_ssco', ['ruc_consultado'], unique=False)
    op.create_index('idx_consultas_ssco_empresa_ruc', 'consultas_ssco', ['empresa_id', 'ruc_consultado'], unique=False)
    op.create_index('idx_consultas_ssco_empresa_created', 'consultas_ssco', ['empresa_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_consultas_ssco_empresa_created', table_name='consultas_ssco')
    op.drop_index('idx_consultas_ssco_empresa_ruc', table_name='consultas_ssco')
    op.drop_index(op.f('ix_consultas_ssco_ruc_consultado'), table_name='consultas_ssco')
    op.drop_index(op.f('ix_consultas_ssco_usuario_id'), table_name='consultas_ssco')
    op.drop_index(op.f('ix_consultas_ssco_empresa_id'), table_name='consultas_ssco')
    op.drop_index(op.f('ix_consultas_ssco_id'), table_name='consultas_ssco')
    op.drop_table('consultas_ssco')

    op.drop_index(op.f('ix_padron_ssco_sincronizaciones_id'), table_name='padron_ssco_sincronizaciones')
    op.drop_table('padron_ssco_sincronizaciones')

    op.drop_index(op.f('ix_padron_ssco_id'), table_name='padron_ssco')
    op.drop_table('padron_ssco')
