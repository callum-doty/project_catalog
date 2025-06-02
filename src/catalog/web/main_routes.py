# app/routes/main_routes.py

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    flash,
    redirect,
    url_for,
    jsonify,
    current_app,
)
from werkzeug.utils import secure_filename
import os
import logging
import src.catalog
from sqlalchemy.orm import joinedload
from datetime import datetime
from src.catalog.services.storage_service import MinIOStorage
from src.catalog import db
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
)
from src.catalog.models import KeywordTaxonomy, KeywordSynonym
from sqlalchemy import or_, func, desc, case, extract
from src.catalog.services.preview_service import PreviewService
from src.catalog.services.dropbox_service import DropboxService
from flask_wtf.csrf import generate_csrf
from src.catalog import csrf
import time
from datetime import datetime, timedelta
from sqlalchemy.sql.expression import text
import statistics
from statistics import mean
from src.catalog.tasks.document_tasks import process_document
from src.catalog.tasks.dropbox_tasks import sync_dropbox
from functools import wraps
from src.catalog import cache
from src.catalog.services.document_service import (
    get_document_count,
    get_document_counts_by_status,
)
from flask_caching import Cache
from src.catalog.utils import search_with_timeout, document_has_column, monitor_query
from src.catalog.utils.query_builders import get_failed_documents_query
from src.catalog.utils.query_builders import (
    get_document_statistics,
    build_document_with_relationships_query,
    apply_sorting,
    get_stuck_documents_query,
)
from src.catalog.constants import CACHE_TIMEOUTS
from flask import send_file  # Added for sending image file
import io  # Added for BytesIO


main_routes = Blueprint("main_routes", __name__)
logger = logging.getLogger(__name__)
storage = MinIOStorage()
preview_service = PreviewService()
search_times = []
MAX_SEARCH_TIMES = 100


def check_password(password):
    """Check if the password is valid"""
    correct_password = os.environ.get("SITE_PASSWORD", "your_secure_password")
    return password == correct_password


def password_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if user is already authenticated
        if session.get("authenticated"):
            return f(*args, **kwargs)

        # Check if password was submitted
        if request.method == "POST" and "password" in request.form:
            if check_password(request.form["password"]):
                session["authenticated"] = True
                return redirect(url_for("main_routes.search_documents"))
            else:
                return render_template("password.html", error="Incorrect password")

        # Show password form
        return render_template("password.html")

    return decorated


@main_routes.before_request
def protect_blueprint():
    # Add debug logging
    current_app.logger.info(
        f"Accessing route: {request.endpoint} with method {request.method}"
    )

    # Skip authentication for certain endpoints
    if request.endpoint in ["main_routes.static", "main_routes.password_check"]:
        return None

    # Check if authenticated
    if not session.get("authenticated"):
        # For AJAX requests, return a JSON error instead of redirecting
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return (
                jsonify(
                    {
                        "error": "Authentication required",
                        "redirect": url_for(
                            "main_routes.password_check", next=request.url
                        ),
                    }
                ),
                401,
            )

        # Preserve the requested URL as 'next' parameter for regular requests
        next_url = request.url
        return redirect(url_for("main_routes.password_check", next=next_url))

    return None


# Add a route to handle password submission


@main_routes.route("/password-check", methods=["GET", "POST"])
def password_check():
    # For debugging - log the request method
    current_app.logger.info(f"Password check accessed with method: {request.method}")

    # Handle POST requests directly
    if request.method == "POST":
        if "password" in request.form:
            if check_password(request.form["password"]):
                session["authenticated"] = True
                # Use relative URL for redirection
                next_url = request.args.get("next") or url_for(
                    "main_routes.search_documents"
                )
                return redirect(next_url)
            else:
                return render_template("password.html", error="Incorrect password")

    # For GET requests, show the password form
    return render_template("password.html")


# end password section


def get_celery_task(task_name):
    """Lazy import of celery tasks to avoid circular imports"""
    if task_name == "process_document":
        return process_document
    elif task_name == "sync_dropbox":
        from src.catalog.tasks.dropbox_tasks import sync_dropbox

        return sync_dropbox


def record_search_time(response_time):
    """Record a search response time and maintain the list size"""
    global search_times
    search_times.append(response_time)
    # Keep only the most recent times
    if len(search_times) > MAX_SEARCH_TIMES:
        search_times = search_times[-MAX_SEARCH_TIMES:]


@main_routes.route("/")
def index():
    # Redirect to the search page instead of showing the index page
    return redirect(url_for("main_routes.search_documents"))


@main_routes.route("/admin", defaults={"path": ""})
@main_routes.route("/admin/<path:path>")
def serve_admin(path):
    """Serve the admin React app for all admin routes"""
    # This will serve your React app's index.html
    return render_template("admin/index.html")


@main_routes.route("/dashboard")
@monitor_query
def dashboard():
    document_counts = get_document_counts_by_status()
    return render_template("dashboard.html", counts=document_counts)


@main_routes.route("/home")
def home():
    try:
        # Get recent documents with relationships, sorted by upload date
        documents_query = build_document_with_relationships_query()
        documents_query = apply_sorting(documents_query, "upload_date", "desc")
        documents = documents_query.limit(10).all()

        formatted_docs = []

        for doc in documents:
            # Get preview if possible
            preview = None
            try:
                preview = preview_service.get_preview(doc.filename)
            except Exception as e:
                current_app.logger.error(
                    f"Preview generation failed for {doc.filename}: {str(e)}"
                )

            # Format document data
            formatted_doc = {
                "id": doc.id,
                "filename": doc.filename,
                "upload_date": doc.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                "status": doc.status,
                "preview": preview,
                "summary": (
                    doc.llm_analysis.summary_description if doc.llm_analysis else ""
                ),
                "keywords": [],
            }

            # Add keywords if they exist
            if doc.llm_analysis and doc.llm_analysis.keywords:
                formatted_doc["keywords"] = [
                    {"text": kw.keyword, "category": kw.category}
                    for kw in doc.llm_analysis.keywords
                ]

            formatted_docs.append(formatted_doc)

        return render_template("pages/index.html", documents=formatted_docs)
    except Exception as e:
        current_app.logger.error(f"Error fetching documents: {str(e)}")
        return render_template("pages/index.html", documents=[])


@main_routes.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("main_routes.search_documents"))

    file = request.files["file"]
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("main_routes.search_documents"))

    document = None  # Initialize document to None
    temp_path = None  # Initialize temp_path

    try:
        filename = secure_filename(file.filename)
        temp_path = os.path.join("/tmp", filename)
        file.save(temp_path)

        # Ensure file was saved before proceeding
        if not os.path.exists(temp_path):
            raise IOError(f"Failed to save temporary file: {temp_path}")

        file_size = os.path.getsize(temp_path)

        # Create document record FIRST
        document = Document(
            filename=filename,
            upload_date=datetime.utcnow(),
            file_size=file_size,
            status="PENDING",  # Start as PENDING
            page_count=0,
        )
        db.session.add(document)
        db.session.commit()

        # Now we have a document.id to use
        minio_path = storage.upload_file(temp_path, filename)
        current_app.logger.info(
            f"Successfully uploaded {filename} to MinIO at {minio_path}"
        )

        # Queue ONLY the main document processing task
        try:
            current_app.logger.info(
                f"Queuing document {document.id} ({filename}) via process_document task"
            )

            from src.catalog.tasks.celery_app import celery_app

            # Pass all necessary arguments: filename, minio_path, document.id
            task = celery_app.send_task(
                "process_document", args=[filename, minio_path, document.id]
            )

            current_app.logger.info(
                f"Main processing task queued with ID: {task.id} for document ID {document.id}"
            )

        except Exception as e:
            current_app.logger.error(
                f"Failed to queue process_document task for document {document.id if document else 'N/A'}: {str(e)}",
                exc_info=True,
            )

            if document:
                document.status = "FAILED"
                db.session.commit()
            flash("Error starting document processing.", "error")

            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            return redirect(url_for("main_routes.search_documents"))

        # Remove temp file *after* successful queuing
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        flash("File uploaded successfully. Processing initiated.", "success")
        return redirect(url_for("main_routes.search_documents"))

    except Exception as e:
        current_app.logger.error(
            f"Upload error for file '{file.filename if file else 'N/A'}': {str(e)}",
            exc_info=True,
        )
        # Rollback DB changes if document creation started but failed
        db.session.rollback()
        # Update status to FAILED if document object exists
        if document and document.id:
            try:
                # Re-fetch the document within a new session scope if needed, or just update status
                doc_to_fail = Document.query.get(document.id)
                if doc_to_fail:
                    doc_to_fail.status = "FAILED"
                    db.session.commit()
            except Exception as db_err:
                current_app.logger.error(
                    f"Failed to mark document as FAILED after upload error: {db_err}",
                    exc_info=True,
                )
                db.session.rollback()

        flash(f"Error uploading file: {str(e)}", "error")
        # Clean up temp file if it exists
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as os_err:
                current_app.logger.error(
                    f"Error removing temp file during cleanup: {os_err}", exc_info=True
                )

        return redirect(url_for("search_routes.search_documents"))


@main_routes.route("/search")
def search_documents():
    """Redirect to the search route"""
    return redirect(url_for("search_routes.search_documents", **request.args))


@cache.memoize(timeout=300)
def get_document_hierarchical_keywords(document_id):
    """Get hierarchical keywords for a document"""
    try:
        keywords = (
            db.session.query(LLMKeyword, KeywordTaxonomy)
            .join(KeywordTaxonomy, LLMKeyword.taxonomy_id == KeywordTaxonomy.id)
            .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
            .filter(LLMAnalysis.document_id == document_id)
            .all()
        )

        result = []
        for llm_kw, taxonomy in keywords:
            result.append(
                {
                    "id": taxonomy.id,
                    "term": taxonomy.term,
                    "primary_category": taxonomy.primary_category,
                    "subcategory": taxonomy.subcategory,
                    "relevance_score": llm_kw.relevance_score,
                }
            )

        return result
    except Exception as e:
        logger.error(f"Error getting hierarchical keywords: {str(e)}")
        return []


@cache.memoize(timeout=300)
def generate_taxonomy_facets(selected_primary=None, selected_subcategory=None):
    """Generate taxonomy facets for sidebar filtering"""
    try:
        logger = current_app.logger
        # Create a CTE for documents that have keywords
        docs_with_keywords = (
            db.session.query(
                LLMKeyword.taxonomy_id,
                func.count(LLMAnalysis.document_id.distinct()).label("doc_count"),
            )
            .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
            .group_by(LLMKeyword.taxonomy_id)
            .cte("docs_with_keywords")
        )

        # Get primary categories with counts
        primary_categories = (
            db.session.query(
                KeywordTaxonomy.primary_category,
                func.sum(docs_with_keywords.c.doc_count).label("count"),
            )
            .join(
                docs_with_keywords,
                KeywordTaxonomy.id == docs_with_keywords.c.taxonomy_id,
            )
            .group_by(KeywordTaxonomy.primary_category)
            .order_by(KeywordTaxonomy.primary_category)
            .all()
        )

        # If a primary category is selected, get subcategories
        subcategories = []
        if selected_primary:
            subcategories = (
                db.session.query(
                    KeywordTaxonomy.subcategory,
                    func.count(KeywordTaxonomy.id.distinct()).label("count"),
                )
                .filter(KeywordTaxonomy.primary_category == selected_primary)
                .join(LLMKeyword, KeywordTaxonomy.id == LLMKeyword.taxonomy_id)
                .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
                .group_by(KeywordTaxonomy.subcategory)
                .order_by(KeywordTaxonomy.subcategory)
                .all()
            )

        # Format results
        result = {
            "primary_categories": [
                {"name": cat, "count": count, "selected": cat == selected_primary}
                for cat, count in primary_categories
            ],
            "subcategories": (
                [
                    {
                        "name": subcat,
                        "count": count,
                        "selected": subcat == selected_subcategory,
                    }
                    for subcat, count in subcategories
                ]
                if selected_primary
                else []
            ),
        }

        return result
    except Exception as e:
        logger.error(f"Error generating taxonomy facets: {str(e)}")
        return {"primary_categories": [], "subcategories": []}


@main_routes.route("/api/reprocess-document/<int:document_id>", methods=["POST"])
def reprocess_document(document_id):
    """API endpoint to reprocess a specific document by ID"""
    try:
        from src.catalog.tasks.recovery_tasks import reprocess_document

        # Start the task
        task = reprocess_document.delay(document_id)

        return jsonify(
            {
                "status": "success",
                "message": f"Started reprocessing document ID: {document_id}",
                "task_id": task.id,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error reprocessing document {document_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@main_routes.route("/recovery-dashboard")
def recovery_dashboard():
    """Display failed documents for recovery"""
    try:

        failed_documents = get_failed_documents_query().all()

        # Prepare data for template
        documents_data = []

        for doc in failed_documents:
            preview = None
            try:
                preview = preview_service.get_preview(doc.filename)
            except Exception as e:
                current_app.logger.error(
                    f"Preview generation failed for {doc.filename}: {str(e)}"
                )

            documents_data.append(
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "upload_date": doc.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "file_size": f"{(doc.file_size/1024):.2f} KB",
                    "preview": preview,
                    "status": doc.status,
                }
            )

        return render_template("pages/recovery.html", documents=documents_data)

    except Exception as e:
        current_app.logger.error(
            f"Error in recovery dashboard: {str(e)}", exc_info=True
        )
        flash(f"Error loading recovery dashboard: {str(e)}", "error")
        return render_template("pages/recovery.html", documents=[])


@main_routes.route("/admin/recover-pending")
def recover_pending():
    """Display pending documents that might be stuck for recovery"""
    try:
        # Use query builder for stuck documents (processing for more than 1 hour)
        # We'll explicitly look for PROCESSING status
        stuck_documents = get_stuck_documents_query(hours=1).all()

        # Log the number of stuck documents
        current_app.logger.info(f"Found {len(stuck_documents)} stuck documents")

        # Prepare data for template
        documents_data = []

        for doc in stuck_documents:
            # Calculate time since upload
            time_since_upload = datetime.utcnow() - doc.upload_date
            hours_pending = time_since_upload.total_seconds() / 3600

            # Get preview with better error handling
            preview = None
            try:  # This try was missing its except/finally, and filename was not defined
                preview_data_from_service = preview_service.get_preview(
                    doc.filename
                )  # Use doc.filename

                # Detailed logging for debugging the signal
                current_app.logger.info(
                    f"Preview data from service for '{doc.filename}': '{preview_data_from_service}' (type: {type(preview_data_from_service)})"
                )
                # Explicitly compare with the known signal string
                expected_signal = "fallback_to_direct_url"
                is_fallback_signal = preview_data_from_service == expected_signal
                current_app.logger.info(
                    f"Is it the fallback signal ('{expected_signal}')? {is_fallback_signal}"
                )

                if is_fallback_signal:
                    current_app.logger.info(
                        f"Fallback signal detected for '{doc.filename}'. Getting presigned URL."
                    )
                    direct_url = storage.get_presigned_url(doc.filename)
                    if direct_url:
                        current_app.logger.info(
                            f"Successfully got presigned URL for '{doc.filename}': {direct_url}"
                        )
                        # This part seems to be from a different route /api/preview/, not recover_pending view
                        # For recover_pending, we just need the preview content for the template
                        preview = {
                            "status": "fallback_redirect",
                            "url": direct_url,
                            "filename": doc.filename,
                        }
                    else:  # Failed to get presigned URL
                        current_app.logger.error(
                            f"Could not get presigned URL for '{doc.filename}' after fallback signal."
                        )
                        preview = {
                            "status": "error",
                            "message": "Preview generation signaled fallback, but failed to get direct URL.",
                        }
                else:
                    # Not the fallback signal, so preview_data_from_service is actual preview content
                    current_app.logger.info(
                        f"Not the fallback signal for '{doc.filename}'. Treating as preview content. Preview data starts with: '{str(preview_data_from_service)[:100]}...'"
                    )
                    preview = {
                        "status": "success",
                        "preview": preview_data_from_service,
                    }
            except Exception as preview_exc:
                current_app.logger.error(
                    f"Preview generation failed for {doc.filename} in recover_pending: {str(preview_exc)}"
                )
                preview = None  # Ensure preview is None if an error occurs

            documents_data.append(
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "upload_date": doc.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "file_size": (
                        f"{(doc.file_size/1024):.2f} KB" if doc.file_size else "N/A"
                    ),
                    "status": doc.status,
                    "hours_pending": f"{hours_pending:.2f}",
                    "preview": preview,  # Use the fetched preview data
                }
            )

        return render_template("pages/recover_pending.html", documents=documents_data)

    except Exception as e:  # This is the except for the main try block of the function
        current_app.logger.error(f"Error in recover pending: {str(e)}", exc_info=True)
        flash(f"Error loading recover pending dashboard: {str(e)}", "error")
        return render_template("pages/recover_pending.html", documents=[])


@main_routes.route("/api/recover-document/<int:document_id>", methods=["POST"])
def recover_document(document_id):
    """Trigger reprocessing of a stuck document"""
    try:
        document = Document.query.get_or_404(document_id)
        current_app.logger.info(
            f"Attempting to recover document {document_id}: {document.filename}"
        )

        if document.status not in ["FAILED", "PENDING", "PROCESSING"]:
            current_app.logger.warning(
                f"Document {document_id} not in recoverable state: {document.status}"
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Document is not in a recoverable state: {document.status}",
                    }
                ),
                400,
            )

        # Verify file exists in storage
        file_exists = False
        try:
            storage.client.stat_object(storage.bucket, document.filename)
            file_exists = True
        except Exception as e:
            current_app.logger.error(f"File not found in storage: {str(e)}")

        if not file_exists:
            current_app.logger.error(
                f"Cannot recover document {document_id}: file {document.filename} not found in storage"
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Document file not found in storage",
                    }
                ),
                400,
            )

        # Import recovery task
        from src.catalog.tasks.recovery_tasks import reprocess_document

        # Reset document status to PENDING
        document.status = "PENDING"
        db.session.commit()
        current_app.logger.info(f"Reset document {document_id} status to PENDING")

        # Get the file from MinIO storage
        minio_path = f"{storage.bucket}/{document.filename}"

        # Queue reprocessing task
        try:
            task = reprocess_document.delay(document.filename, minio_path, document.id)
            current_app.logger.info(
                f"Queued document {document_id} for reprocessing with task ID: {task.id}"
            )
        except Exception as task_error:
            current_app.logger.error(
                f"Failed to queue reprocessing task: {str(task_error)}", exc_info=True
            )
            # Reset status to original if task queueing fails
            document.status = "PROCESSING"
            db.session.commit()
            raise task_error

        return jsonify(
            {
                "status": "success",
                "message": f"Document recovery initiated for {document.filename}",
                "task_id": task.id,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error recovering document: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@main_routes.route("/api/recovery-status/<int:document_id>", methods=["GET"])
def recovery_status(document_id):
    """Get current status of a document"""
    try:
        document = Document.query.get_or_404(document_id)

        # Add more detailed information
        processing_time = None
        if document.status == "COMPLETED":
            processing_time = document.processing_time

        return jsonify(
            {
                "status": "success",
                "document_status": document.status,
                "id": document.id,
                "filename": document.filename,
                "processing_time": processing_time,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting recovery status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@main_routes.route("/api/execute-sync", methods=["POST"])
def execute_sync():
    """Directly execute Dropbox sync (not just queue it)"""
    try:
        current_app.logger.info("Directly executing Dropbox sync")

        # Import the sync task function
        from src.catalog.tasks.dropbox_tasks import sync_dropbox

        # Call the function directly (not as a task)
        result = sync_dropbox()

        return jsonify(
            {"status": "success", "message": "Sync executed directly", "result": result}
        )
    except Exception as e:
        current_app.logger.error(f"Error executing sync: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@main_routes.route("/api/cache-stats")
def cache_stats():
    """Return basic cache statistics"""
    stats = {
        "cache_type": src.config["CACHE_TYPE"],
        "default_timeout": src.catalog.config["CACHE_DEFAULT_TIMEOUT"],
    }

    # Add Redis-specific stats if using Redis
    if src.catalog.config["CACHE_TYPE"] == "redis":
        try:
            import redis

            redis_client = redis.from_url(src.catalog.config["CACHE_REDIS_URL"])
            info = redis_client.info()
            stats.update(
                {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "N/A"),
                    "hit_rate": info.get("keyspace_hits", 0)
                    / (
                        info.get("keyspace_hits", 0)
                        + info.get("keyspace_misses", 0)
                        + 0.001
                    ),
                    "total_keys": sum(
                        db.get("keys", 0) for db in info.get("keyspace", {}).values()
                    ),
                }
            )
        except Exception as e:
            stats["error"] = str(e)

    return jsonify(stats)


@main_routes.route("/api/preview-status/<path:filename>")
def preview_status(filename):
    """Check if a preview is available in cache"""
    cache_key = f"preview:{filename}"
    preview_data = cache.get(cache_key)

    if preview_data:
        return jsonify({"status": "available", "preview_url": preview_data})
    else:
        # Check if still in progress
        in_progress = cache.get(f"preview_in_progress:{filename}")
        return jsonify({"status": "pending" if in_progress else "not_found"})


def get_document_hierarchical_keywords_bulk(document_ids):
    """Efficiently get hierarchical keywords for multiple documents at once"""
    try:
        keywords_data = (
            db.session.query(
                LLMKeyword.document_id,
                KeywordTaxonomy.id,
                KeywordTaxonomy.term,
                KeywordTaxonomy.primary_category,
                KeywordTaxonomy.subcategory,
                LLMKeyword.relevance_score,
            )
            .join(KeywordTaxonomy, LLMKeyword.taxonomy_id == KeywordTaxonomy.id)
            .filter(LLMKeyword.document_id.in_(document_ids))
            .all()
        )

        results = {doc_id: [] for doc_id in document_ids}

        for doc_id, tax_id, term, primary_cat, subcat, score in keywords_data:
            results[doc_id].append(
                {
                    "id": tax_id,
                    "term": term,
                    "primary_category": primary_cat,
                    "subcategory": subcat,
                    "relevance_score": score,
                }
            )

        return results
    except Exception as e:
        current_app.logger.error(f"Error getting hierarchical keywords: {str(e)}")
        return {doc_id: [] for doc_id in document_ids}


@main_routes.route("/api/documents")
def api_documents():
    last_id = request.args.get("last_id", type=int)
    limit = request.args.get("limit", 20, type=int)

    query = Document.query.order_by(Document.id)

    if last_id:
        # Keyset pagination - much more efficient for large tables
        query = query.filter(Document.id > last_id)

    documents = query.limit(limit).all()

    return jsonify(
        {
            "documents": [doc.to_dict() for doc in documents],
            "has_more": len(documents) == limit,
            "last_id": documents[-1].id if documents else None,
        }
    )


# Add to app/routes/main_routes.py


@main_routes.route("/api/preview/<path:filename>")
def get_document_preview(filename):
    """API endpoint for fetching document previews based on database status."""
    try:
        # Attempt to find the document by filename
        document = Document.query.filter_by(filename=filename).first()

        if document:
            current_app.logger.info(
                f"Document ID {document.id} found for filename {filename}. Preview status: {document.preview_status}, S3 Key: {document.s3_preview_key}"
            )
            if document.preview_status == "SUCCESS" and document.s3_preview_key:
                preview_bucket_name = current_app.config.get(
                    "S3_PREVIEW_BUCKET", storage.bucket
                )  # Fallback to main bucket if not set
                try:
                    # Generate presigned URL for the actual preview file
                    preview_url = storage.get_presigned_url(
                        document.s3_preview_key,  # Positional argument for object_name
                        bucket_name=preview_bucket_name,
                    )
                    if preview_url:
                        current_app.logger.info(
                            f"Successfully generated presigned URL for preview key '{document.s3_preview_key}' in bucket '{preview_bucket_name}' for document {document.id}"
                        )
                        return jsonify(
                            {
                                "status": "success",
                                "url": preview_url,
                                "filename": filename,
                                "preview_type": "s3_generated",
                            }
                        )
                    else:
                        current_app.logger.error(
                            f"Failed to generate presigned URL for preview key '{document.s3_preview_key}' for document {document.id}. Falling back."
                        )
                        # Fall through to fallback logic if URL generation fails for some reason
                except Exception as presign_err:
                    current_app.logger.error(
                        f"Error generating presigned URL for preview key '{document.s3_preview_key}': {presign_err}",
                        exc_info=True,
                    )
                    # Fall through to fallback logic

            elif document.preview_status == "PENDING":
                current_app.logger.info(
                    f"Preview for document {document.id} ({filename}) is PENDING."
                )
                return (
                    jsonify(
                        {
                            "status": "pending",
                            "message": "Preview generation is currently in progress.",
                            "filename": filename,
                        }
                    ),
                    202,
                )  # Accepted

            # If status is FAILED, or SUCCESS but no key, or any other status, or document fields not yet populated
            current_app.logger.info(
                f"Preview for document {document.id} ({filename}) not available or failed. Status: {document.preview_status}. Proceeding to fallback."
            )

        else:
            current_app.logger.info(
                f"Document with filename '{filename}' not found in database. Proceeding to fallback for original document."
            )

        # Fallback logic: try to serve the original document or a placeholder
        # This part can reuse some of the original logic if PreviewService.get_preview() handles placeholders
        # For simplicity, let's directly try to get a presigned URL for the original document.
        current_app.logger.info(
            f"Attempting fallback: generating presigned URL for original document '{filename}' in bucket '{storage.bucket}'."
        )
        try:
            original_doc_url = storage.get_presigned_url(
                filename,
                bucket_name=storage.bucket,  # Positional argument for object_name
            )  # Assuming default bucket for originals
            if original_doc_url:
                current_app.logger.info(
                    f"Fallback: Successfully generated presigned URL for original document '{filename}': {original_doc_url}"
                )
                return jsonify(
                    {
                        "status": "fallback_redirect",
                        "url": original_doc_url,
                        "filename": filename,
                    }
                )
            else:
                current_app.logger.error(
                    f"Fallback: Failed to generate presigned URL for original document '{filename}'."
                )
                # If even the original can't be served, return a more definitive error.
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Preview not available and original document URL could not be generated.",
                        }
                    ),
                    404,
                )
        except Exception as fallback_presign_err:
            current_app.logger.error(
                f"Fallback: Error generating presigned URL for original document '{filename}': {fallback_presign_err}",
                exc_info=True,
            )
            return (
                jsonify(
                    {"status": "error", "message": "Error during fallback attempt."}
                ),
                500,
            )

    except Exception as e:
        current_app.logger.error(
            f"General Preview API error for {filename}: {str(e)}", exc_info=True
        )
        return (
            jsonify({"status": "error", "message": "An unexpected error occurred."}),
            500,
        )


@main_routes.route("/api/sync-status")
def sync_status():
    """API endpoint to check sync status"""
    try:
        # Check if DropboxService is available
        try:
            from catalog.services.dropbox_service import DropboxService

            dropbox_service = DropboxService()
            status = dropbox_service.get_sync_status()
        except ImportError:
            # If Dropbox service not available, return dummy data
            status = {
                "dropbox_connected": False,
                "last_sync_time": None,
                "last_status": "NOT_CONFIGURED",
                "message": "Dropbox integration not configured",
            }

        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Error checking sync status: {str(e)}")
        return jsonify({"error": str(e), "dropbox_connected": False}), 500


@main_routes.route("/document/<path:filename>")
def view_document(filename):
    """Serve the document file from storage for viewing in the browser"""
    try:
        # Get the file data from MinIO
        from src.catalog.services.storage_service import MinIOStorage

        storage = MinIOStorage()

        # Log the request
        current_app.logger.info(f"Fetching document file: {filename}")

        # Get the file data
        file_data = storage.get_file(filename)

        if not file_data:
            current_app.logger.error(f"Document file not found: {filename}")
            flash("Document not found", "error")
            return redirect(url_for("main_routes.search_documents"))

        # Get file extension and set correct mime type
        ext = os.path.splitext(filename.lower())[1]
        mime_type = "application/pdf"
        if ext in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif ext == ".png":
            mime_type = "image/png"

        # Return the file with appropriate content type
        response = current_app.response_class(file_data, mimetype=mime_type)

        # Set content disposition to inline for in-browser viewing
        response.headers.set(
            "Content-Disposition", f'inline; filename="{os.path.basename(filename)}"'
        )

        return response

    except Exception as e:
        current_app.logger.error(f"Error fetching document: {str(e)}")
        flash(f"Error viewing document: {str(e)}", "error")
        return redirect(url_for("main_routes.search_documents"))


@main_routes.route("/api/admin/quality-metrics")
def get_quality_metrics():
    """API endpoint to get quality metrics for document processing"""
    try:
        # Create evaluation service instance
        from src.catalog.services.evaluation_service import EvaluationService

        evaluation_service = EvaluationService()

        # Get days parameter with default value
        days = request.args.get("days", default=30, type=int)

        # Get metrics data
        metrics = evaluation_service.get_quality_metrics(days=days)

        return jsonify({"success": True, "data": metrics})
    except Exception as e:
        current_app.logger.error(
            f"Error getting quality metrics: {str(e)}", exc_info=True
        )
        return jsonify({"success": False, "error": str(e)}), 500


@main_routes.route("/api/placeholder-image")
def get_placeholder_image_route():
    """API endpoint to serve the placeholder image."""
    try:
        # The 'storage' instance is MinIOStorage, which has _get_placeholder_image
        image_data = storage._get_placeholder_image()
        if image_data:
            return send_file(
                io.BytesIO(image_data),
                mimetype="image/png",
                as_attachment=False,
                download_name="placeholder.png",
            )
        else:
            # This case should ideally not happen if _get_placeholder_image always returns something
            current_app.logger.error("Placeholder image data was empty.")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Failed to generate placeholder image",
                    }
                ),
                500,
            )
    except Exception as e:
        current_app.logger.error(
            f"Error serving placeholder image: {str(e)}", exc_info=True
        )
        return (
            jsonify(
                {"status": "error", "message": "Server error generating placeholder"}
            ),
            500,
        )


@main_routes.route("/api/generate-scorecards", methods=["POST"])
def generate_missing_scorecards():
    """Generate evaluation scorecards for all documents that don't have them"""
    try:
        # Get documents with COMPLETED status
        from src.catalog.models import Document, DocumentScorecard
        from src.catalog.services.evaluation_service import EvaluationService

        # Find documents that don't have scorecards
        documents_without_scorecards = (
            db.session.query(Document)
            .filter(
                Document.status == "COMPLETED",
                ~Document.id.in_(db.session.query(DocumentScorecard.document_id)),
            )
            .all()
        )

        current_app.logger.info(
            f"Found {len(documents_without_scorecards)} documents without scorecards"
        )

        # Create evaluation service
        eval_service = EvaluationService()

        # Create scorecards for each document
        created_count = 0
        for doc in documents_without_scorecards:
            try:
                # Evaluate each batch
                batch1_success, _ = eval_service.evaluate_batch1(doc.id)
                batch2_success, _ = eval_service.evaluate_batch2(doc.id)
                batch3_success, _ = eval_service.evaluate_batch3(doc.id)

                created_count += 1
                current_app.logger.info(f"Created scorecard for document {doc.id}")
            except Exception as e:
                current_app.logger.error(
                    f"Error creating scorecard for document {doc.id}: {str(e)}"
                )

        return jsonify(
            {
                "success": True,
                "message": f"Created {created_count} scorecards out of {len(documents_without_scorecards)} documents",
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error generating scorecards: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@main_routes.route("/api/search-feedback", methods=["POST"])
def submit_search_feedback():
    """API endpoint to submit search result feedback"""
    try:
        # Import SearchFeedback model directly here
        from src.catalog.models import SearchFeedback
        from datetime import datetime

        # Debug logging
        current_app.logger.info(f"Received feedback data: {request.json}")

        # Validate required fields
        if not request.json:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        data = request.json

        # Check required fields
        if "document_id" not in data or not data["document_id"]:
            return jsonify({"status": "error", "message": "Missing document ID"}), 400

        if "feedback_type" not in data or not data["feedback_type"]:
            return jsonify({"status": "error", "message": "Missing feedback type"}), 400

        # Create feedback record directly
        feedback = SearchFeedback(
            search_query=data.get("search_query", ""),
            document_id=data["document_id"],
            feedback_type=data["feedback_type"],
            user_comment=data.get("comment", ""),
            feedback_date=datetime.utcnow(),
        )

        # Log the feedback object before adding to session
        current_app.logger.info(
            f"Creating feedback: {feedback.document_id} - {feedback.feedback_type}"
        )

        db.session.add(feedback)
        db.session.commit()

        current_app.logger.info(
            f"Feedback recorded successfully with ID: {feedback.id}"
        )

        return jsonify(
            {
                "status": "success",
                "message": "Feedback recorded successfully",
                "feedback_id": feedback.id,
            }
        )

    except Exception as e:
        current_app.logger.error(
            f"Error recording search feedback: {str(e)}", exc_info=True
        )
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500


@main_routes.route("/api/admin/feedback", methods=["GET"])
def get_search_feedback():
    """API endpoint to retrieve search feedback data for admin dashboard"""
    try:
        # Import necessary models
        from src.catalog.models import SearchFeedback, Document

        # Get pagination parameters
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        # Get optional filter parameters
        feedback_type = request.args.get("type", None)
        start_date = request.args.get("start_date", None)
        end_date = request.args.get("end_date", None)

        # Build base query with join to get document filenames
        query = db.session.query(SearchFeedback, Document.filename).outerjoin(
            Document, SearchFeedback.document_id == Document.id
        )

        # Apply filters if provided
        if feedback_type:
            query = query.filter(SearchFeedback.feedback_type == feedback_type)

        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(SearchFeedback.feedback_date >= start_datetime)
            except ValueError:
                # Invalid date format, ignore this filter
                pass

        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                # Add one day to include the end date fully
                end_datetime = end_datetime + timedelta(days=1)
                query = query.filter(SearchFeedback.feedback_date < end_datetime)
            except ValueError:
                # Invalid date format, ignore this filter
                pass

        # Order by most recent first
        query = query.order_by(SearchFeedback.feedback_date.desc())

        # Get total count for pagination
        total_count = query.count()

        # Apply pagination
        paginated_query = query.offset((page - 1) * per_page).limit(per_page)

        # Execute query
        results = paginated_query.all()

        # Format the results
        feedback_list = []
        for feedback, filename in results:
            feedback_list.append(
                {
                    "id": feedback.id,
                    "document_id": feedback.document_id,
                    "filename": filename or "Unknown Document",
                    "search_query": feedback.search_query or "",
                    "feedback_type": feedback.feedback_type,
                    "user_comment": feedback.user_comment or "",
                    "feedback_date": (
                        feedback.feedback_date.strftime("%Y-%m-%d %H:%M:%S")
                        if feedback.feedback_date
                        else None
                    ),
                }
            )

        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1 if page > 1 else None,
            "next_page": page + 1 if page < total_pages else None,
        }

        # Get feedback type distribution for charts
        feedback_distribution = (
            db.session.query(
                SearchFeedback.feedback_type, func.count(SearchFeedback.id)
            )
            .group_by(SearchFeedback.feedback_type)
            .all()
        )

        # Format distribution data
        distribution = {type_name: count for type_name, count in feedback_distribution}

        # Return response
        return jsonify(
            {
                "success": True,
                "data": {
                    "feedback": feedback_list,
                    "pagination": pagination,
                    "distribution": distribution,
                },
            }
        )

    except Exception as e:
        current_app.logger.error(
            f"Error getting feedback data: {str(e)}", exc_info=True
        )
        return jsonify({"success": False, "error": str(e)}), 500
