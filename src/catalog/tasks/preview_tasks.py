from .celery_app import celery_app, logger
from src.catalog.models import Document

# from src.catalog.services.storage_service import MinIOStorage # Not directly used here anymore
# from src.catalog.services.preview_service import PreviewService # Instantiated inside task
from src.catalog import db
from datetime import datetime

# preview_service = PreviewService() # Instantiated inside task or app context
# storage = MinIOStorage() # Not directly used here anymore


@celery_app.task(name="tasks.generate_preview", bind=True)
def generate_preview(self, document_id, filename):  # document_id is now mandatory
    """
    Asynchronously generates a preview for a document and updates its status.
    """
    logger.info(
        f"Task {self.request.id}: Starting preview generation for document ID {document_id}, filename {filename}"
    )

    # Create Flask app context to access db, services, etc.
    from src.catalog import (
        create_app,
        cache,
    )  # cache might still be used by PreviewService
    from src.catalog.services.preview_service import (
        PreviewService as AppPreviewService,
    )  # Avoid name clash

    app = create_app()
    with app.app_context():
        document = db.session.get(Document, document_id)

        if not document:
            logger.error(
                f"Task {self.request.id}: Document with ID {document_id} not found. Aborting preview generation."
            )
            return False

        # Initial status update: PENDING
        document.preview_status = "PENDING"
        document.preview_task_id = self.request.id
        document.s3_preview_key = None  # Clear any old key
        document.preview_error_message = None  # Clear any old error
        document.preview_generated_at = None  # Clear any old timestamp
        try:
            db.session.commit()
        except Exception as e_commit_pending:
            logger.error(
                f"Task {self.request.id}: Failed to commit PENDING status for document {document_id}: {e_commit_pending}",
                exc_info=True,
            )
            # Optionally, re-raise or handle so the task retries if appropriate
            return False  # Or raise to trigger retry

        try:
            # Instantiate PreviewService within app_context if it needs app config
            preview_service_instance = AppPreviewService()

            # Assuming _generate_preview_internal handles actual generation and S3 upload,
            # and returns a dictionary or object with s3_key.
            # Example: preview_result = {'s3_key': 'previews/some_file.jpg', ...other_data}
            # If it returns raw data, this task needs to upload it to S3/Minio.
            preview_result = preview_service_instance._generate_preview_internal(
                filename
            )

            if (
                not preview_result
                or not isinstance(preview_result, dict)
                or "s3_key" not in preview_result
            ):
                # This condition depends heavily on what _generate_preview_internal actually returns.
                # If it returns raw data, this task needs to upload it.
                # For now, assuming it must return an s3_key.
                logger.error(
                    f"Task {self.request.id}: Preview generation for {filename} (doc ID {document_id}) did not return a valid s3_key."
                )
                document.preview_status = "FAILED"
                document.preview_error_message = (
                    "Preview generation did not yield an S3 key."
                )
                db.session.commit()
                return False

            # Store the preview in cache if PreviewService doesn't do it already
            # The original code cached `preview_data`. If `preview_result` is metadata, caching it might still be useful.
            # If `preview_result` contains the actual preview content (e.g. `preview_result['content']`), cache that.
            # For now, let's assume PreviewService handles its own caching if needed, or the API endpoint will cache.
            # cache_key = f"preview:{filename}" # Or use document_id for more specific caching
            # cache.set(cache_key, preview_result, timeout=86400) # Example: caching the result metadata

            # Update document on success
            document.preview_status = "SUCCESS"
            document.s3_preview_key = preview_result[
                "s3_key"
            ]  # Critical assumption here
            document.preview_generated_at = datetime.utcnow()
            document.preview_error_message = None  # Clear error on success

            db.session.commit()
            logger.info(
                f"Task {self.request.id}: Successfully generated preview for document {document_id} (file: {filename}). S3 Key: {document.s3_preview_key}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Task {self.request.id}: Error generating preview for document {document_id} (file: {filename}): {str(e)}",
                exc_info=True,
            )
            if document:  # Document should exist if we passed the initial check
                document.preview_status = "FAILED"
                document.preview_error_message = str(e)[
                    :1024
                ]  # Truncate if error message is too long for DB field
                try:
                    db.session.commit()
                except Exception as e_commit_fail:
                    logger.error(
                        f"Task {self.request.id}: Failed to commit FAILED status for document {document_id}: {e_commit_fail}",
                        exc_info=True,
                    )
            return False
