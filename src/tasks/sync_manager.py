# src/tasks/sync_manager.py
from flask_apscheduler import APScheduler
from src.integrations.dropbox_handler import DropboxHandler
from src.database.models import Document, db
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)
scheduler = APScheduler()


class DropboxSyncManager:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.dropbox = DropboxHandler()
        scheduler.init_app(app)
        scheduler.start()

        # Add scheduled job for syncing
        scheduler.add_job(
            id='sync_dropbox',
            func=self.sync_dropbox_files,
            trigger='interval',
            minutes=30,  # Adjust frequency as needed
            max_instances=1
        )

    def sync_dropbox_files(self):
        """Sync files from Dropbox folder"""
        with self.app.app_context():
            try:
                logger.info("Starting Dropbox sync...")
                folder_path = os.getenv('DROPBOX_FOLDER_PATH', '')
                files = self.dropbox.list_documents(folder_path)

                for file in files:
                    try:
                        self._process_file(file)
                    except Exception as e:
                        logger.error(
                            f"Error processing file {file.name}: {str(e)}")

                logger.info("Dropbox sync completed")

            except Exception as e:
                logger.error(f"Error during Dropbox sync: {str(e)}")

    def _process_file(self, file):
        """Process a single file from Dropbox"""
        # Check if file already exists and needs update
        existing_doc = Document.query.filter_by(filename=file.name).first()

        if existing_doc and self._is_up_to_date(existing_doc, file):
            logger.debug(f"File {file.name} is up to date")
            return

        # Download file from Dropbox
        local_path = os.path.join(self.app.config['UPLOAD_FOLDER'], file.name)
        try:
            content = self.dropbox.download_file(file.path_display)
            with open(local_path, 'wb') as f:
                f.write(content)

            # Update or create database record
            if existing_doc:
                existing_doc.file_size = file.size
                existing_doc.upload_date = datetime.utcnow()
                existing_doc.status = 'updated'
            else:
                new_doc = Document(
                    filename=file.name,
                    file_size=file.size,
                    upload_date=datetime.utcnow(),
                    status='new',
                    page_count=1  # This will be updated by the CNN processing
                )
                db.session.add(new_doc)

            db.session.commit()
            logger.info(f"Successfully processed {file.name}")

        except Exception as e:
            logger.error(f"Error downloading file {file.name}: {str(e)}")
            raise

    def _is_up_to_date(self, doc, dropbox_file):
        """Check if local file is up to date with Dropbox version"""
        # You might want to add more sophisticated comparison logic
        return doc.file_size == dropbox_file.size

    def force_sync(self):
        """Manually trigger a sync"""
        logger.info("Manual sync triggered")
        self.sync_dropbox_files()
