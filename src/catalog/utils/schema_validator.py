"""
Schema validation utilities to ensure the database schema is properly configured
before starting the application.
"""

import logging
from sqlalchemy import text
from src.catalog import db

logger = logging.getLogger(__name__)


def check_column_exists(table, column):
    """Check if a column exists in a table"""
    sql = text(
        f"""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = '{table}'
            AND column_name = '{column}'
        );
    """
    )
    result = db.session.execute(sql).scalar()
    return result


def check_extension_exists(extension_name):
    """Check if a PostgreSQL extension exists"""
    sql = text(
        f"""
        SELECT EXISTS (
            SELECT 1
            FROM pg_extension
            WHERE extname = '{extension_name}'
        );
    """
    )
    result = db.session.execute(sql).scalar()
    return result


def validate_schema():
    """
    Validate that the database schema is properly configured.
    Returns a tuple of (is_valid, issues) where is_valid is a boolean
    and issues is a list of strings describing any issues found.
    """
    issues = []

    # Check for required extensions
    if not check_extension_exists("vector"):
        issues.append("pgvector extension is not installed")

    # Check for required columns in documents table
    required_columns_documents = [
        "id",
        "filename",
        "upload_date",
        "file_size",
        "page_count",
        "status",
        "search_vector",
        "embeddings",
    ]

    for column in required_columns_documents:
        if not check_column_exists("documents", column):
            issues.append(f"documents.{column} column is missing")

    # Check for required columns in llm_analysis table
    required_columns_llm_analysis = [
        "id",
        "document_id",
        "summary_description",
        "content_analysis",
        "analysis_date",
        "embeddings",
    ]

    for column in required_columns_llm_analysis:
        if not check_column_exists("llm_analysis", column):
            issues.append(f"llm_analysis.{column} column is missing")

    # Return validation result
    is_valid = len(issues) == 0
    return is_valid, issues


def validate_schema_or_fail():
    """
    Validate the database schema and raise an exception if it's not valid.
    This can be called during application startup to ensure the schema is correct.
    """
    is_valid, issues = validate_schema()

    if not is_valid:
        error_message = "Database schema validation failed:\n"
        for issue in issues:
            error_message += f"- {issue}\n"
        error_message += "\nPlease run the appropriate migration or fix script to resolve these issues."

        logger.error(error_message)
        raise RuntimeError(error_message)

    logger.info("Database schema validation passed")
    return True
