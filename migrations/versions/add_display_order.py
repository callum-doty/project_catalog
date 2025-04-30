"""add display_order to document_keywords

Revision ID: add_display_order
Revises: fix_search_vector_columns
Create Date: 2025-04-30 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_display_order'
down_revision = 'fix_search_vector_columns'
branch_labels = None
depends_on = None


def upgrade():
    # Add display_order column with default value of 0
    with op.batch_alter_table('document_keywords', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_order', sa.Integer(),
                                      nullable=False, server_default='0'))

    # Create an index for faster ordering by display_order
    op.create_index(op.f('ix_document_keywords_display_order'),
                    'document_keywords', ['display_order'], unique=False)


def downgrade():
    # Remove the index
    op.drop_index(op.f('ix_document_keywords_display_order'),
                  table_name='document_keywords')

    # Remove the display_order column
    with op.batch_alter_table('document_keywords', schema=None) as batch_op:
        batch_op.drop_column('display_order')
