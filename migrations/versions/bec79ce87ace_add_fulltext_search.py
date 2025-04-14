"""Add full text search capability

Revision ID: add_fulltext_search
Revises: add_critical_indexes  # Make sure this points to your previous migration
Create Date: 2025-04-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

# revision identifiers
revision = 'add_fulltext_search'  # This should already be filled in
down_revision = 'add_critical_indexes'  # Make sure this is correct
branch_labels = None
depends_on = None

def upgrade():
    # Add tsvector columns to store pre-processed search data
    op.add_column('documents', 
                  sa.Column('search_vector', TSVECTOR))
                  
    op.add_column('llm_analysis', 
                  sa.Column('search_vector', TSVECTOR))
    
    op.add_column('extracted_text', 
                  sa.Column('search_vector', TSVECTOR))
                  
    # Create GIN indexes for fast full-text search
    # GIN (Generalized Inverted Index) is optimized for full-text search
    op.create_index('ix_documents_search_vector', 'documents', 
                    ['search_vector'], postgresql_using='gin')
                    
    op.create_index('ix_llm_analysis_search_vector', 'llm_analysis', 
                    ['search_vector'], postgresql_using='gin')
                    
    op.create_index('ix_extracted_text_search_vector', 'extracted_text', 
                    ['search_vector'], postgresql_using='gin')
    
    # Add triggers to automatically update search vectors when records change
    # This uses PostgreSQL's to_tsvector function to convert text to the tsvector format
    op.execute('''
    CREATE OR REPLACE FUNCTION documents_search_vector_update() RETURNS trigger AS $$
    BEGIN
        NEW.search_vector = to_tsvector('english', COALESCE(NEW.filename, ''));
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;
    
    CREATE TRIGGER documents_search_vector_update
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION documents_search_vector_update();
    ''')
    
    op.execute('''
    CREATE OR REPLACE FUNCTION llm_analysis_search_vector_update() RETURNS trigger AS $$
    BEGIN
        NEW.search_vector = to_tsvector('english', 
            COALESCE(NEW.summary_description, '') || ' ' || 
            COALESCE(NEW.campaign_type, '') || ' ' || 
            COALESCE(NEW.election_year, '') || ' ' || 
            COALESCE(NEW.document_tone, ''));
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;
    
    CREATE TRIGGER llm_analysis_search_vector_update
    BEFORE INSERT OR UPDATE ON llm_analysis
    FOR EACH ROW EXECUTE FUNCTION llm_analysis_search_vector_update();
    ''')
    
    op.execute('''
    CREATE OR REPLACE FUNCTION extracted_text_search_vector_update() RETURNS trigger AS $$
    BEGIN
        NEW.search_vector = to_tsvector('english', 
            COALESCE(NEW.text_content, '') || ' ' || 
            COALESCE(NEW.main_message, '') || ' ' || 
            COALESCE(NEW.supporting_text, '') || ' ' || 
            COALESCE(NEW.call_to_action, ''));
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;
    
    CREATE TRIGGER extracted_text_search_vector_update
    BEFORE INSERT OR UPDATE ON extracted_text
    FOR EACH ROW EXECUTE FUNCTION extracted_text_search_vector_update();
    ''')
    
    # Populate existing records with search vectors
    # This updates all existing records to have search vectors
    op.execute("UPDATE documents SET search_vector = to_tsvector('english', COALESCE(filename, ''))")
    op.execute("UPDATE llm_analysis SET search_vector = to_tsvector('english', COALESCE(summary_description, '') || ' ' || COALESCE(campaign_type, '') || ' ' || COALESCE(election_year, '') || ' ' || COALESCE(document_tone, ''))")
    op.execute("UPDATE extracted_text SET search_vector = to_tsvector('english', COALESCE(text_content, '') || ' ' || COALESCE(main_message, '') || ' ' || COALESCE(supporting_text, '') || ' ' || COALESCE(call_to_action, ''))")

def downgrade():
    # Remove triggers
    op.execute("DROP TRIGGER IF EXISTS documents_search_vector_update ON documents")
    op.execute("DROP FUNCTION IF EXISTS documents_search_vector_update()")
    
    op.execute("DROP TRIGGER IF EXISTS llm_analysis_search_vector_update ON llm_analysis")
    op.execute("DROP FUNCTION IF EXISTS llm_analysis_search_vector_update()")
    
    op.execute("DROP TRIGGER IF EXISTS extracted_text_search_vector_update ON extracted_text")
    op.execute("DROP FUNCTION IF EXISTS extracted_text_search_vector_update()")
    
    # Drop indexes
    op.drop_index('ix_documents_search_vector', table_name='documents')
    op.drop_index('ix_llm_analysis_search_vector', table_name='llm_analysis')
    op.drop_index('ix_extracted_text_search_vector', table_name='extracted_text')
    
    # Drop columns
    op.drop_column('documents', 'search_vector')
    op.drop_column('llm_analysis', 'search_vector')
    op.drop_column('extracted_text', 'search_vector')