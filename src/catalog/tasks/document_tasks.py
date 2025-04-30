
import os
import time
import json
from celery import Task
from .celery_app import celery_app
from .task_base import DocumentProcessor
from .celery_app import celery_app, logger
from src.catalog.models import Document, LLMAnalysis, LLMKeyword, Classification, DesignElement, ExtractedText, DropboxSync, Entity, CommunicationFocus
from datetime import datetime, timedelta
from src.catalog import db, cache
from src.catalog.services.preview_service import PreviewService
from src.catalog.services.search_service import SearchService
from src.catalog.services.storage_service import MinIOStorage
import logging
import traceback
from src.catalog.constants import DOCUMENT_STATUSES
from src.catalog.tasks.analysis_utils import check_minimum_analysis


search_service = SearchService()
logger = logging.getLogger(__name__)


class DocumentProcessorTask(Task):
    """Base class for document processing tasks"""
    abstract = True
    _storage = None
    _llm_service = None

    @property
    def storage(self):
        if self._storage is None:
            self._storage = MinIOStorage()
        return self._storage

    @property
    def llm_service(self):
        if self._llm_service is None:
            from catalog.services.llm_service import LLMService
            self._llm_service = LLMService()
        return self._llm_service

    def download_temp_file(self, filename):
        """Download file to temp location for processing"""
        try:
            temp_path = f"/tmp/{filename}"
            self.storage.download_file(filename, temp_path)
            return temp_path
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return None


@celery_app.task(name='tasks.list_tasks')
def list_tasks():
    """List all registered tasks"""
    logger.info("Listing all registered Celery tasks:")
    for task_name in sorted(celery_app.tasks.keys()):
        logger.info(f"- {task_name}")
    return list(celery_app.tasks.keys())


@celery_app.task(bind=True, name='tasks.test_document_processing')
def test_document_processing(self, document_id):
    """Simplified document processing to test Celery execution"""
    logger.info(
        f"=== TESTING DOCUMENT PROCESSING === Task ID: {self.request.id}")
    logger.info(f"Document ID: {document_id}")

    try:
        # Import Flask app
        from src.catalog import create_app
        app = create_app()

        with app.app_context():
            # Update document status
            doc = Document.query.get(document_id)
            if doc:
                logger.info(f"Found document: {doc.filename}")
                doc.status = DOCUMENT_STATUSES['COMPLETED']
                db.session.commit()
                logger.info("Document status updated to COMPLETED")
                return True
            else:
                logger.error(f"Document with ID {document_id} not found")
                return False
    except Exception as e:
        logger.error(f"Error in test processing: {str(e)}", exc_info=True)
        raise


preview_service = PreviewService()


def invalidate_document_cache(document_id):
    """Invalidate all cache related to a specific document"""
    # Import the SearchService here to avoid circular imports
    from catalog.services.search_service import SearchService
    search_service = SearchService()

    try:
        # Invalidate document preview cache
        document = Document.query.get(document_id)
        if document:
            # Clear preview cache for this document
            cache_key = f"preview:{document.filename}"
            cache.delete(cache_key)

        # Clear any memoized cache related to search
        # Using a broader approach to avoid specific function references
        if hasattr(cache, 'delete_memoized'):
            # If a search service exists with these methods, clear them
            if hasattr(search_service, 'get_document_hierarchical_keywords_bulk'):
                cache.delete_memoized(
                    search_service.get_document_hierarchical_keywords_bulk)

            if hasattr(search_service, 'generate_taxonomy_facets'):
                cache.delete_memoized(search_service.generate_taxonomy_facets)

        # Finally, clear the entire cache to be safe
        cache.clear()

    except Exception as e:
        # Log but don't fail if cache invalidation has issues
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f"Error invalidating cache for document {document_id}: {str(e)}")


@celery_app.task(bind=True, base=DocumentProcessorTask, name='process_document')
def process_document(self, filename, minio_path, document_id):
    """Process document through the pipeline using truly modular analysis"""
    logger.info(f"=== STARTING DOCUMENT PROCESSING ===")
    logger.info(f"Task ID: {self.request.id}")
    logger.info(f"Processing document: {filename}")
    logger.info(f"MinIO path: {minio_path}")
    logger.info(f"Document ID: {document_id}")

    # avoid circular import
    from src.catalog import create_app
    app = create_app()

    with app.app_context():
        doc = Document.query.get(document_id)
        if not doc:
            logger.error(f"Document with ID {document_id} not found")
            return False

        doc.status = DOCUMENT_STATUSES['PROCESSING']
        db.session.commit()
        logger.info(f"Updated document status to PROCESSING")

        try:
            logger.info(f"Starting analysis for document: {filename}")

            # Initialize LLM service
            from src.catalog.services.llm_service import LLMService
            llm_service = LLMService()

            # Process in batches with different priorities
            success_count = 0

            # Batch 1: Core components (highest priority)
            logger.info(f"Processing core components (metadata, text)")
            try:
                core_response = llm_service.analyze_document_modular(
                    filename, components=["metadata", "text"]
                )
                if core_response:
                    store_partial_analysis(document_id, core_response)
                    success_count += 1
                    logger.info(f"Core components processed successfully")
            except Exception as e:
                logger.error(f"Error in core component analysis: {str(e)}")

            # Batch 2: Important components
            logger.info(
                f"Processing important components (classification, entities, design)")
            try:
                important_response = llm_service.analyze_document_modular(
                    filename, components=[
                        "classification", "entities", "design"]
                )
                if important_response:
                    store_partial_analysis(document_id, important_response)
                    success_count += 1
                    logger.info(f"Important components processed successfully")
            except Exception as e:
                logger.error(
                    f"Error in important component analysis: {str(e)}")

            # Batch 3: Enrichment components
            logger.info(
                f"Processing enrichment components (keywords, communication)")
            try:
                enrichment_response = llm_service.analyze_document_modular(
                    filename, components=["keywords", "communication"]
                )
                if enrichment_response:
                    store_partial_analysis(document_id, enrichment_response)
                    success_count += 1
                    logger.info(
                        f"Enrichment components processed successfully")
            except Exception as e:
                logger.error(
                    f"Error in enrichment component analysis: {str(e)}")

            # Check if we have minimum necessary components for a useful document
            has_minimum_analysis = check_minimum_analysis(document_id)

            if has_minimum_analysis:
                # Update status and commit
                doc.status = DOCUMENT_STATUSES['COMPLETED']
                db.session.commit()
                logger.info(
                    f"Analysis completed successfully with {success_count} component groups")

                # Queue embeddings generation
                try:
                    from tasks.embedding_tasks import generate_embeddings
                    generate_embeddings.delay(document_id)
                    logger.info(
                        f"Queued embeddings generation for document {document_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to queue embeddings generation: {str(e)}")

                # Queue preview generation
                try:
                    from tasks.preview_tasks import generate_preview
                    generate_preview.delay(filename, document_id)
                    logger.info(
                        f"Queued preview generation for document {document_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to queue preview generation: {str(e)}")

                return True
            else:
                # Mark as failed if we don't have minimum analysis
                doc.status = DOCUMENT_STATUSES['FAILED']
                db.session.commit()
                logger.error(f"Failed to obtain minimum required analysis")
                raise Exception("Failed to obtain minimum required analysis")

        except Exception as e:
            logger.error(
                f"Document processing failed: {str(e)}", exc_info=True)
            doc.status = DOCUMENT_STATUSES['FAILED']
            db.session.commit()
            raise


def store_partial_analysis(document_id: int, response: dict):
    """Store partial analysis results in database"""
    from src.catalog.services.llm_parser import LLMResponseParser

    logger.info(f"Starting store_partial_analysis for document {document_id}")
    logger.info(f"Response keys: {list(response.keys())}")

    if not response:
        logger.warning(f"Empty response for document {document_id}")
        return False

    try:
        parser = LLMResponseParser()

        # Store document analysis (metadata) if present
        if "document_analysis" in response:
            try:
                logger.info(
                    f"Processing document_analysis for document {document_id}")
                llm_analysis_data = parser.parse_llm_analysis(
                    {"document_analysis": response["document_analysis"]})

                # Print the data to be stored
                logger.info(f"Analysis data to save: {llm_analysis_data}")

                # Check if record exists
                llm_analysis = LLMAnalysis.query.filter_by(
                    document_id=document_id).first()

                if llm_analysis:
                    # Update existing record
                    for key, value in llm_analysis_data.items():
                        setattr(llm_analysis, key, value)
                    logger.info(
                        f"Updated existing LLM analysis for document {document_id}")
                else:
                    # Create new record
                    llm_analysis = LLMAnalysis(
                        document_id=document_id,
                        **llm_analysis_data
                    )
                    db.session.add(llm_analysis)
                    logger.info(
                        f"Created new LLM analysis for document {document_id}")

                # Commit immediately for this critical component
                db.session.commit()
                logger.info(f"Successfully stored document analysis")

                # Verify the record was saved
                verification = LLMAnalysis.query.filter_by(
                    document_id=document_id).first()
                if verification is not None:
                    logger.info("Verified LLM Analysis was saved correctly")
                else:
                    logger.error(
                        "LLM Analysis failed to save to database despite successful commit!")

            except Exception as e:
                logger.error(f"Error storing document analysis: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()

        # Store classification if present
        if "classification" in response:
            try:
                classification_data = parser.parse_classification(
                    {"classification": response["classification"]})

                # Check if record exists
                classification = Classification.query.filter_by(
                    document_id=document_id).first()

                if classification:
                    # Update existing record
                    for key, value in classification_data.items():
                        setattr(classification, key, value)
                else:
                    # Create new record
                    classification = Classification(
                        document_id=document_id,
                        **classification_data
                    )
                    db.session.add(classification)

                # Commit immediately after this component
                db.session.commit()
                logger.info(f"Successfully stored classification data")
            except Exception as e:
                logger.error(f"Error storing classification: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()

        # Store extracted text if present
        if "extracted_text" in response:
            try:
                extracted_text_data = parser.parse_extracted_text(
                    {"extracted_text": response["extracted_text"]})

                # Check if record exists
                extracted_text = ExtractedText.query.filter_by(
                    document_id=document_id).first()

                if extracted_text:
                    # Update existing record
                    for key, value in extracted_text_data.items():
                        setattr(extracted_text, key, value)
                else:
                    # Create new record
                    extracted_text = ExtractedText(
                        document_id=document_id,
                        **extracted_text_data
                    )
                    db.session.add(extracted_text)

                # Commit immediately after this component
                db.session.commit()
                logger.info(f"Successfully stored extracted text data")

                # Verify the record was saved
                if ExtractedText.query.filter_by(document_id=document_id).first() is not None:
                    logger.info("Verified Extracted Text was saved correctly")
                else:
                    logger.warning(
                        "Extracted Text failed to save to database!")

            except Exception as e:
                logger.error(f"Error storing extracted text: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()

        # Store design elements if present
        if "design_elements" in response:
            try:
                design_data = parser.parse_design_elements(
                    {"design_elements": response["design_elements"]})

                # Check if record exists
                design = DesignElement.query.filter_by(
                    document_id=document_id).first()

                if design:
                    # Update existing record
                    for key, value in design_data.items():
                        setattr(design, key, value)
                else:
                    # Create new record
                    design = DesignElement(
                        document_id=document_id,
                        **design_data
                    )
                    db.session.add(design)

                db.session.commit()
                logger.info(f"Successfully stored design element data")
            except Exception as e:
                logger.error(f"Error storing design elements: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()

        # Store entity information if present
        if "entities" in response:
            try:
                entity_data = parser.parse_entity_info(
                    {"entities": response["entities"]})

                # Check if record exists
                entity = Entity.query.filter_by(
                    document_id=document_id).first()

                if entity:
                    # Update existing record
                    for key, value in entity_data.items():
                        setattr(entity, key, value)
                else:
                    # Create new record
                    entity = Entity(
                        document_id=document_id,
                        **entity_data
                    )
                    db.session.add(entity)

                db.session.commit()
                logger.info(f"Successfully stored entity information")
            except Exception as e:
                logger.error(f"Error storing entity information: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()

        # Store communication focus if present
        if "communication_focus" in response:
            try:
                focus_data = parser.parse_communication_focus(
                    {"communication_focus": response["communication_focus"]})

                # Check if record exists
                focus = CommunicationFocus.query.filter_by(
                    document_id=document_id).first()

                if focus:
                    # Update existing record
                    for key, value in focus_data.items():
                        setattr(focus, key, value)
                else:
                    # Create new record
                    focus = CommunicationFocus(
                        document_id=document_id,
                        **focus_data
                    )
                    db.session.add(focus)

                db.session.commit()
                logger.info(f"Successfully stored communication focus data")
            except Exception as e:
                logger.error(f"Error storing communication focus: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()

        # Store hierarchical keywords if present
        if "hierarchical_keywords" in response:
            try:
                hierarchical_keywords = parser.parse_hierarchical_keywords(
                    response, document_id)
                for keyword in hierarchical_keywords:
                    db.session.add(keyword)

                db.session.commit()
                logger.info(
                    f"Successfully stored {len(hierarchical_keywords)} hierarchical keywords")
            except Exception as e:
                logger.error(
                    f"Error processing hierarchical keywords: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()

        # Final check after processing all components
        has_minimum = check_minimum_analysis(document_id)
        logger.info(
            f"Final check - Has minimum required analysis: {has_minimum}")

        return True

    except Exception as e:
        logger.error(f"Error storing partial analysis results: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        db.session.rollback()
        return False


def store_analysis_results(document_id: int, response: dict):
    """Store analysis results in database"""
    from src.catalog.services.llm_parser import LLMResponseParser

    try:
        parser = LLMResponseParser()

        # Store LLM Analysis
        llm_analysis_data = parser.parse_llm_analysis(response)
        llm_analysis = LLMAnalysis(
            document_id=document_id,
            **llm_analysis_data
        )
        db.session.add(llm_analysis)
        db.session.flush()  # Get the ID for keywords
        logger.info(f"Stored LLM analysis for document {document_id}")

        # Store Keywords
        keywords_data = parser.parse_keywords(response)
        for keyword_data in keywords_data:
            keyword = LLMKeyword(
                llm_analysis_id=llm_analysis.id,
                **keyword_data
            )
            db.session.add(keyword)
        logger.info(
            f"Stored {len(keywords_data)} keywords for document {document_id}")

        # Store Extracted Text
        extracted_text_data = parser.parse_extracted_text(response)
        extracted_text = ExtractedText(
            document_id=document_id,
            **extracted_text_data
        )
        db.session.add(extracted_text)
        logger.info(f"Stored extracted text for document {document_id}")

        # Store Design Elements
        design_data = parser.parse_design_elements(response)
        design_element = DesignElement(
            document_id=document_id,
            **design_data
        )
        db.session.add(design_element)
        logger.info(f"Stored design elements for document {document_id}")

        # Store Classification
        classification_data = parser.parse_classification(response)
        classification = Classification(
            document_id=document_id,
            **classification_data
        )
        db.session.add(classification)
        logger.info(f"Stored classification for document {document_id}")

        try:
            entity_data = parser.parse_entity_info(response)
            entity = Entity(
                document_id=document_id,
                **entity_data
            )
            db.session.add(entity)
            logger.info(
                f"Stored entity information for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to store entity information: {str(e)}")

        try:
            focus_data = parser.parse_communication_focus(response)
            focus = CommunicationFocus(
                document_id=document_id,
                **focus_data
            )
            db.session.add(focus)
            logger.info(
                f"Stored communication focus for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to store communication focus: {str(e)}")

        try:
            hierarchical_keywords = parser.parse_hierarchical_keywords(
                response, document_id)
            for keyword in hierarchical_keywords:
                db.session.add(keyword)
            logger.info(
                f"Stored {len(hierarchical_keywords)} hierarchical keywords for document {document_id}")
        except Exception as e:
            logger.error(f"Error processing hierarchical keywords: {str(e)}")

        try:
            # Queue embeddings generation
            from tasks.embedding_tasks import generate_embeddings
            generate_embeddings.delay(document_id)
            logger.info(
                f"Queued embeddings generation for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to queue embeddings generation: {str(e)}")

        # Commit all changes to database
        db.session.commit()
        logger.info(
            f"Successfully stored all analysis results for document {document_id}")

        return True

    except Exception as e:
        logger.error(f"Error storing analysis results: {str(e)}")
        db.session.rollback()
        raise


@celery_app.task(name='tasks.recover_pending_documents')
def recover_pending_documents():
    """Identify and recover documents stuck in PENDING state"""
    from src.catalog import create_app
    app = create_app()

    with app.app_context():
        # Get documents stuck in PENDING state for more than 1 hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        stuck_documents = Document.query.filter_by(status='PENDING') \
            .filter(Document.upload_date < one_hour_ago) \
            .all()

        logger.info(
            f"Found {len(stuck_documents)} documents stuck in PENDING state")
        storage = MinIOStorage()  # Initialize storage service

        for doc in stuck_documents:
            try:
                # Check if document exists in MinIO
                minio_path = f"{storage.bucket}/{doc.filename}"
                try:
                    storage.client.stat_object(storage.bucket, doc.filename)
                    file_exists = True
                except:
                    file_exists = False

                if file_exists:
                    # Reprocess the document
                    logger.info(f"Reprocessing stuck document: {doc.filename}")
                    process_document.delay(doc.filename, minio_path, doc.id)
                else:
                    # Mark as failed if file doesn't exist
                    logger.error(
                        f"Document file not found in storage: {doc.filename}")
                    doc.status = 'FAILED'
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error recovering document {doc.id}: {str(e)}")

        return f"Processed {len(stuck_documents)} stuck documents"
