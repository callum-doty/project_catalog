from src.catalog.utils.query_builders import (
    build_document_with_relationships_query,
    filter_by_document_type,
    filter_by_year,
    filter_by_location,
    filter_by_taxonomy,
    apply_sorting,
    apply_pagination,
)
from flask import Blueprint, render_template, request, jsonify, current_app
from src.catalog.services.search_service import SearchService
from src.catalog import cache, db
from src.catalog.constants import CACHE_TIMEOUTS
from src.catalog.utils import monitor_query
from src.catalog.models import Document
import time
from src.catalog.models import LLMAnalysis, LLMKeyword, KeywordTaxonomy
from src.catalog.services.storage_service import MinIOStorage  # Added import

search_routes = Blueprint("search_routes", __name__)
search_service = SearchService()
storage_service = MinIOStorage()  # Added storage service instance


@search_routes.route("/")
@monitor_query
@cache.cached(timeout=CACHE_TIMEOUTS["SEARCH"], query_string=True)
def search_documents():
    """Search documents with multiple strategies and filters"""
    start_time = time.time()

    try:
        # Extract all parameters from the request
        query = request.args.get("q", "")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 12, type=int)
        sort_by = request.args.get("sort_by", "upload_date")
        sort_direction = request.args.get("sort_dir", "desc")
        filter_type = request.args.get("filter_type", "")
        filter_year = request.args.get("filter_year", "")
        filter_location = request.args.get("filter_location", "")
        primary_category = request.args.get("primary_category", "")
        subcategory = request.args.get("subcategory", "")
        specific_term = request.args.get("specific_term", "")

        # Default values
        expanded_query = None
        taxonomy_facets = {"primary_categories": [], "subcategories": [], "terms": []}

        # Step 1: Get document IDs matching the search query
        document_ids = []

        if query:
            # Use the search service to get document IDs
            # This part stays in the search service since it's specific to search
            expanded_query = search_service.expand_query(query)

            if isinstance(expanded_query, set):
                expanded_query_list = list(expanded_query)
            else:
                expanded_query_list = [expanded_query]

            # Based on search strategy, get matching document IDs
            document_ids = search_service.search_document_ids(query, expanded_query)

        # Step 2: Build base query for documents with relationships
        if query and document_ids:
            # Filter by document IDs from search results
            base_query = build_document_with_relationships_query().filter(
                Document.id.in_(document_ids)
            )
        else:
            # No search query, get all documents
            base_query = build_document_with_relationships_query()

        # Step 3: Apply filters
        if filter_type:
            base_query = filter_by_document_type(base_query, filter_type)

        if filter_year:
            base_query = filter_by_year(base_query, filter_year)

        if filter_location:
            base_query = filter_by_location(base_query, filter_location)

        # Handle taxonomy filtering with proper variable initialization
        if primary_category:
            try:
                # Create the taxonomy query to get matching document IDs
                taxonomy_query = (
                    db.session.query(LLMAnalysis.document_id)
                    .join(LLMKeyword, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
                    .join(KeywordTaxonomy, LLMKeyword.taxonomy_id == KeywordTaxonomy.id)
                    .filter(KeywordTaxonomy.primary_category == primary_category)
                )

                # Apply subcategory filter if present
                if subcategory:
                    taxonomy_query = taxonomy_query.filter(
                        KeywordTaxonomy.subcategory == subcategory
                    )

                # Apply specific term filter if present
                if specific_term:
                    taxonomy_query = taxonomy_query.filter(
                        KeywordTaxonomy.term == specific_term
                    )

                # Use the taxonomy query to filter document IDs
                taxonomy_ids_subquery = taxonomy_query.distinct().subquery()
                base_query = base_query.filter(
                    Document.id.in_(taxonomy_ids_subquery.select())
                )

            except Exception as e:
                current_app.logger.error(f"Error applying taxonomy filter: {str(e)}")
                # If there's an error, try using the filter_by_taxonomy function as fallback
                base_query = filter_by_taxonomy(
                    base_query,
                    primary_category=primary_category,
                    subcategory=subcategory,
                    specific_term=specific_term,
                )

        # Step 4: Apply sorting and pagination
        sorted_query = apply_sorting(base_query, sort_by, sort_direction)

        # Get total count and apply pagination
        paginated_query, pagination = apply_pagination(sorted_query, page, per_page)

        # Step 5: Get documents
        documents = paginated_query.all()

        # Step 6: Format documents for display
        document_ids = [doc.id for doc in documents]

        if document_ids:
            # Get hierarchical keywords for all documents
            all_keywords = search_service.get_document_hierarchical_keywords_bulk(
                document_ids
            )

            # Format documents for display
            formatted_documents = search_service._format_documents_for_display(
                documents, all_keywords
            )

            # Queue missing previews for generation
            search_service._queue_missing_previews([doc.filename for doc in documents])
        else:
            formatted_documents = []

        # Step 7: Generate taxonomy facets for filtering
        taxonomy_facets = search_service.generate_taxonomy_facets(
            primary_category, subcategory, specific_term
        )

        # Calculate response time
        response_time = (time.time() - start_time) * 1000

        # Check for AJAX request
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # For AJAX requests, render cards to HTML server-side
            cards_html_list = []
            if formatted_documents:
                doc_card_template = current_app.jinja_env.get_template(
                    "components/cards/document_card.html"
                )
                doc_card_macro = getattr(
                    doc_card_template.module, "document_card", None
                )

                if doc_card_macro:
                    for doc_data_dict in formatted_documents:
                        card_html = doc_card_macro(doc=doc_data_dict)
                        cards_html_list.append(card_html)
                else:
                    current_app.logger.error(
                        "Could not load document_card macro from components/cards/document_card.html"
                    )

            # Ensure expanded_query_list is suitable for JSON
            # expanded_query_list is already a list (potentially of one item, or empty if original query was None)
            final_expanded_terms = []
            if expanded_query_list and expanded_query_list[0] is not None:
                final_expanded_terms = expanded_query_list

            return jsonify(
                {
                    "results_html": cards_html_list,  # Send list of HTML strings
                    "pagination": pagination,
                    "taxonomy_facets": taxonomy_facets,
                    "expanded_terms": final_expanded_terms,
                    "response_time_ms": round(response_time, 2),
                    "query": query,
                }
            )
        else:
            # Return HTML for browser requests
            return render_template(
                "pages/search.html",
                documents=formatted_documents,
                pagination=pagination,
                taxonomy_facets=taxonomy_facets,
                expanded_terms=(
                    expanded_query_list if isinstance(expanded_query, set) else []
                ),
                query=query,
                sort_by=sort_by,
                sort_dir=sort_direction,
                primary_category=primary_category,
                subcategory=subcategory,
                specific_term=specific_term,
                filter_type=filter_type,
                filter_year=filter_year,
                filter_location=filter_location,
                response_time_ms=round(response_time, 2),
            )

    except Exception as e:
        current_app.logger.error(f"Search error: {str(e)}", exc_info=True)

        response_time = (time.time() - start_time) * 1000

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {
                    "error": str(e),
                    "results": [],
                    "pagination": None,
                    "expanded_terms": [],
                    "response_time_ms": round(response_time, 2),
                }
            )
        else:
            return render_template(
                "pages/search.html",
                documents=[],
                query=query,
                error=str(e),
                taxonomy_facets={
                    "primary_categories": [],
                    "subcategories": [],
                    "terms": [],
                },
                expanded_terms=[],
                response_time_ms=round(response_time, 2),
            )


@search_routes.route("/api/taxonomy/suggestions")
def taxonomy_suggestions():
    """API endpoint for taxonomy term suggestions/autocomplete"""
    try:
        query = request.args.get("q", "")
        if not query or len(query) < 2:
            return jsonify([])

        # Use search service to get taxonomy suggestions
        suggestions = search_service.get_taxonomy_suggestions(query)
        return jsonify(suggestions)
    except Exception as e:
        current_app.logger.error(f"Error getting taxonomy suggestions: {str(e)}")
        return jsonify([])


@search_routes.route("/api/taxonomy/related-terms/<int:term_id>")
def related_taxonomy_terms(term_id):
    """Get related taxonomy terms for a given term ID"""
    try:
        # Use search service to get related terms
        related_terms = search_service.get_related_taxonomy_terms(term_id)
        return jsonify(related_terms)
    except Exception as e:
        current_app.logger.error(f"Error getting related terms: {str(e)}")
        return jsonify([]), 500


@search_routes.route("/fallback_to_direct_url")
def fallback_to_direct_url():
    """
    Provides a direct, presigned URL to an original document in storage.
    This is used as a fallback when preview generation fails.
    """
    filename = request.args.get("filename")
    if not filename:
        return jsonify({"error": "Missing filename parameter"}), 400

    try:
        # Use the MinIOStorage service to get a presigned URL
        # The MinIOStorage class is a singleton, so instantiating it
        # will return the existing instance.
        url = storage_service.get_presigned_url(filename)

        if url:
            return jsonify({"direct_url": url})
        else:
            current_app.logger.error(f"Failed to generate presigned URL for {filename}")
            return jsonify({"error": "Could not generate direct URL"}), 500
    except Exception as e:
        current_app.logger.error(
            f"Error generating presigned URL for {filename}: {str(e)}", exc_info=True
        )
        return jsonify({"error": "Server error generating direct URL"}), 500
