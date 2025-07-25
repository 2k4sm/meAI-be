"""adds user_toolkit_connection 

Revision ID: cf2754c8bfd0
Revises: d6f527abe7c9
Create Date: 2025-07-20 12:19:03.301520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cf2754c8bfd0'
down_revision: Union[str, Sequence[str], None] = 'd6f527abe7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_toolkit_connections',
    sa.Column('connection_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('toolkit_slug', sa.String(length=100), nullable=False),
    sa.Column('connection_status', sa.String(length=20), nullable=False),
    sa.Column('connected_account_id', sa.String(length=255), nullable=True),
    sa.Column('auth_config_id', sa.String(length=255), nullable=True),
    sa.Column('connection_request_id', sa.String(length=255), nullable=True),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('connection_id')
    )
    op.create_index(op.f('ix_user_toolkit_connections_connection_id'), 'user_toolkit_connections', ['connection_id'], unique=False)
    op.create_index(op.f('ix_user_toolkit_connections_toolkit_slug'), 'user_toolkit_connections', ['toolkit_slug'], unique=False)
    op.drop_index(op.f('ix_user_tool_preferences_preference_id'), table_name='user_tool_preferences')
    op.drop_table('user_tool_preferences')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_tool_preferences',
    sa.Column('preference_id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('toolkit_slug', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('is_enabled', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('user_tool_preferences_user_id_fkey')),
    sa.PrimaryKeyConstraint('preference_id', name=op.f('user_tool_preferences_pkey'))
    )
    op.create_index(op.f('ix_user_tool_preferences_preference_id'), 'user_tool_preferences', ['preference_id'], unique=False)
    op.drop_index(op.f('ix_user_toolkit_connections_toolkit_slug'), table_name='user_toolkit_connections')
    op.drop_index(op.f('ix_user_toolkit_connections_connection_id'), table_name='user_toolkit_connections')
    op.drop_table('user_toolkit_connections')
    # ### end Alembic commands ###
