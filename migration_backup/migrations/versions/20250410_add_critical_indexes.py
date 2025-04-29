# Create a new migration file with the needed indexes
"""Add critical database indexes

Revision ID: add_critical_indexes
Revises: 326a84e6b998
Create Date: 2025-04-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_critical_indexes'
down_revision = '326a84e6b998'
branch_labels = None
depends_on = None

def upgrade():
    # Document table indexes
    op.create_index('ix_documents_filename', 'documents', ['filename'], unique=False)
    op.create_index('ix_documents_status', 'documents', ['status'], unique=False)
    op.create_index('ix_documents_upload_date', 'documents', ['upload_date'], unique=False)
    
    # LLM Analysis indexes
    op.create_index('ix_llm_analysis_summary', 'llm_analysis', ['summary_description'], unique=False)
    op.create_index('ix_llm_analysis_document_id', 'llm_analysis', ['document_id'], unique=False)
    op.create_index('ix_llm_analysis_campaign_type', 'llm_analysis', ['campaign_type'], unique=False)
    op.create_index('ix_llm_analysis_election_year', 'llm_analysis', ['election_year'], unique=False)
    op.create_index('ix_llm_analysis_document_tone', 'llm_analysis', ['document_tone'], unique=False)
    
    # Keyword indexes
    op.create_index('ix_llm_keywords_keyword', 'llm_keywords', ['keyword'], unique=False)
    op.create_index('ix_llm_keywords_analysis_id', 'llm_keywords', ['llm_analysis_id'], unique=False)
    
    # Classification indexes
    op.create_index('ix_classifications_document_id', 'classifications', ['document_id'], unique=False)
    op.create_index('ix_classifications_category', 'classifications', ['category'], unique=False)
    
    # Design Elements indexes
    op.create_index('ix_design_elements_document_id', 'design_elements', ['document_id'], unique=False)
    op.create_index('ix_design_elements_geographic_location', 'design_elements', ['geographic_location'], unique=False)
    
    # Extracted Text indexes
    op.create_index('ix_extracted_text_document_id', 'extracted_text', ['document_id'], unique=False)
    op.create_index('ix_extracted_text_main_message', 'extracted_text', ['main_message'], unique=False)
    op.create_index('ix_extracted_text_supporting_text', 'extracted_text', ['supporting_text'], unique=False)
    
    # Entity indexes
    op.create_index('ix_entities_document_id', 'entities', ['document_id'], unique=False)
    op.create_index('ix_entities_client_name', 'entities', ['client_name'], unique=False)
    op.create_index('ix_entities_opponent_name', 'entities', ['opponent_name'], unique=False)
    
    # Communication Focus indexes
    op.create_index('ix_communication_focus_document_id', 'communication_focus', ['document_id'], unique=False)
    op.create_index('ix_communication_focus_primary_issue', 'communication_focus', ['primary_issue'], unique=False)
    
    # Taxonomy and Hierarchical Keyword indexes
    op.create_index('ix_keyword_taxonomy_term', 'keyword_taxonomy', ['term'], unique=False)
    op.create_index('ix_keyword_taxonomy_primary_category', 'keyword_taxonomy', ['primary_category'], unique=False)
    op.create_index('ix_keyword_taxonomy_subcategory', 'keyword_taxonomy', ['subcategory'], unique=False)
    
    op.create_index('ix_keyword_synonyms_synonym', 'keyword_synonyms', ['synonym'], unique=False)
    op.create_index('ix_keyword_synonyms_taxonomy_id', 'keyword_synonyms', ['taxonomy_id'], unique=False)
    
    op.create_index('ix_document_keywords_document_id', 'document_keywords', ['document_id'], unique=False)
    op.create_index('ix_document_keywords_taxonomy_id', 'document_keywords', ['taxonomy_id'], unique=False)

def downgrade():
    # Document table indexes
    op.drop_index('ix_documents_filename', table_name='documents')
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_index('ix_documents_upload_date', table_name='documents')
    
    # LLM Analysis indexes
    op.drop_index('ix_llm_analysis_summary', table_name='llm_analysis')
    op.drop_index('ix_llm_analysis_document_id', table_name='llm_analysis')
    op.drop_index('ix_llm_analysis_campaign_type', table_name='llm_analysis')
    op.drop_index('ix_llm_analysis_election_year', table_name='llm_analysis')
    op.drop_index('ix_llm_analysis_document_tone', table_name='llm_analysis')
    
    # Keyword indexes
    op.drop_index('ix_llm_keywords_keyword', table_name='llm_keywords')
    op.drop_index('ix_llm_keywords_analysis_id', table_name='llm_keywords')
    
    # Classification indexes
    op.drop_index('ix_classifications_document_id', table_name='classifications')
    op.drop_index('ix_classifications_category', table_name='classifications')
    
    # Design Elements indexes
    op.drop_index('ix_design_elements_document_id', table_name='design_elements')
    op.drop_index('ix_design_elements_geographic_location', table_name='design_elements')
    
    # Extracted Text indexes
    op.drop_index('ix_extracted_text_document_id', table_name='extracted_text')
    op.drop_index('ix_extracted_text_main_message', table_name='extracted_text')
    op.drop_index('ix_extracted_text_supporting_text', table_name='extracted_text')
    
    # Entity indexes
    op.drop_index('ix_entities_document_id', table_name='entities')
    op.drop_index('ix_entities_client_name', table_name='entities')
    op.drop_index('ix_entities_opponent_name', table_name='entities')
    
    # Communication Focus indexes
    op.drop_index('ix_communication_focus_document_id', table_name='communication_focus')
    op.drop_index('ix_communication_focus_primary_issue', table_name='communication_focus')
    
    # Taxonomy and Hierarchical Keyword indexes
    op.drop_index('ix_keyword_taxonomy_term', table_name='keyword_taxonomy')
    op.drop_index('ix_keyword_taxonomy_primary_category', table_name='keyword_taxonomy')
    op.drop_index('ix_keyword_taxonomy_subcategory', table_name='keyword_taxonomy')
    
    op.drop_index('ix_keyword_synonyms_synonym', table_name='keyword_synonyms')
    op.drop_index('ix_keyword_synonyms_taxonomy_id', table_name='keyword_synonyms')
    
    op.drop_index('ix_document_keywords_document_id', table_name='document_keywords')
    op.drop_index('ix_document_keywords_taxonomy_id', table_name='document_keywords')