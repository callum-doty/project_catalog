#!/usr/bin/env python
"""
Script to migrate existing LLM keywords to use taxonomy references
"""

import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"keyword_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("migration")


def migrate_existing_keywords():
    """Migrate existing keywords to use taxonomy references"""
    # Import Flask app
    from src.catalog import create_app
    from src.catalog.models import LLMKeyword, KeywordTaxonomy, KeywordSynonym, Document, LLMAnalysis
    from src.catalog import db
    from sqlalchemy import func

    # Create app context
    app = create_app()

    with app.app_context():
        try:
            # Get all LLM keywords that don't have a taxonomy_id
            keywords = LLMKeyword.query.filter(
                LLMKeyword.taxonomy_id.is_(None)).all()
            logger.info(f"Found {len(keywords)} keywords to process")

            # Track progress
            mapped_count = 0
            exact_matches = 0
            partial_matches = 0
            synonym_matches = 0
            no_matches = 0

            # Process each keyword
            for keyword in keywords:
                keyword_text = keyword.keyword.strip().lower()
                if not keyword_text:
                    continue

                # Get analysis and document info for logging
                analysis = LLMAnalysis.query.get(keyword.llm_analysis_id)
                doc_id = analysis.document_id if analysis else "unknown"
                doc = Document.query.get(doc_id) if analysis else None
                doc_name = doc.filename if doc else "unknown"

                # Try exact match first
                taxonomy_term = KeywordTaxonomy.query.filter(
                    func.lower(KeywordTaxonomy.term) == keyword_text
                ).first()

                if taxonomy_term:
                    exact_matches += 1
                    logger.info(
                        f"Exact match: '{keyword_text}' -> '{taxonomy_term.term}' (doc: {doc_name})")
                else:
                    # Try partial match
                    taxonomy_term = KeywordTaxonomy.query.filter(
                        func.lower(KeywordTaxonomy.term).like(
                            f"%{keyword_text}%")
                    ).first()

                    if taxonomy_term:
                        partial_matches += 1
                        logger.info(
                            f"Partial match: '{keyword_text}' -> '{taxonomy_term.term}' (doc: {doc_name})")
                    else:
                        # Try synonym match
                        synonym_match = db.session.query(KeywordTaxonomy).join(
                            KeywordSynonym, KeywordTaxonomy.id == KeywordSynonym.taxonomy_id
                        ).filter(
                            func.lower(KeywordSynonym.synonym) == keyword_text
                        ).first()

                        if synonym_match:
                            taxonomy_term = synonym_match
                            synonym_matches += 1
                            logger.info(
                                f"Synonym match: '{keyword_text}' -> '{taxonomy_term.term}' (doc: {doc_name})")
                        else:
                            no_matches += 1
                            logger.warning(
                                f"No match found for '{keyword_text}' (doc: {doc_name})")

                # Update keyword with taxonomy reference if found
                if taxonomy_term:
                    keyword.taxonomy_id = taxonomy_term.id
                    mapped_count += 1

                # Commit in smaller batches to avoid memory issues
                if mapped_count % 100 == 0:
                    db.session.commit()
                    logger.info(f"Committed batch of {mapped_count} keywords")

            # Final commit for remaining changes
            db.session.commit()

            # Log summary
            logger.info("=" * 50)
            logger.info("Migration Summary:")
            logger.info(f"Total keywords processed: {len(keywords)}")
            logger.info(f"Successfully mapped: {mapped_count}")
            logger.info(f" - Exact matches: {exact_matches}")
            logger.info(f" - Partial matches: {partial_matches}")
            logger.info(f" - Synonym matches: {synonym_matches}")
            logger.info(f"No matches found: {no_matches}")
            logger.info("=" * 50)

            return mapped_count

        except Exception as e:
            logger.error(f"Error during migration: {str(e)}", exc_info=True)
            db.session.rollback()
            return 0


def main():
    """Main entry point"""
    logger.info("Starting keyword migration process")
    try:
        mapped_count = migrate_existing_keywords()
        logger.info(f"Migration completed. Mapped {mapped_count} keywords.")
        return 0
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
