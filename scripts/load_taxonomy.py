import os
import sys
import logging
from flask import current_app

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.catalog import create_app, db
from src.catalog.services.taxonomy_service import TaxonomyService
from src.catalog.models.keyword import KeywordTaxonomy, KeywordSynonym

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Main function to load taxonomy from CSV."""
    app = create_app()
    with app.app_context():
        logger.info("Starting taxonomy loading process...")

        # Path to the canonical taxonomy file
        # Check if running in Docker (APP_SETTINGS contains Docker) or locally
        app_settings = os.getenv("APP_SETTINGS", "")
        if "Docker" in app_settings:
            # Docker environment - use absolute path
            file_path = "/app/data/taxonomy.csv"
        else:
            # Local environment - use relative path
            file_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "taxonomy.csv"
            )

        if not os.path.exists(file_path):
            logger.error(f"Taxonomy file not found at: {file_path}")
            return

        logger.info(f"Loading taxonomy from: {file_path}")

        # Clear existing taxonomy data
        db.session.query(KeywordSynonym).delete()
        db.session.query(KeywordTaxonomy).delete()
        db.session.commit()
        logger.info("Cleared existing taxonomy data.")

        # Initialize taxonomy from the CSV file
        success, message = TaxonomyService.initialize_taxonomy_from_file(file_path)

        if success:
            logger.info(f"Taxonomy loading successful: {message}")
        else:
            logger.error(f"Taxonomy loading failed: {message}")


if __name__ == "__main__":
    main()
