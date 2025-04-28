# migrations/versions/add_document_scorecard.py
"""Add document scorecard model

Revision ID: add_document_scorecard
Revises: bec79ce87ace
Create Date: 2025-04-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_document_scorecard'
down_revision = 'bec79ce87ace'
branch_labels = None
depends_on = None


def upgrade():
    # Create document_scorecards table
    op.create_table('document_scorecards',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('document_id', sa.Integer(), nullable=False),
                    sa.Column('text_extraction_score',
                              sa.Integer(), nullable=True),
                    sa.Column('classification_score',
                              sa.Integer(), nullable=True),
                    sa.Column('keyword_relevance_score',
                              sa.Integer(), nullable=True),
                    sa.Column('visual_analysis_score',
                              sa.Integer(), nullable=True),
                    sa.Column('entity_recognition_score',
                              sa.Integer(), nullable=True),
                    sa.Column('overall_quality_score',
                              sa.Integer(), nullable=True),
                    sa.Column('created_date', sa.DateTime(
                        timezone=True), nullable=True),
                    sa.Column('last_updated', sa.DateTime(
                        timezone=True), nullable=True),
                    sa.Column('notes', sa.Text(), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['document_id'], ['documents.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    # Add index for faster lookups by document_id
    op.create_index(op.f('ix_document_scorecards_document_id'),
                    'document_scorecards', ['document_id'], unique=True)


def downgrade():
    # Drop the table when downgrading
    op.drop_index(op.f('ix_document_scorecards_document_id'),
                  table_name='document_scorecards')
    op.drop_table('document_scorecards')
