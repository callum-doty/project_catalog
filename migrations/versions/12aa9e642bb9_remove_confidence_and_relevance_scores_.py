"""Remove confidence and relevance scores and redundant text fields

Revision ID: 12aa9e642bb9
Revises: e77dd18eb872
Create Date: 2025-06-25 20:00:22.443469

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '12aa9e642bb9'
down_revision = 'e77dd18eb872'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('classifications', schema=None) as batch_op:
        batch_op.drop_column('confidence')

    with op.batch_alter_table('design_elements', schema=None) as batch_op:
        batch_op.drop_column('confidence')

    with op.batch_alter_table('extracted_text', schema=None) as batch_op:
        batch_op.drop_column('candidate_name')
        batch_op.drop_column('opponent_name')
        batch_op.drop_column('confidence')

    with op.batch_alter_table('llm_keywords', schema=None) as batch_op:
        batch_op.drop_column('relevance_score')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('llm_keywords', schema=None) as batch_op:
        batch_op.add_column(sa.Column('relevance_score', sa.BIGINT(), autoincrement=False, nullable=True))

    with op.batch_alter_table('extracted_text', schema=None) as batch_op:
        batch_op.add_column(sa.Column('confidence', sa.BIGINT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('opponent_name', sa.TEXT(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('candidate_name', sa.TEXT(), autoincrement=False, nullable=True))

    with op.batch_alter_table('design_elements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('confidence', sa.BIGINT(), autoincrement=False, nullable=True))

    with op.batch_alter_table('classifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('confidence', sa.BIGINT(), autoincrement=False, nullable=True))

    # ### end Alembic commands ###
