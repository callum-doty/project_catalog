from .celery_app import celery_app, logger
from src.catalog.models import Document
from src.catalog.services.storage_service import MinIOStorage
from src.catalog.services.preview_service import PreviewService
from src.catalog import db

preview_service = PreviewService()
storage = MinIOStorage()


@celery_app.task(name="tasks.generate_preview")
def generate_preview(filename, document_id=None):
    """
    Asynchronously generate and cache a preview for a document
    """
    logger.info(f"Generating preview for {filename} in background task")

    try:
        # Create Flask app context
        from src.catalog import create_app
        from src.catalog.services.preview_service import PreviewService
        from src.catalog import cache

        app = create_app()
        with app.app_context():
            preview_service = PreviewService()
            preview_data = preview_service._generate_preview_internal(filename)

            # Store the preview in cache with a long timeout (1 day)
            cache_key = f"preview:{filename}"
            cache.set(cache_key, preview_data, timeout=86400)

            # Update document if ID provided
            if document_id:
                from src.catalog.models import Document

                document = Document.query.get(document_id)
                if document:
                    document.has_preview = True
                    db.session.commit()

        logger.info(f"Successfully generated and cached preview for {filename}")
        return True

    except Exception as e:
        logger.error(
            f"Error generating preview for {filename}: {str(e)}", exc_info=True
        )
        return False
