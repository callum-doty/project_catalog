"""Merge multiple heads

Revision ID: 9776dbefad1c
Revises: add_keyword_category_fields, 8b298fa7a6ba
Create Date: 2025-07-01 12:41:32.274880

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9776dbefad1c"
down_revision = ("add_keyword_category_fields", "8b298fa7a6ba")
branch_labels = None
depends_on = None


def upgrade():
    # This merge migration resolves conflicts between two branches:
    # 1. add_keyword_category_fields: adds keyword, category columns
    # 2. 8b298fa7a6ba chain: removes keyword, category and adds verbatim_term

    # Since both branches modify llm_keywords table, we need to ensure
    # the final state has all required columns

    # Check if verbatim_term column exists (from 16067fd1223d)
    # If not, we need to add it since the 8b298fa7a6ba branch expects it
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("llm_keywords")]

    if "verbatim_term" not in columns:
        # Add verbatim_term column if it doesn't exist
        op.add_column(
            "llm_keywords", sa.Column("verbatim_term", sa.Text(), nullable=True)
        )

        # Copy keyword to verbatim_term if keyword exists
        if "keyword" in columns:
            op.execute(
                "UPDATE llm_keywords SET verbatim_term = keyword WHERE verbatim_term IS NULL"
            )

    # Ensure relevance_score is Float type (from 16067fd1223d)
    if "relevance_score" in columns:
        # Check current type and alter if needed
        try:
            op.alter_column(
                "llm_keywords",
                "relevance_score",
                existing_type=sa.BigInteger(),
                type_=sa.Float(),
                existing_nullable=True,
            )
        except:
            # Column might already be Float type
            pass
    else:
        # Add relevance_score as Float if it doesn't exist
        op.add_column(
            "llm_keywords", sa.Column("relevance_score", sa.Float(), nullable=True)
        )

    # Add created_date if it doesn't exist (from 16067fd1223d)
    if "created_date" not in columns:
        op.add_column(
            "llm_keywords",
            sa.Column("created_date", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade():
    # Reverse the merge by removing columns that were added
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("llm_keywords")]

    if "created_date" in columns:
        op.drop_column("llm_keywords", "created_date")

    if "verbatim_term" in columns:
        op.drop_column("llm_keywords", "verbatim_term")

    # Revert relevance_score to BigInteger if it exists
    if "relevance_score" in columns:
        try:
            op.alter_column(
                "llm_keywords",
                "relevance_score",
                existing_type=sa.Float(),
                type_=sa.BigInteger(),
                existing_nullable=True,
            )
        except:
            pass
