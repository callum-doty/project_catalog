"""Add keyword and category fields to LLMKeyword table

Revision ID: add_keyword_category_fields
Revises: e77dd18eb872
Create Date: 2025-01-07 12:21:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_keyword_category_fields"
down_revision = "e77dd18eb872"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to llm_keywords table
    op.add_column("llm_keywords", sa.Column("keyword", sa.Text(), nullable=True))
    op.add_column("llm_keywords", sa.Column("category", sa.Text(), nullable=True))

    # Make taxonomy_id nullable
    op.alter_column("llm_keywords", "taxonomy_id", nullable=True)

    # Make verbatim_term nullable for backward compatibility
    op.alter_column("llm_keywords", "verbatim_term", nullable=True)

    # Copy verbatim_term to keyword for existing records
    op.execute("UPDATE llm_keywords SET keyword = verbatim_term WHERE keyword IS NULL")

    # Now make keyword not nullable
    op.alter_column("llm_keywords", "keyword", nullable=False)


def downgrade():
    # Remove the new columns
    op.drop_column("llm_keywords", "category")
    op.drop_column("llm_keywords", "keyword")

    # Restore original constraints
    op.alter_column("llm_keywords", "taxonomy_id", nullable=False)
    op.alter_column("llm_keywords", "verbatim_term", nullable=False)
