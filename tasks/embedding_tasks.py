# tasks/embedding_tasks.py
from .celery_app import celery_app, logger
from app.models.models import Document
from app.extensions import db
import asyncio
import os


if 'FLASK_ENV' in os.environ and os.environ['FLASK_ENV'] == 'development':
    os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
    os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
    os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

@celery_app.task(name='tasks.generate_embeddings')
def generate_embeddings(document_id=None):
    """Generate embeddings for documents"""
    from app import create_app
    from app.services.embeddings_service import EmbeddingsService
    
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
                embeddings_service.generate_and_store_embeddings_for_document(document_id)
            )
            result = {document_id: "success" if success else "failed"}
        else:
            # Process all documents without embeddings
            documents = Document.query.filter(Document.embeddings.is_(None)).all()
            logger.info(f"Generating embeddings for {len(documents)} documents")
            
            result = {}
            for doc in documents:
                try:
                    success = loop.run_until_complete(
                        embeddings_service.generate_and_store_embeddings_for_document(doc.id)
                    )
                    result[doc.id] = "success" if success else "failed"
                except Exception as e:
                    logger.error(f"Error generating embeddings for document {doc.id}: {str(e)}")
                    result[doc.id] = "error"
        
        loop.close()
        return result