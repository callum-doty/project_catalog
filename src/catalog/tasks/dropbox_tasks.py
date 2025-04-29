

from celery import shared_task
import time
from .celery_app import celery_app, logger
from src.catalog.constants import DOCUMENT_STATUSES, DROPBOX_SYNC_SETTINGS
from src.catalog.services.dropbox_service import DropboxService
from src.catalog.models import Document, DropboxSync
from src.catalog import db
from src.catalog import create_app
import os
import tempfile
from datetime import datetime
import traceback
import json
from .document_tasks import process_document


@celery_app.task(name='tasks.sync_dropbox', bind=True)
def sync_dropbox(self):
    """Sync files from Dropbox folder with rate limiting"""
    logger.info("=== Starting Dropbox sync task ===")

    # Create Flask app instance
    app = create_app()

    # Use app context for database operations
    with app.app_context():
        try:
            # Debug environment variables
            dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN', 'NOT_SET')
            dropbox_folder = os.getenv('DROPBOX_FOLDER_PATH', '')

            # Rate limiting configuration from constants (with environment variable override)
            delay_seconds = int(os.getenv(
                "DOCUMENT_PROCESSING_DELAY",
                str(DROPBOX_SYNC_SETTINGS['DOCUMENT_PROCESSING_DELAY'])
            ))
            batch_size = int(os.getenv(
                "DROPBOX_BATCH_SIZE",
                str(DROPBOX_SYNC_SETTINGS['DROPBOX_BATCH_SIZE'])
            ))
            max_concurrent = int(os.getenv(
                "MAX_CONCURRENT_PROCESSING",
                str(DROPBOX_SYNC_SETTINGS['MAX_CONCURRENT_PROCESSING'])
            ))

            logger.info(
                f"DROPBOX_ACCESS_TOKEN exists: {'Yes' if dropbox_token != 'NOT_SET' else 'No'}")
            logger.info(f"DROPBOX_FOLDER_PATH value: '{dropbox_folder}'")
            logger.info(
                f"Rate limiting: {delay_seconds}s delay, batch size: {batch_size}, max concurrent: {max_concurrent}")

            # Initialize DropboxService
            try:
                dropbox_service = DropboxService()
            except Exception as e:
                logger.error(f"Failed to initialize DropboxService: {str(e)}")
                logger.error(traceback.format_exc())
                return {"status": "error", "message": f"Failed to initialize DropboxService: {str(e)}"}

            # Get already processed files
            processed_files = {
                sync.dropbox_file_id for sync in DropboxSync.query.all()}
            logger.info(
                f"Found {len(processed_files)} previously processed files in database")

            # List files in Dropbox
            try:
                result = dropbox_service.dbx.files_list_folder(
                    dropbox_service.folder_path,
                    recursive=True
                )

                # Initialize new files list
                new_files = []

                # Process files from Dropbox
                for entry in result.entries:
                    try:
                        # Skip if not a file
                        if not hasattr(entry, 'id') or not hasattr(entry, 'path_lower'):
                            continue

                        # Skip if already processed
                        if entry.id in processed_files:
                            continue

                        # Check if it's a supported file type
                        path_lower = entry.path_lower
                        if not (path_lower.endswith('.pdf') or path_lower.endswith('.jpg') or
                                path_lower.endswith('.jpeg') or path_lower.endswith('.png')):
                            logger.info(
                                f"Skipping unsupported file type: {path_lower}")
                            continue

                        # Add to new files list
                        new_files.append(entry)
                        logger.info(f"Found new file to process: {path_lower}")
                    except Exception as e:
                        logger.error(f"Error processing entry: {str(e)}")
                        continue

                # Handle pagination
                while result.has_more:
                    result = dropbox_service.dbx.files_list_folder_continue(
                        result.cursor)
                    for entry in result.entries:
                        try:
                            # Skip if not a file
                            if not hasattr(entry, 'id') or not hasattr(entry, 'path_lower'):
                                continue

                            # Skip if already processed
                            if entry.id in processed_files:
                                continue

                            # Check if it's a supported file type
                            path_lower = entry.path_lower
                            if not (path_lower.endswith('.pdf') or path_lower.endswith('.jpg') or
                                    path_lower.endswith('.jpeg') or path_lower.endswith('.png')):
                                logger.info(
                                    f"Skipping unsupported file type: {path_lower}")
                                continue

                            # Add to new files list
                            new_files.append(entry)
                            logger.info(
                                f"Found new file to process: {path_lower}")
                        except Exception as e:
                            logger.error(f"Error processing entry: {str(e)}")
                            continue

                logger.info(f"Found {len(new_files)} new files to process")

                if not new_files:
                    logger.info("No new files to process")
                    return {"status": "success", "processed": 0, "message": "No new files found"}

            except Exception as e:
                logger.error(f"Error listing Dropbox files: {str(e)}")
                logger.error(traceback.format_exc())
                return {"status": "error", "message": f"Error listing Dropbox files: {str(e)}"}

            # Process files with rate limiting
            processed_count = 0
            error_count = 0

            # Initialize storage service
            from catalog.services.storage_service import MinIOStorage
            storage = MinIOStorage()

            # Process files in batches with delays
            for i, file_metadata in enumerate(new_files):
                temp_file = None
                try:
                    # Get filename from path
                    file_name = os.path.basename(getattr(file_metadata, 'path_display',
                                                         getattr(file_metadata, 'path_lower')))

                    logger.info(
                        f"Processing file: {file_name} ({i+1}/{len(new_files)})")

                    # Create temp file
                    temp_file = tempfile.NamedTemporaryFile(delete=False).name

                    # Download file from Dropbox
                    path_to_download = getattr(
                        file_metadata, 'path_display', file_metadata.path_lower)
                    dropbox_service.dbx.files_download_to_file(
                        temp_file, path_to_download)

                    if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                        logger.error(
                            f"Downloaded file is empty or doesn't exist: {temp_file}")
                        error_count += 1
                        continue

                    file_size = os.path.getsize(temp_file)
                    logger.info(
                        f"Downloaded file {file_name} (Size: {file_size} bytes)")

                    # Create document record
                    document = Document(
                        filename=file_name,
                        upload_date=datetime.utcnow(),
                        file_size=file_size,
                        status=DOCUMENT_STATUSES['PENDING'],
                        page_count=1
                    )
                    db.session.add(document)
                    db.session.flush()

                    # Upload to MinIO
                    try:
                        minio_path = storage.upload_file(temp_file, file_name)
                        logger.info(f"Uploaded to MinIO: {minio_path}")
                    except Exception as e:
                        logger.error(
                            f"MinIO upload failed for {file_name}: {str(e)}")
                        db.session.rollback()
                        error_count += 1
                        continue

                    # Create sync record
                    sync_record = DropboxSync(
                        document_id=document.id,
                        dropbox_file_id=file_metadata.id,
                        dropbox_path=path_to_download,
                        sync_date=datetime.utcnow(),
                        status='SYNCED'
                    )
                    db.session.add(sync_record)
                    db.session.commit()

                    # Queue document for processing
                    process_document.delay(file_name, minio_path, document.id)
                    logger.info(
                        f"Queued {file_name} for processing (Document ID: {document.id})")

                    processed_count += 1

                    # Apply rate limiting
                    if i < len(new_files) - 1:
                        # Apply full delay between batches, or a small delay within batches
                        if (processed_count % batch_size) == 0:
                            logger.info(
                                f"Processed batch of {batch_size}. Waiting {delay_seconds}s before next batch...")
                            time.sleep(delay_seconds)
                        else:
                            # Small delay between documents in the same batch
                            small_delay = 5
                            logger.info(
                                f"Adding small delay of {small_delay}s between files in batch")
                            time.sleep(small_delay)

                except Exception as e:
                    logger.error(
                        f"Error processing file {getattr(file_metadata, 'name', 'unknown')}: {str(e)}")
                    logger.error(traceback.format_exc())
                    error_count += 1
                    db.session.rollback()
                finally:
                    # Clean up temp file
                    if temp_file and os.path.exists(temp_file):
                        os.remove(temp_file)

            # Return summary
            result = {
                "status": "success",
                "processed": processed_count,
                "errors": error_count,
                "total": len(new_files),
                "message": f"Processed {processed_count} out of {len(new_files)} files. Errors: {error_count}"
            }

            logger.info(f"=== Sync task complete: {json.dumps(result)} ===")
            return result

        except Exception as e:
            logger.error(f"Error in Dropbox sync task: {str(e)}")
            logger.error(traceback.format_exc())
            return {"status": "error", "message": f"Dropbox sync failed: {str(e)}"}
