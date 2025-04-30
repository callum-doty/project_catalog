# migrations/versions/fix_search_vector_columns.py
"""fix search vector columns

Revision ID: fix_search_vector_columns
Revises: 08fbf7066db8
Create Date: 2025-04-30 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fix_search_vector_columns'
down_revision = '08fbf7066db8'
branch_labels = None
depends_on = None


def upgrade():
    # Add search_vector columns to tables that need them
    with op.batch_alter_table('llm_analysis', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True))

    with op.batch_alter_table('extracted_text', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True))

    # Create indexes for the search vectors
    op.create_index(op.f('ix_llm_analysis_search_vector'), 'llm_analysis', [
                    'search_vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_extracted_text_search_vector'), 'extracted_text', [
                    'search_vector'], unique=False, postgresql_using='gin')


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_llm_analysis_search_vector'),
                  table_name='llm_analysis')
    op.drop_index(op.f('ix_extracted_text_search_vector'),
                  table_name='extracted_text')

    # Remove columns
    with op.batch_alter_table('llm_analysis', schema=None) as batch_op:
        batch_op.drop_column('search_vector')

    with op.batch_alter_table('extracted_text', schema=None) as batch_op:
        batch_op.drop_column('search_vector')
