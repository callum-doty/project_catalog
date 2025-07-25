import os
import time
import json
from celery import Task
from .celery_app import celery_app
from .task_base import DocumentProcessor
from .celery_app import celery_app, logger
from src.catalog.models import (
    Document,
    LLMAnalysis,
    LLMKeyword,
    Classification,
    DesignElement,
    ExtractedText,
    DropboxSync,
    Entity,
    CommunicationFocus,
    KeywordTaxonomy,
)
from datetime import datetime, timedelta
from src.catalog import db, cache
from src.catalog.services.preview_service import PreviewService
from src.catalog.services.search_service import SearchService
from src.catalog.services.storage_service import MinIOStorage
import logging
import traceback
from src.catalog.constants import DOCUMENT_STATUSES
from src.catalog.tasks.analysis_utils import check_minimum_analysis
from src.catalog.services.llm_parser import LLMResponseParser


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
            from src.catalog.services.llm_service import LLMService

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


@celery_app.task(name="tasks.list_tasks")
def list_tasks():
    """List all registered tasks"""
    logger.info("Listing all registered Celery tasks:")
    for task_name in sorted(celery_app.tasks.keys()):
        logger.info(f"- {task_name}")
    return list(celery_app.tasks.keys())


@celery_app.task(bind=True, name="tasks.test_document_processing")
def test_document_processing(self, document_id):
    """Simplified document processing to test Celery execution"""
    logger.info(f"=== TESTING DOCUMENT PROCESSING === Task ID: {self.request.id}")
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
                doc.status = DOCUMENT_STATUSES["COMPLETED"]
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
    from src.catalog.services.search_service import SearchService

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
        if hasattr(cache, "delete_memoized"):
            # If a search service exists with these methods, clear them
            if hasattr(search_service, "get_document_hierarchical_keywords_bulk"):
                cache.delete_memoized(
                    search_service.get_document_hierarchical_keywords_bulk
                )

            if hasattr(search_service, "generate_taxonomy_facets"):
                cache.delete_memoized(search_service.generate_taxonomy_facets)

        # Finally, clear the entire cache to be safe
        cache.clear()

    except Exception as e:
        # Log but don't fail if cache invalidation has issues
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error invalidating cache for document {document_id}: {str(e)}")


@celery_app.task(bind=True, name="process_document")
def process_document(self, filename, minio_path, document_id):
    """Process document through the pipeline using truly modular analysis"""
    logger.info(f"=== STARTING DOCUMENT PROCESSING ===")
    logger.info(f"Task ID: {self.request.id}")
    logger.info(f"Processing document: {filename}")
    logger.info(f"MinIO path: {minio_path}")
    logger.info(f"Document ID: {document_id}")

    # Import Flask app in function to avoid circular imports
    from src.catalog import create_app

    app = create_app()

    with app.app_context():
        try:
            doc = Document.query.get(document_id)
            if not doc:
                logger.error(f"Document with ID {document_id} not found")
                return False

            doc.status = DOCUMENT_STATUSES["PROCESSING"]
            db.session.commit()
            logger.info(f"Updated document status to PROCESSING")

            # Initialize LLM service
            from src.catalog.services.llm_service import LLMService

            llm_service = LLMService()

            # Process document with a single call
            analysis_response = llm_service.analyze_document(filename)

            if analysis_response:
                store_partial_analysis(document_id, analysis_response)

            # Check if we have minimum required analysis
            has_minimum_analysis = check_minimum_analysis(document_id)
            logger.info(f"Minimum analysis check: {has_minimum_analysis}")

            if has_minimum_analysis:
                try:
                    # Update status to COMPLETED
                    # Re-fetch to ensure fresh state
                    doc = Document.query.get(document_id)
                    if doc:
                        doc.status = DOCUMENT_STATUSES["COMPLETED"]
                        db.session.commit()

                        # Verify the status was updated
                        db.session.refresh(doc)
                        if doc.status == DOCUMENT_STATUSES["COMPLETED"]:
                            logger.info(f"Document processing completed successfully")
                        else:
                            logger.error(
                                f"Failed to update document status to COMPLETED"
                            )
                            return False
                    else:
                        logger.error(
                            f"Document {document_id} not found when updating status"
                        )
                        return False

                    # Queue preview generation
                    try:
                        from src.catalog.tasks.preview_tasks import generate_preview

                        # Corrected argument order: document_id first, then filename
                        generate_preview.delay(document_id, filename)
                        logger.info(
                            f"Queued preview generation for document ID {document_id} ({filename})"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to queue preview for document ID {document_id} ({filename}): {str(e)}"
                        )

                    # Queue embeddings generation
                    try:
                        from src.catalog.tasks.embedding_tasks import (
                            generate_embeddings,
                        )

                        generate_embeddings.delay(document_id)
                        logger.info(
                            f"Queued embeddings generation for document {document_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to queue embeddings generation: {str(e)}")

                    return True
                except Exception as status_e:
                    logger.error(
                        f"Error updating document status to COMPLETED: {str(status_e)}"
                    )
                    db.session.rollback()
                    return False
            else:
                # Mark as failed if we don't have minimum analysis
                try:
                    doc = Document.query.get(document_id)
                    if doc:
                        doc.status = DOCUMENT_STATUSES["FAILED"]
                        db.session.commit()
                        logger.error(f"Failed to obtain minimum required analysis")
                    return False
                except Exception as e:
                    logger.error(f"Error updating document status to FAILED: {str(e)}")
                    db.session.rollback()
                    return False

        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}", exc_info=True)

            try:
                # Update status to FAILED (not COMPLETED) when an exception occurs
                doc = Document.query.get(document_id)
                if doc and doc.status != DOCUMENT_STATUSES["FAILED"]:
                    # Change to FAILED
                    doc.status = DOCUMENT_STATUSES["FAILED"]
                    db.session.commit()
                    logger.info(f"✅ Updated document {document_id} status to FAILED")
            except Exception as status_e:
                logger.error(
                    f"❌ Failed to update document status to FAILED: {str(status_e)}"
                )

            return False


def store_partial_analysis(document_id: int, response: dict):
    """Store partial analysis results in database"""
    try:
        # Process each component in the response
        for component, data in response.items():
            try:
                if component == "document_analysis":
                    # Store LLM analysis
                    analysis_data = LLMResponseParser.parse_llm_analysis(response)
                    llm_analysis = LLMAnalysis(document_id=document_id, **analysis_data)
                    db.session.add(llm_analysis)
                    db.session.commit()
                    logger.info("Successfully stored document analysis")
                    logger.info("Verified LLM Analysis was saved correctly")

                elif component == "extracted_text":
                    # Store extracted text
                    text_data = LLMResponseParser.parse_extracted_text(response)
                    extracted_text = ExtractedText(document_id=document_id, **text_data)
                    db.session.add(extracted_text)
                    db.session.commit()
                    logger.info("Successfully stored extracted text data")
                    logger.info("Verified Extracted Text was saved correctly")

                elif component == "classification":
                    # Store classification
                    classification_data = LLMResponseParser.parse_classification(
                        response
                    )
                    classification = Classification(
                        document_id=document_id, **classification_data
                    )
                    db.session.add(classification)
                    db.session.commit()
                    logger.info("Successfully stored classification data")

                elif component == "design_elements":
                    # Store design elements
                    design_data = LLMResponseParser.parse_design_elements(response)
                    design = DesignElement(document_id=document_id, **design_data)
                    db.session.add(design)
                    db.session.commit()
                    logger.info("Successfully stored design element data")

                elif component == "entities":
                    # Store entity information
                    entity_data = LLMResponseParser.parse_entity_info(data)
                    entity = Entity(document_id=document_id, **entity_data)
                    db.session.add(entity)
                    db.session.commit()
                    logger.info("Successfully stored entity information")

                elif component == "communication_focus":
                    # Store communication focus
                    focus_data = LLMResponseParser.parse_communication_focus(response)
                    focus = CommunicationFocus(document_id=document_id, **focus_data)
                    db.session.add(focus)
                    db.session.commit()
                    logger.info("Successfully stored communication focus data")

                elif component == "hierarchical_keywords":
                    try:
                        # First get or create LLMAnalysis for this document
                        llm_analysis = LLMAnalysis.query.filter_by(
                            document_id=document_id
                        ).first()
                        if not llm_analysis:
                            logger.info(
                                f"Creating new LLMAnalysis for document {document_id}"
                            )
                            llm_analysis = LLMAnalysis(
                                document_id=document_id,
                                analysis_date=datetime.utcnow(),
                                model_version="claude-3-opus-20240229",
                            )
                            db.session.add(llm_analysis)
                            db.session.flush()  # Get the ID
                            logger.info(
                                f"Created new LLMAnalysis with ID {llm_analysis.id}"
                            )
                        else:
                            logger.info(
                                f"Found existing LLMAnalysis with ID {llm_analysis.id}"
                            )

                        # Wrap the data in a dictionary with the expected key
                        wrapped_data = {"hierarchical_keywords": data}

                        # Store hierarchical keywords
                        doc_keywords = LLMResponseParser.parse_hierarchical_keywords(
                            wrapped_data, document_id
                        )
                        logger.info(
                            f"Processing {len(doc_keywords)} hierarchical keywords for document {document_id}"
                        )

                        # Convert DocumentKeyword objects to LLMKeyword objects
                        keywords_added = 0
                        for doc_keyword in doc_keywords:
                            try:
                                # Get the taxonomy term directly from the database
                                taxonomy_term = KeywordTaxonomy.query.get(
                                    doc_keyword.taxonomy_id
                                )
                                if taxonomy_term:
                                    logger.info(
                                        f"Creating LLMKeyword for term: {taxonomy_term.term}"
                                    )
                                    keyword = LLMKeyword(
                                        llm_analysis_id=llm_analysis.id,
                                        keyword=taxonomy_term.term,
                                        category=taxonomy_term.primary_category,
                                        relevance_score=(
                                            int(doc_keyword.relevance_score * 100)
                                            if doc_keyword.relevance_score
                                            else 0
                                        ),
                                        taxonomy_id=taxonomy_term.id,  # Ensure taxonomy_id is set
                                    )
                                    db.session.add(keyword)
                                    keywords_added += 1
                                    logger.info(
                                        f"Added keyword {taxonomy_term.term} to session"
                                    )
                                else:
                                    logger.warning(
                                        f"No taxonomy term found for ID {doc_keyword.taxonomy_id}"
                                    )
                            except Exception as keyword_error:
                                logger.error(
                                    f"Error processing individual keyword: {str(keyword_error)}"
                                )
                                logger.error(traceback.format_exc())
                                continue

                        # Commit the changes
                        try:
                            db.session.commit()
                            logger.info(
                                f"Successfully committed {keywords_added} keywords to database"
                            )
                        except Exception as commit_error:
                            logger.error(
                                f"Error committing keywords: {str(commit_error)}"
                            )
                            logger.error(traceback.format_exc())
                            db.session.rollback()
                            raise

                        # Verify keywords were stored using llm_analysis_id
                        stored_keywords = LLMKeyword.query.filter_by(
                            llm_analysis_id=llm_analysis.id
                        ).count()
                        if stored_keywords != keywords_added:
                            logger.error(
                                f"Keyword count mismatch: expected {keywords_added}, found {stored_keywords}"
                            )
                            # Try to rollback and re-add any missing keywords
                            db.session.rollback()
                            raise Exception(
                                f"Keyword count mismatch: expected {keywords_added}, found {stored_keywords}"
                            )
                        else:
                            logger.info(
                                f"Verification: {stored_keywords} keywords in database for analysis {llm_analysis.id}"
                            )
                            logger.info(
                                f"Successfully processed hierarchical keywords for document {document_id}"
                            )
                    except Exception as e:
                        logger.error(f"Error storing hierarchical keywords: {str(e)}")
                        logger.error(traceback.format_exc())
                        db.session.rollback()
                        raise

            except Exception as component_error:
                logger.error(f"Error storing {component}: {str(component_error)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()
                # Continue processing other components instead of failing completely
                continue

        return True

    except Exception as e:
        logger.error(f"Error in store_partial_analysis: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        db.session.rollback()
        return False


def map_keywords_to_taxonomy(document_id, llm_analysis_id, keywords):
    """Map extracted keywords to taxonomy terms"""
    from src.catalog.models import KeywordTaxonomy, LLMKeyword, KeywordSynonym
    from src.catalog import db
    from sqlalchemy import func
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Get existing keywords from LLM analysis
        llm_keywords = LLMKeyword.query.filter_by(llm_analysis_id=llm_analysis_id).all()

        # If keywords already exist for this analysis, we can skip
        if llm_keywords:
            logger.info(f"Keywords already exist for analysis ID {llm_analysis_id}")
            return True

        # Process each keyword
        keywords_added = 0
        for keyword_data in keywords:
            keyword_text = keyword_data.get("keyword", "").strip().lower()
            if not keyword_text:
                continue

            # First, try to find an exact match in taxonomy
            taxonomy_term = KeywordTaxonomy.query.filter(
                func.lower(KeywordTaxonomy.term) == keyword_text
            ).first()

            # If no exact match, try partial matches
            if not taxonomy_term:
                taxonomy_term = KeywordTaxonomy.query.filter(
                    func.lower(KeywordTaxonomy.term).like(f"%{keyword_text}%")
                ).first()

            # If still no match, try synonyms
            if not taxonomy_term:
                synonym_match = (
                    db.session.query(KeywordTaxonomy)
                    .join(
                        KeywordSynonym, KeywordTaxonomy.id == KeywordSynonym.taxonomy_id
                    )
                    .filter(func.lower(KeywordSynonym.synonym) == keyword_text)
                    .first()
                )

                if synonym_match:
                    taxonomy_term = synonym_match

            # Add the keyword with taxonomy information if found
            keyword = LLMKeyword(
                llm_analysis_id=llm_analysis_id,
                keyword=keyword_data.get("keyword", ""),
                category=keyword_data.get("category", ""),
            )

            # Add taxonomy reference if found
            if taxonomy_term:
                keyword.taxonomy_id = taxonomy_term.id
                logger.info(
                    f"Mapped keyword '{keyword_text}' to taxonomy term '{taxonomy_term.term}'"
                )
            else:
                logger.info(f"No taxonomy match found for keyword '{keyword_text}'")

            # Set relevance score
            if "relevance_score" in keyword_data:
                keyword.relevance_score = keyword_data["relevance_score"]

            db.session.add(keyword)
            keywords_added += 1

        # Commit all keywords at once
        if keywords_added > 0:
            db.session.commit()
            logger.info(
                f"Added {keywords_added} keywords with taxonomy mapping for document {document_id}"
            )

        return True

    except Exception as e:
        logger.error(f"Error mapping keywords to taxonomy: {str(e)}")
        db.session.rollback()
        return False


def store_analysis_results(document_id: int, response: dict):
    """Store analysis results in database"""
    from src.catalog.services.llm_parser import LLMResponseParser

    try:
        parser = LLMResponseParser()

        # Store LLM Analysis
        llm_analysis_data = parser.parse_llm_analysis(response)
        llm_analysis = LLMAnalysis(document_id=document_id, **llm_analysis_data)
        db.session.add(llm_analysis)
        db.session.flush()  # Get the ID for keywords
        logger.info(f"Stored LLM analysis for document {document_id}")

        # Store Keywords
        keywords_data = parser.parse_keywords(response)
        for keyword_data in keywords_data:
            keyword = LLMKeyword(llm_analysis_id=llm_analysis.id, **keyword_data)
            db.session.add(keyword)
        logger.info(f"Stored {len(keywords_data)} keywords for document {document_id}")

        # Store Extracted Text
        extracted_text_data = parser.parse_extracted_text(response)
        extracted_text = ExtractedText(document_id=document_id, **extracted_text_data)
        db.session.add(extracted_text)
        logger.info(f"Stored extracted text for document {document_id}")

        # Store Design Elements
        design_data = parser.parse_design_elements(response)
        design_element = DesignElement(document_id=document_id, **design_data)
        db.session.add(design_element)
        logger.info(f"Stored design elements for document {document_id}")

        # Store Classification
        classification_data = parser.parse_classification(response)
        classification = Classification(document_id=document_id, **classification_data)
        db.session.add(classification)
        logger.info(f"Stored classification for document {document_id}")

        try:
            entity_data = parser.parse_entity_info(response)
            entity = Entity(document_id=document_id, **entity_data)
            db.session.add(entity)
            logger.info(f"Stored entity information for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to store entity information: {str(e)}")

        try:
            focus_data = parser.parse_communication_focus(response)
            focus = CommunicationFocus(document_id=document_id, **focus_data)
            db.session.add(focus)
            logger.info(f"Stored communication focus for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to store communication focus: {str(e)}")

        try:
            hierarchical_keywords = parser.parse_hierarchical_keywords(
                response, document_id
            )
            for keyword in hierarchical_keywords:
                db.session.add(keyword)
            logger.info(
                f"Stored {len(hierarchical_keywords)} hierarchical keywords for document {document_id}"
            )
        except Exception as e:
            logger.error(f"Error processing hierarchical keywords: {str(e)}")

        try:
            # Queue embeddings generation
            from tasks.embedding_tasks import generate_embeddings

            generate_embeddings.delay(document_id)
            logger.info(f"Queued embeddings generation for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to queue embeddings generation: {str(e)}")

        # Commit all changes to database
        db.session.commit()
        logger.info(
            f"Successfully stored all analysis results for document {document_id}"
        )

        return True

    except Exception as e:
        logger.error(f"Error storing analysis results: {str(e)}")
        db.session.rollback()
        raise


@celery_app.task(name="tasks.recover_pending_documents")
def recover_pending_documents():
    """Identify and recover documents stuck in PENDING state"""
    from src.catalog import create_app

    app = create_app()

    with app.app_context():
        # Get documents stuck in PENDING state for more than 1 hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        stuck_documents = (
            Document.query.filter_by(status="PENDING")
            .filter(Document.upload_date < one_hour_ago)
            .all()
        )

        logger.info(f"Found {len(stuck_documents)} documents stuck in PENDING state")
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
                    logger.error(f"Document file not found in storage: {doc.filename}")
                    doc.status = "FAILED"
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error recovering document {doc.id}: {str(e)}")

        return f"Processed {len(stuck_documents)} stuck documents"


@celery_app.task(name="tasks.process_batch_uploads")
def process_batch_uploads():
    """
    Periodically checks for documents with 'BATCH_PENDING' status
    and queues them for individual processing.
    """
    from src.catalog import create_app

    app = create_app()
    with app.app_context():
        logger.info("Running process_batch_uploads task...")
        batch_pending_docs = Document.query.filter_by(status="BATCH_PENDING").all()

        if not batch_pending_docs:
            logger.info("No documents found in BATCH_PENDING state.")
            return "No BATCH_PENDING documents found."

        logger.info(
            f"Found {len(batch_pending_docs)} documents in BATCH_PENDING state."
        )
        storage = MinIOStorage()  # Initialize storage service

        queued_count = 0
        for doc in batch_pending_docs:
            try:
                logger.info(
                    f"Processing document ID: {doc.id}, Filename: {doc.filename} from BATCH_PENDING."
                )

                # Construct minio_path (assuming it's not stored directly on the model)
                # This needs to align with how `process_document` expects it.
                # Typically, it's bucket_name/filename.
                minio_path = f"{storage.bucket}/{doc.filename}"

                # Check if file actually exists in MinIO before queueing
                # This is a good practice to avoid queueing tasks for non-existent files
                try:
                    storage.client.stat_object(storage.bucket, doc.filename)
                    file_exists_in_minio = True
                except Exception as minio_exc:
                    logger.error(
                        f"File {doc.filename} (ID: {doc.id}) not found in MinIO. Error: {minio_exc}. Marking as FAILED."
                    )
                    file_exists_in_minio = False
                    doc.status = DOCUMENT_STATUSES["FAILED"]
                    db.session.commit()
                    continue  # Skip to the next document

                if file_exists_in_minio:
                    # Update status to PENDING before queueing to avoid re-picking by this task
                    doc.status = DOCUMENT_STATUSES["PENDING"]
                    db.session.commit()
                    logger.info(f"Updated document ID: {doc.id} status to PENDING.")

                    # Queue the main processing task
                    process_document.delay(doc.filename, minio_path, doc.id)
                    logger.info(
                        f"Queued document ID: {doc.id} ({doc.filename}) for processing."
                    )
                    queued_count += 1

            except Exception as e:
                logger.error(
                    f"Error processing document ID: {doc.id} from BATCH_PENDING state: {str(e)}",
                    exc_info=True,
                )
                # Optionally, set status to FAILED here if a general error occurs during this stage
                try:
                    doc.status = DOCUMENT_STATUSES[
                        "FAILED"
                    ]  # Mark as FAILED if any error during batch handling
                    db.session.commit()
                except Exception as db_err:
                    logger.error(
                        f"Failed to update status to FAILED for doc ID {doc.id} after error: {db_err}",
                        exc_info=True,
                    )
                    db.session.rollback()  # Rollback this specific doc's status update attempt

        return f"Processed {len(batch_pending_docs)} BATCH_PENDING documents. Queued {queued_count} for processing."
