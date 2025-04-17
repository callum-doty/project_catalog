# migrations/versions/add_vector_embeddings.py
"""Add vector embeddings for semantic search

Revision ID: add_vector_embeddings
Revises: add_fulltext_search  # Make sure this points to your previous migration
Create Date: 2025-04-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import VECTOR

# revision identifiers
revision = 'add_vector_embeddings'
down_revision = 'add_fulltext_search'  # Update to your last migration
branch_labels = None
depends_on = None

def upgrade():
    # Add vector embeddings columns for documents and analysis
    op.add_column('documents', 
                  sa.Column('embeddings', VECTOR(1536)))  # OpenAI embeddings are 1536 dimensions
                  
    op.add_column('llm_analysis', 
                  sa.Column('embeddings', VECTOR(1536)))
    
    # Create index for fast vector similarity search
    op.execute(
        'CREATE INDEX documents_embeddings_idx ON documents USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100)'
    )
    
    op.execute(
        'CREATE INDEX llm_analysis_embeddings_idx ON llm_analysis USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100)'
    )

def downgrade():
    # Drop indexes
    op.execute('DROP INDEX IF EXISTS documents_embeddings_idx')
    op.execute('DROP INDEX IF EXISTS llm_analysis_embeddings_idx')
    
    # Drop columns
    op.drop_column('documents', 'embeddings')
    op.drop_column('llm_analysis', 'embeddings')