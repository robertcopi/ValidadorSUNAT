"""006_add_username_usuarios

Revision ID: 006_add_username_usuarios
Revises: 005_fase6_seguridad_administracion
Create Date: 2026-09-30 09:00:00.000000

"""
import re
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_username_usuarios'
down_revision: Union[str, None] = '005_fase6_seguridad_administracion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agregar columna username como nullable inicialmente para poblar datos existentes de forma segura
    op.add_column(
        'usuarios',
        sa.Column('username', sa.String(length=50), nullable=True)
    )

    # 2. Migración de datos: Asignar usernames iniciales únicos a los usuarios existentes
    bind = op.get_bind()
    usuarios_table = sa.table(
        'usuarios',
        sa.column('id', sa.Integer),
        sa.column('email', sa.String),
        sa.column('username', sa.String)
    )

    rows = bind.execute(sa.select(usuarios_table.c.id, usuarios_table.c.email, usuarios_table.c.username)).fetchall()
    used_usernames = set()

    for row in rows:
        user_id = row[0]
        email = row[1] or f"user_{user_id}@sistema.local"
        existing_uname = row[2]

        if not existing_uname:
            # Extraer prefijo del email, normalizar a minúsculas y caracteres válidos
            base = email.split('@')[0].strip().lower()
            clean = re.sub(r'[^a-z0-9._-]', '', base)
            if len(clean) < 3:
                clean = f"user_{user_id}"
            clean = clean[:50]

            candidate = clean
            idx = 1
            while candidate in used_usernames:
                suffix = f"_{idx}"
                candidate = f"{clean[:50 - len(suffix)]}{suffix}"
                idx += 1

            used_usernames.add(candidate)
            bind.execute(
                usuarios_table.update().where(usuarios_table.c.id == user_id).values(username=candidate)
            )
        else:
            used_usernames.add(existing_uname.strip().lower())

    # 3. Una vez garantizado que no existen registros nulos, establecer NOT NULL
    op.alter_column('usuarios', 'username', nullable=False, existing_type=sa.String(length=50))

    # 4. Crear índice único
    op.create_index(op.f('ix_usuarios_username'), 'usuarios', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_usuarios_username'), table_name='usuarios')
    op.drop_column('usuarios', 'username')
