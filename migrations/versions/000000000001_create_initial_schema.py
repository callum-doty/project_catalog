"""Create initial database schema

Revision ID: 000000000001
Revises:
Create Date: 2025-05-22 17:24:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR  # For tsvector type
from pgvector.sqlalchemy import Vector  # For vector type

# revision identifiers
revision = "000000000001"
down_revision = None  # This is the first migration
branch_labels = None
depends_on = None


def upgrade():
    # Create pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Create batch_jobs table
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("job_name", sa.Text(), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("total_documents", sa.Integer(), nullable=False),
        sa.Column("processed_documents", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batch_jobs")),
    )

    # Create keyword_taxonomy table
    op.create_table(
        "keyword_taxonomy",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("primary_category", sa.Text(), nullable=False),
        sa.Column("subcategory", sa.Text(), nullable=True),
        sa.Column("specific_term", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_taxonomy")),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["keyword_taxonomy.id"],
            name=op.f("fk_keyword_taxonomy_parent_id_keyword_taxonomy"),
        ),
    )
    op.create_index(
        op.f("ix_keyword_taxonomy_term"), "keyword_taxonomy", ["term"], unique=False
    )
    op.create_index(
        op.f("ix_keyword_taxonomy_primary_category"),
        "keyword_taxonomy",
        ["primary_category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_keyword_taxonomy_subcategory"),
        "keyword_taxonomy",
        ["subcategory"],
        unique=False,
    )

    # Create documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("upload_date", sa.TIMESTAMP(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("batch_jobs_id", sa.Integer(), nullable=True),
        sa.Column("processing_time", sa.Float(), nullable=True),  # 'double' in DBML
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.Column("embeddings", Vector(1536), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.ForeignKeyConstraint(
            ["batch_jobs_id"],
            ["batch_jobs.id"],
            name=op.f("fk_documents_batch_jobs_id_batch_jobs"),
        ),
    )
    op.create_index(
        op.f("ix_documents_filename"), "documents", ["filename"], unique=False
    )
    op.create_index(
        op.f("ix_documents_upload_date"), "documents", ["upload_date"], unique=False
    )
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)
    op.create_index(
        "ix_documents_search_vector_gin",
        "documents",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS documents_embeddings_idx ON documents USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100);"
    )

    # Create classifications table
    op.create_table(
        "classifications",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("confidence", sa.BigInteger(), nullable=True),
        sa.Column("classification_date", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classifications")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_classifications_document_id_documents"),
        ),
    )
    op.create_index(
        op.f("ix_classifications_document_id"),
        "classifications",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classifications_category"),
        "classifications",
        ["category"],
        unique=False,
    )

    # Create communication_focus table
    op.create_table(
        "communication_focus",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("primary_issue", sa.Text(), nullable=True),
        sa.Column("secondary_issues", sa.Text(), nullable=True),
        sa.Column("messaging_strategy", sa.Text(), nullable=True),
        sa.Column("created_date", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_communication_focus")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_communication_focus_document_id_documents"),
        ),
    )
    op.create_index(
        op.f("ix_communication_focus_document_id"),
        "communication_focus",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_communication_focus_primary_issue"),
        "communication_focus",
        ["primary_issue"],
        unique=False,
    )

    # Create design_elements table
    op.create_table(
        "design_elements",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("color_scheme", sa.Text(), nullable=True),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column("mail_piece_type", sa.Text(), nullable=True),
        sa.Column("geographic_location", sa.Text(), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("campaign_name", sa.Text(), nullable=True),
        sa.Column("confidence", sa.BigInteger(), nullable=True),
        sa.Column("created_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("visual_elements", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_design_elements")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_design_elements_document_id_documents"),
        ),
    )
    op.create_index(
        op.f("ix_design_elements_document_id"),
        "design_elements",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_design_elements_geographic_location"),
        "design_elements",
        ["geographic_location"],
        unique=False,
    )

    # Create entities table
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("client_name", sa.Text(), nullable=True),
        sa.Column("opponent_name", sa.Text(), nullable=True),
        sa.Column(
            "creation_date", sa.Text(), nullable=True
        ),  # As per schema, noted as 'text'
        sa.Column("survey_question", sa.Text(), nullable=True),
        sa.Column("file_identifier", sa.Text(), nullable=True),
        sa.Column("created_date", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entities")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_entities_document_id_documents"),
        ),
    )
    op.create_index(
        op.f("ix_entities_document_id"), "entities", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_entities_client_name"), "entities", ["client_name"], unique=False
    )
    op.create_index(
        op.f("ix_entities_opponent_name"), "entities", ["opponent_name"], unique=False
    )

    # Create extracted_text table
    op.create_table(
        "extracted_text",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("confidence", sa.BigInteger(), nullable=True),
        sa.Column("extraction_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("main_message", sa.Text(), nullable=True),
        sa.Column("supporting_text", sa.Text(), nullable=True),
        sa.Column("call_to_action", sa.Text(), nullable=True),
        sa.Column("candidate_name", sa.Text(), nullable=True),
        sa.Column("opponent_name", sa.Text(), nullable=True),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extracted_text")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_extracted_text_document_id_documents"),
        ),
    )
    op.create_index(
        op.f("ix_extracted_text_document_id"),
        "extracted_text",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_text_main_message"),
        "extracted_text",
        ["main_message"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extracted_text_supporting_text"),
        "extracted_text",
        ["supporting_text"],
        unique=False,
    )
    op.create_index(
        "ix_extracted_text_search_vector_gin",
        "extracted_text",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    # Create keyword_synonyms table
    op.create_table(
        "keyword_synonyms",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("taxonomy_id", sa.Integer(), nullable=True),
        sa.Column("synonym", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_synonyms")),
        sa.ForeignKeyConstraint(
            ["taxonomy_id"],
            ["keyword_taxonomy.id"],
            name=op.f("fk_keyword_synonyms_taxonomy_id_keyword_taxonomy"),
        ),
    )
    op.create_index(
        op.f("ix_keyword_synonyms_taxonomy_id"),
        "keyword_synonyms",
        ["taxonomy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_keyword_synonyms_synonym"),
        "keyword_synonyms",
        ["synonym"],
        unique=False,
    )

    # Create llm_analysis table
    op.create_table(
        "llm_analysis",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("summary_description", sa.Text(), nullable=True),
        sa.Column("visual_analysis", sa.Text(), nullable=True),
        sa.Column("content_analysis", sa.Text(), nullable=True),
        sa.Column("campaign_type", sa.Text(), nullable=True),
        sa.Column("election_year", sa.Text(), nullable=True),
        sa.Column("document_tone", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("analysis_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.Column("embeddings", Vector(1536), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_analysis")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_llm_analysis_document_id_documents"),
        ),
    )
    op.create_index(
        op.f("ix_llm_analysis_campaign_type"),
        "llm_analysis",
        ["campaign_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_analysis_document_id"),
        "llm_analysis",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_analysis_document_tone"),
        "llm_analysis",
        ["document_tone"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_analysis_election_year"),
        "llm_analysis",
        ["election_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_analysis_summary_description"),
        "llm_analysis",
        ["summary_description"],
        unique=False,
    )
    op.create_index(
        "ix_llm_analysis_search_vector_gin",
        "llm_analysis",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS llm_analysis_embeddings_idx ON llm_analysis USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100);"
    )

    # Create llm_keywords table
    op.create_table(
        "llm_keywords",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("llm_analysis_id", sa.Integer(), nullable=True),
        sa.Column("keyword", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.BigInteger(), nullable=True),
        sa.Column("taxonomy_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_keywords")),
        sa.ForeignKeyConstraint(
            ["llm_analysis_id"],
            ["llm_analysis.id"],
            name=op.f("fk_llm_keywords_llm_analysis_id_llm_analysis"),
        ),
        sa.ForeignKeyConstraint(
            ["taxonomy_id"],
            ["keyword_taxonomy.id"],
            name=op.f("fk_llm_keywords_taxonomy_id_keyword_taxonomy"),
        ),
    )
    op.create_index(
        op.f("ix_llm_keywords_llm_analysis_id"),
        "llm_keywords",
        ["llm_analysis_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_keywords_keyword"), "llm_keywords", ["keyword"], unique=False
    )

    # Create clients table
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("client_name", sa.Text(), nullable=True),
        sa.Column("campaign_name", sa.Text(), nullable=True),
        sa.Column("created_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_clients_document_id_documents"),
        ),
    )

    # Create dropbox_syncs table
    op.create_table(
        "dropbox_syncs",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("dropbox_file_id", sa.String(255), nullable=True, unique=True),
        sa.Column("dropbox_path", sa.String(512), nullable=True),
        sa.Column("sync_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dropbox_syncs")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_dropbox_syncs_document_id_documents"),
        ),
    )

    # Create search_feedback table
    op.create_table(
        "search_feedback",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("search_query", sa.Text(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("feedback_type", sa.String(50), nullable=True),
        sa.Column("feedback_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("user_comment", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_feedback")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_search_feedback_document_id_documents"),
        ),
    )

    # Create document_scorecards table
    op.create_table(
        "document_scorecards",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("metadata_score", sa.Integer(), nullable=True),
        sa.Column("text_extraction_score", sa.Integer(), nullable=True),
        sa.Column("classification_score", sa.Integer(), nullable=True),
        sa.Column("entity_score", sa.Integer(), nullable=True),
        sa.Column("design_score", sa.Integer(), nullable=True),
        sa.Column("keyword_score", sa.Integer(), nullable=True),
        sa.Column("communication_score", sa.Integer(), nullable=True),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("batch1_success", sa.Boolean(), nullable=True),
        sa.Column("batch2_success", sa.Boolean(), nullable=True),
        sa.Column("batch3_success", sa.Boolean(), nullable=True),
        sa.Column("metadata_flags", sa.Text(), nullable=True),
        sa.Column("text_flags", sa.Text(), nullable=True),
        sa.Column("classification_flags", sa.Text(), nullable=True),
        sa.Column("entity_flags", sa.Text(), nullable=True),
        sa.Column("design_flags", sa.Text(), nullable=True),
        sa.Column("keyword_flags", sa.Text(), nullable=True),
        sa.Column("communication_flags", sa.Text(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=True),
        sa.Column("review_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("corrections_made", sa.Text(), nullable=True),
        sa.Column("created_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_date", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_scorecards")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_scorecards_document_id_documents"),
        ),
    )


def downgrade():
    # Drop tables in reverse order of creation
    op.drop_table("document_scorecards")
    op.drop_table("search_feedback")
    op.drop_table("dropbox_syncs")
    op.drop_table("clients")
    op.drop_table("llm_keywords")

    op.execute("DROP INDEX IF EXISTS llm_analysis_embeddings_idx;")
    op.drop_table("llm_analysis")

    op.drop_table("keyword_synonyms")
    op.drop_table("extracted_text")
    op.drop_table("entities")
    op.drop_table("design_elements")
    op.drop_table("communication_focus")
    op.drop_table("classifications")

    op.execute("DROP INDEX IF EXISTS documents_embeddings_idx;")
    op.drop_table("documents")

    op.drop_table("keyword_taxonomy")
    op.drop_table("batch_jobs")

    # op.execute("DROP EXTENSION IF EXISTS vector;") # Generally not dropped in migrations
