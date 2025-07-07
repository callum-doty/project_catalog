# app/services/taxonomy_service.py

import logging
import json
import csv
import os
from io import StringIO
from src.catalog.models import KeywordTaxonomy, KeywordSynonym
from src.catalog import db
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app

logger = logging.getLogger(__name__)


class TaxonomyService:
    """Service for managing keyword taxonomy"""

    @staticmethod
    def initialize_taxonomy_from_file(file_path):
        """Initialize taxonomy from a structured CSV file"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"Taxonomy file not found: {file_path}")
                return False, "Taxonomy file not found"

            with open(file_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            counter = {"created": 0, "errors": 0}

            for row in rows:
                if not row.get("primary_category") or not row.get("term"):
                    counter["errors"] += 1
                    continue

                try:
                    term = KeywordTaxonomy(
                        term=row["term"],
                        primary_category=row["primary_category"],
                        subcategory=row.get("subcategory", ""),
                        description=row.get("description", ""),
                    )
                    db.session.add(term)
                    counter["created"] += 1
                except Exception as e:
                    logger.error(
                        f"Error creating taxonomy term {row.get('term')}: {str(e)}"
                    )
                    counter["errors"] += 1
                    continue
            db.session.commit()
            logger.info(
                f"Taxonomy initialization complete: {counter['created']} terms created, {counter['errors']} errors"
            )
            return True, f"Successfully created {counter['created']} taxonomy terms"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Taxonomy initialization failed: {str(e)}")
            return False, f"Taxonomy initialization failed: {str(e)}"

    @staticmethod
    def export_taxonomy_to_csv():
        """Export the entire taxonomy to CSV format"""
        try:
            # Query all taxonomy terms
            terms = KeywordTaxonomy.query.all()

            if not terms:
                return False, "No taxonomy terms found to export"

            # Create CSV in memory
            output = StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(
                [
                    "id",
                    "term",
                    "primary_category",
                    "subcategory",
                    "specific_term",
                    "parent_id",
                    "description",
                    "synonyms",
                ]
            )

            # Write data rows
            for term in terms:
                # Get synonyms as comma-separated string
                synonyms = (
                    ", ".join([s.synonym for s in term.synonyms])
                    if term.synonyms
                    else ""
                )

                writer.writerow(
                    [
                        term.id,
                        term.term,
                        term.primary_category,
                        term.subcategory or "",
                        term.specific_term or "",
                        term.parent_id or "",
                        term.description or "",
                        synonyms,
                    ]
                )

            # Get CSV as string
            csv_data = output.getvalue()
            output.close()

            return True, csv_data

        except Exception as e:
            logger.error(f"Error exporting taxonomy: {str(e)}")
            return False, f"Export failed: {str(e)}"

    @staticmethod
    def get_taxonomy_stats():
        """Get statistics about the taxonomy"""
        try:
            stats = {
                "total_terms": KeywordTaxonomy.query.count(),
                "primary_categories": {},
                "terms_with_synonyms": db.session.query(KeywordTaxonomy.id)
                .join(KeywordSynonym)
                .distinct()
                .count(),
                "total_synonyms": KeywordSynonym.query.count(),
                "hierarchical_terms": KeywordTaxonomy.query.filter(
                    KeywordTaxonomy.parent_id.isnot(None)
                ).count(),
            }

            # Get counts by primary category
            category_counts = (
                db.session.query(
                    KeywordTaxonomy.primary_category, db.func.count(KeywordTaxonomy.id)
                )
                .group_by(KeywordTaxonomy.primary_category)
                .all()
            )

            for category, count in category_counts:
                stats["primary_categories"][category] = count

            return stats
        except Exception as e:
            logger.error(f"Error getting taxonomy stats: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def find_or_create_taxonomy_term(
        term, primary_category, subcategory=None, synonyms=None, strict=False
    ):
        """
        Find an existing taxonomy term or create a new one.
        If strict is True, it will not create new terms.
        """
        try:
            # Normalize inputs
            term = term.strip()
            primary_category = primary_category.strip()
            subcategory = subcategory.strip() if subcategory else None

            # Check for existing term
            existing_term = KeywordTaxonomy.query.filter(
                KeywordTaxonomy.term == term,
                KeywordTaxonomy.primary_category == primary_category,
            )

            if subcategory:
                existing_term = existing_term.filter(
                    KeywordTaxonomy.subcategory == subcategory
                )

            existing_term = existing_term.first()

            if existing_term:
                return existing_term

            if strict:
                logger.warning(f"Strict mode: Term not found and not created: {term}")
                return None

            # Create new term
            new_term = KeywordTaxonomy(
                term=term,
                primary_category=primary_category,
                subcategory=subcategory,
            )
            db.session.add(new_term)
            db.session.commit()
            logger.info(f"Created new taxonomy term: {term} ({primary_category})")
            return new_term

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error finding/creating taxonomy term: {str(e)}")
            raise

    @staticmethod
    def get_taxonomy_for_prompt():
        """Get the taxonomy formatted for prompt injection."""
        try:
            terms = KeywordTaxonomy.query.order_by(
                KeywordTaxonomy.primary_category,
                KeywordTaxonomy.subcategory,
                KeywordTaxonomy.term,
            ).all()

            taxonomy_structure = {}
            for term in terms:
                if term.primary_category not in taxonomy_structure:
                    taxonomy_structure[term.primary_category] = {}
                if term.subcategory not in taxonomy_structure[term.primary_category]:
                    taxonomy_structure[term.primary_category][term.subcategory] = []
                taxonomy_structure[term.primary_category][term.subcategory].append(
                    term.term
                )

            return taxonomy_structure
        except Exception as e:
            logger.error(f"Error getting taxonomy for prompt: {str(e)}")
            return {}
