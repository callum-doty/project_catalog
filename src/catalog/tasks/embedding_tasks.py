from .celery_app import celery_app, logger
from src.catalog.models import Document
from src.catalog import db
import asyncio
import os


@celery_app.task(name="tasks.generate_embeddings")
def generate_embeddings(document_id=None):
    """Generate embeddings for documents"""
    from src.catalog import create_app
    from src.catalog.services.embeddings_service import EmbeddingsService

    # Create Flask app context
    app = create_app()

    with app.app_context():
        embeddings_service = EmbeddingsService()

        # Create event loop for async functions
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if document_id:
            # Process specific document
            logger.info(f"Generating embeddings for document {document_id}")
            success = loop.run_until_complete(
                embeddings_service.generate_and_store_embeddings_for_document(
                    document_id
                )
            )
            result = {document_id: "success" if success else "failed"}
        else:
            # Process all documents without embeddings
            documents = Document.query.filter(Document.search_vector.is_(None)).all()
            logger.info(f"Generating embeddings for {len(documents)} documents")

            result = {}
            for doc in documents:
                try:
                    success = loop.run_until_complete(
                        embeddings_service.generate_and_store_embeddings_for_document(
                            doc.id
                        )
                    )
                    result[doc.id] = "success" if success else "failed"
                except Exception as e:
                    logger.error(
                        f"Error generating embeddings for document {doc.id}: {str(e)}"
                    )
                    result[doc.id] = "error"

        loop.close()
        return result
