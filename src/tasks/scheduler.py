# src/tasks/scheduler.py
from flask_apscheduler import APScheduler
from datetime import datetime
import logging
from typing import Optional, List
from dropbox.files import FileMetadata
import os

scheduler = APScheduler()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DropboxSync:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        # Initialize scheduler with app
        scheduler.init_app(app)
        scheduler.start()

        # Add periodic sync job
        scheduler.add_job(
            id='dropbox_sync',
            func=self.sync_dropbox_documents,
            trigger='interval',
            minutes=30,  # Adjust frequency as needed
            max_instances=1
        )

    def sync_dropbox_documents(self):
        """Main sync function that runs periodically"""
        with self.app.app_context():
            try:
                logger.info(f"Starting Dropbox sync at {datetime.utcnow()}")

                # Initialize Dropbox handler
                from src.integrations.dropbox_handler import DropboxHandler
                handler = DropboxHandler(os.getenv('DROPBOX_ACCESS_TOKEN'))

                # Get list of documents from Dropbox
                dropbox_files = handler.list_documents(
                    "/designs")  # Adjust path as needed

                # Process each file
                processed_count = 0
                error_count = 0

                for file in dropbox_files:
                    try:
                        if self._should_process_file(file):
                            success = self._process_single_file(handler, file)
                            if success:
                                processed_count += 1
                            else:
                                error_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.error(
                            f"Error processing file {file.name}: {str(e)}")

                logger.info(
                    f"Sync completed. Processed: {processed_count}, Errors: {error_count}")

            except Exception as e:
                logger.error(f"Sync failed: {str(e)}")

    def _should_process_file(self, file: FileMetadata) -> bool:
        """Determine if a file should be processed"""
        from src.database.models import Document

        # Check if file already exists in database
        existing_doc = Document.query.filter_by(filename=file.name).first()

        if existing_doc:
            # Check if file has been modified since last sync
            dropbox_modified = file.server_modified
            if existing_doc.upload_date and existing_doc.upload_date >= dropbox_modified:
                return False

        # Check file extension
        allowed_extensions = {'.pdf', '.psd', '.ai'}
        return any(file.name.lower().endswith(ext) for ext in allowed_extensions)

    def _process_single_file(self, handler, file: FileMetadata) -> bool:
        """Process a single file from Dropbox"""
        try:
            from src.database.models import Document, db

            # Download and process file
            document = handler.process_document(file.path_display)

            if document:
                logger.info(f"Successfully processed {file.name}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to process {file.name}: {str(e)}")
            return False
