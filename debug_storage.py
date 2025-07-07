#!/usr/bin/env python3
"""
Debug script to check storage issues and fix file locations
"""

import os
import sys
import logging
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_local_storage():
    """Check what files exist in local storage"""
    base_path = "/tmp/mock_storage"
    logger.info(f"Checking local storage at: {base_path}")

    if not os.path.exists(base_path):
        logger.info("Local storage directory does not exist")
        return

    # Walk through all files
    for root, dirs, files in os.walk(base_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_path)
            size = os.path.getsize(full_path)
            logger.info(f"Found file: {rel_path} (size: {size} bytes)")


def check_minio_connection():
    """Check MinIO connection and list files"""
    try:
        # Check environment variables first
        flask_env = os.getenv("FLASK_ENV")
        use_minio_in_dev = os.getenv("USE_MINIO_IN_DEV")
        logger.info(f"FLASK_ENV: {flask_env}")
        logger.info(f"USE_MINIO_IN_DEV: {use_minio_in_dev}")

        from src.catalog.services.storage_service import MinIOStorage

        storage = MinIOStorage()
        logger.info(f"Storage client type: {type(storage.client)}")
        logger.info(f"Storage bucket: {storage.bucket}")

        # Try to list files
        try:
            files = storage.list_files()
            logger.info(f"Found {len(files)} files in storage:")
            for file in files:
                logger.info(f"  - {file}")
        except Exception as e:
            logger.error(f"Error listing files: {e}")

        # Check if bucket exists
        try:
            bucket_exists = storage.bucket_exists(storage.bucket)
            logger.info(f"Bucket '{storage.bucket}' exists: {bucket_exists}")
        except Exception as e:
            logger.error(f"Error checking bucket: {e}")

    except Exception as e:
        logger.error(f"Error initializing storage: {e}")


def check_database_documents():
    """Check what documents are in the database"""
    try:
        # Set up Flask app context
        from src.catalog import create_app, db
        from src.catalog.models import Document

        app = create_app()
        with app.app_context():
            documents = Document.query.all()
            logger.info(f"Found {len(documents)} documents in database:")

            for doc in documents:
                logger.info(
                    f"  ID: {doc.id}, Filename: {doc.filename}, Status: {doc.status}"
                )

                # Try to check if file exists in storage
                try:
                    from src.catalog.services.storage_service import MinIOStorage

                    storage = MinIOStorage()

                    # Try to get file
                    file_data = storage.get_file(doc.filename)
                    if file_data:
                        logger.info(
                            f"    ✓ File exists in storage (size: {len(file_data)} bytes)"
                        )
                    else:
                        logger.warning(f"    ✗ File NOT found in storage")

                    # Try stat_object
                    try:
                        stat = storage.stat_object(storage.bucket, doc.filename)
                        logger.info(f"    ✓ File stat successful")
                    except Exception as e:
                        logger.warning(f"    ✗ File stat failed: {e}")

                except Exception as e:
                    logger.error(f"    Error checking file: {e}")

    except Exception as e:
        logger.error(f"Error checking database: {e}")


def fix_file_locations():
    """Try to fix file locations by moving files to correct bucket structure"""
    base_path = "/tmp/mock_storage"
    documents_path = os.path.join(base_path, "documents")

    if not os.path.exists(base_path):
        logger.info("No local storage to fix")
        return

    # Create documents directory if it doesn't exist
    os.makedirs(documents_path, exist_ok=True)

    # Move files from root to documents bucket
    moved_count = 0
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)

        # Skip directories
        if os.path.isdir(item_path):
            continue

        # Move file to documents bucket
        dest_path = os.path.join(documents_path, item)
        if not os.path.exists(dest_path):
            try:
                import shutil

                shutil.move(item_path, dest_path)
                logger.info(f"Moved {item} to documents bucket")
                moved_count += 1
            except Exception as e:
                logger.error(f"Error moving {item}: {e}")

    logger.info(f"Moved {moved_count} files to documents bucket")


if __name__ == "__main__":
    logger.info("=== Storage Debug Script ===")

    logger.info("\n1. Checking local storage...")
    check_local_storage()

    logger.info("\n2. Checking MinIO connection...")
    check_minio_connection()

    logger.info("\n3. Checking database documents...")
    check_database_documents()

    logger.info("\n4. Fixing file locations...")
    fix_file_locations()

    logger.info("\n5. Re-checking after fixes...")
    check_local_storage()
    check_database_documents()

    logger.info("\n=== Debug Complete ===")
