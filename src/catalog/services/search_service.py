import logging
import time
import datetime
from typing import List, Dict, Any, Optional, Set, Union, Tuple

from sqlalchemy import or_, func, desc, asc, case, text
from sqlalchemy.orm import joinedload

from src.catalog import db, cache

from src.catalog.models import Document, LLMAnalysis, ExtractedText, DesignElement
from src.catalog.models import KeywordTaxonomy, KeywordSynonym, LLMKeyword
from src.catalog.constants import (
    CACHE_TIMEOUTS,
    DEFAULTS,
    SEARCH_TYPES,
    DOCUMENT_STATUSES,
)
from src.catalog.services.preview_service import PreviewService
from src.catalog.services.embeddings_service import EmbeddingsService

logger = logging.getLogger(__name__)


class SearchService:
    """Service for handling different search strategies and result formatting"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.preview_service = PreviewService()
        # Lazy-loaded embeddings service to avoid initialization when not needed
        self._embeddings_service = None

    @property
    def embeddings_service(self):
        """Lazy-load the embeddings service only when needed"""
        if self._embeddings_service is None:
            self._embeddings_service = EmbeddingsService()
        return self._embeddings_service

    def search(self, query: str, **kwargs) -> Tuple[List[Dict], Dict, float]:
        """
        Main search method that orchestrates different search strategies

        Args:
            query: The search query string
            **kwargs: Additional search parameters (page, sort_by, etc.)

        Returns:
            Tuple containing:
            - List of formatted document results
            - Pagination info dictionary
            - Response time in milliseconds
        """
        start_time = time.time()

        # Extract search parameters
        page = kwargs.get("page", 1)
        per_page = kwargs.get("per_page", DEFAULTS["SEARCH_RESULTS_PER_PAGE"])
        sort_by = kwargs.get("sort_by", DEFAULTS["SORT_BY"])
        sort_direction = kwargs.get("sort_dir", DEFAULTS["SORT_DIRECTION"])

        # Extract filter parameters
        filter_type = kwargs.get("filter_type", "")
        filter_year = kwargs.get("filter_year", "")
        filter_location = kwargs.get("filter_location", "")
        primary_category = kwargs.get("primary_category", "")
        subcategory = kwargs.get("subcategory", "")
        specific_term = kwargs.get("specific_term", "")

        # Search strategy selection
        search_type = kwargs.get("search_type", SEARCH_TYPES["HYBRID"])

        # Default values
        expanded_query = None
        formatted_documents = []
        taxonomy_facets = {}

        try:
            # Process query if present
            if query:
                # Expand query with related terms
                expanded_query = self.expand_query(query)

                # Perform search based on strategy
                if search_type == SEARCH_TYPES["KEYWORD"]:
                    base_query = self.perform_keyword_search(query, expanded_query)
                elif search_type == SEARCH_TYPES["VECTOR"]:
                    base_query = self.perform_vector_search(query)
                else:  # Default to hybrid
                    base_query = self.perform_hybrid_search(query, expanded_query)
            else:
                # No query - return all documents
                base_query = db.session.query(Document.id)

            # Apply filters
            base_query = self._apply_filters(
                base_query,
                filter_type=filter_type,
                filter_year=filter_year,
                filter_location=filter_location,
                primary_category=primary_category,
                subcategory=subcategory,
                specific_term=specific_term,
            )

            # Get total count for pagination
            base_query = base_query.distinct()
            total_count = base_query.count()

            # Apply sorting and pagination
            sorted_query = self._apply_sorting(
                db.session.query(Document).filter(Document.id.in_(base_query)),
                sort_by,
                sort_direction,
            )

            # Paginate results
            documents = sorted_query.offset((page - 1) * per_page).limit(per_page).all()

            # Get document IDs for eager loading
            document_ids = [doc.id for doc in documents]

            # Fetch documents with relationships for display
            if document_ids:
                documents = self._fetch_documents_with_relationships(document_ids)

                # Get hierarchical keywords for all documents
                all_keywords = self.get_document_hierarchical_keywords_bulk(
                    document_ids
                )

                # Format documents for display
                formatted_documents = self._format_documents_for_display(
                    documents, all_keywords
                )

                # Queue missing previews for generation
                self._queue_missing_previews([doc.filename for doc in documents])

            # Calculate pagination info
            pagination = self._create_pagination_info(page, per_page, total_count)

            # Generate taxonomy facets for filtering
            taxonomy_facets = self.generate_taxonomy_facets(
                primary_category, subcategory, specific_term
            )

            # Calculate response time
            response_time = (time.time() - start_time) * 1000

            return (
                formatted_documents,
                pagination,
                taxonomy_facets,
                expanded_query,
                response_time,
            )

        except Exception as e:
            self.logger.error(f"Search error: {str(e)}", exc_info=True)
            response_time = (time.time() - start_time) * 1000
            return [], None, {}, None, response_time

    def perform_keyword_search(
        self, query: str, expanded_query: Optional[Union[str, Set[str]]] = None
    ):
        """
        Perform keyword-based search using PostgreSQL full-text search or ILIKE

        Args:
            query: Original search query
            expanded_query: Expanded query terms (optional)

        Returns:
            SQLAlchemy query object with document IDs
        """
        try:
            # If we have search_vector column available, use full-text search
            if hasattr(Document, "search_vector") and hasattr(
                LLMAnalysis, "search_vector"
            ):
                self.logger.info("Using PostgreSQL full-text search")

                # Format query for tsquery if it's a string of terms
                if isinstance(expanded_query, str):
                    search_query = expanded_query
                elif isinstance(expanded_query, set):
                    search_query = " | ".join(expanded_query)
                else:
                    search_query = query

                # Perform full-text search across multiple tables
                combined_query = (
                    db.session.query(Document.id)
                    .outerjoin(LLMAnalysis, Document.id == LLMAnalysis.document_id)
                    .outerjoin(ExtractedText, Document.id == ExtractedText.document_id)
                    .filter(
                        or_(
                            Document.search_vector.op("@@")(
                                func.to_tsquery("english", search_query)
                            ),
                            LLMAnalysis.search_vector.op("@@")(
                                func.to_tsquery("english", search_query)
                            ),
                            ExtractedText.search_vector.op("@@")(
                                func.to_tsquery("english", search_query)
                            ),
                        )
                    )
                )

                return combined_query

            else:
                # Fall back to basic ILIKE search
                self.logger.info("Using ILIKE search (full-text search not available)")

                # Prepare search terms
                if isinstance(expanded_query, set):
                    search_terms = expanded_query
                else:
                    search_terms = {query}

                # Build a query that searches across multiple fields
                combined_query = (
                    db.session.query(Document.id)
                    .outerjoin(LLMAnalysis, Document.id == LLMAnalysis.document_id)
                    .outerjoin(ExtractedText, Document.id == ExtractedText.document_id)
                    .outerjoin(DesignElement, Document.id == DesignElement.document_id)
                )

                # Build conditions for each term and each field
                conditions = []
                for term in search_terms:
                    term_conditions = [
                        Document.filename.ilike(f"%{term}%"),
                        LLMAnalysis.summary_description.ilike(f"%{term}%"),
                        LLMAnalysis.campaign_type.ilike(f"%{term}%"),
                        LLMAnalysis.election_year.ilike(f"%{term}%"),
                        ExtractedText.text_content.ilike(f"%{term}%"),
                        ExtractedText.main_message.ilike(f"%{term}%"),
                        ExtractedText.supporting_text.ilike(f"%{term}%"),
                        DesignElement.geographic_location.ilike(f"%{term}%"),
                    ]
                    conditions.append(or_(*term_conditions))

                # Add the combined conditions to the query
                if conditions:
                    combined_query = combined_query.filter(or_(*conditions))

                return combined_query

        except Exception as e:
            self.logger.error(f"Error in keyword search: {str(e)}", exc_info=True)
            # Return a simple query that matches on filename as fallback
            return db.session.query(Document.id).filter(
                Document.filename.ilike(f"%{query}%")
            )

    def search_document_ids(self, query: str, expanded_query=None):
        """
        Search for document IDs matching the query

        Args:
            query: Search query string
            expanded_query: Expanded query terms (optional)

        Returns:
            List of document IDs matching the search criteria
        """
        try:
            # Try vector search first
            if query:
                # Attempt vector search if available
                try:
                    import asyncio

                    # Create new event loop for each request
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        # Get embeddings
                        query_embeddings = loop.run_until_complete(
                            self.embeddings_service.generate_query_embeddings(query)
                        )
                    finally:
                        # Always close the loop
                        loop.close()

                    if query_embeddings:
                        # Use vector search from query builders
                        from catalog.utils.query_builders import (
                            search_document_ids_by_vector,
                        )

                        vector_results = search_document_ids_by_vector(query_embeddings)

                        if vector_results:
                            # Return IDs from vector results
                            return [doc_id for doc_id, in vector_results.all()]
                except Exception as e:
                    self.logger.error(f"Vector search failed: {str(e)}")
                    # Continue to keyword search on failure

            # Fall back to keyword search
            # First, use the keyword search method
            keyword_query = self.perform_keyword_search(query, expanded_query)

            # Extract document IDs from the query result
            document_ids = [doc_id for doc_id, in keyword_query.all()]

            return document_ids
        except Exception as e:
            self.logger.error(f"Error in search_document_ids: {str(e)}")
            return []

    def perform_vector_search(self, query: str):
        """
        Perform vector-based semantic search with pgvector
        """
        try:
            # Check if vector search is available
            if not hasattr(Document, "embeddings"):
                self.logger.warning(
                    "Vector search not available - Document model doesn't have embeddings attribute"
                )
                return self.perform_keyword_search(query, set([query]))

            # Run the async function to get query embeddings - changes needed here
            import asyncio

            # Create a new event loop for each request to avoid issues
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Get embeddings and ensure we have a result, not a coroutine
                query_embeddings = loop.run_until_complete(
                    self.embeddings_service.generate_query_embeddings(query)
                )
            finally:
                # Always close the loop
                loop.close()

            if not query_embeddings:
                # Fall back to keyword search if embeddings generation fails
                self.logger.warning(
                    "Vector embeddings generation failed, falling back to keyword search"
                )
                return self.perform_keyword_search(query, set([query]))

            # Use a lower threshold to catch more semantic relationships
            similarity_threshold = DEFAULTS["VECTOR_SIMILARITY_THRESHOLD"]

            # Use cosine similarity with pgvector
            # Find documents with similar embeddings using pgvector's <=> operator for cosine distance
            doc_matches = (
                db.session.query(
                    Document.id,
                    (1 - (Document.embeddings.op("<=>")(query_embeddings))).label(
                        "similarity"
                    ),
                )
                .filter(Document.embeddings.is_not(None))
                .filter(
                    (1 - (Document.embeddings.op("<=>")(query_embeddings)))
                    > similarity_threshold
                )
                .subquery()
            )

            # Find analysis content with similar embeddings
            analysis_matches = (
                db.session.query(
                    LLMAnalysis.document_id,
                    (1 - (LLMAnalysis.embeddings.op("<=>")(query_embeddings))).label(
                        "similarity"
                    ),
                )
                .filter(LLMAnalysis.embeddings.is_not(None))
                .filter(
                    (1 - (LLMAnalysis.embeddings.op("<=>")(query_embeddings)))
                    > similarity_threshold
                )
                .subquery()
            )

            # Combine the results and order by similarity score
            combined_query = (
                db.session.query(Document.id)
                .outerjoin(doc_matches, Document.id == doc_matches.c.id)
                .outerjoin(
                    analysis_matches, Document.id == analysis_matches.c.document_id
                )
                .filter(
                    or_(
                        doc_matches.c.id.is_not(None),
                        analysis_matches.c.document_id.is_not(None),
                    )
                )
                .order_by(
                    (
                        func.coalesce(doc_matches.c.similarity, 0)
                        + func.coalesce(analysis_matches.c.similarity, 0)
                    ).desc()
                )
            )

            return combined_query

        except Exception as e:
            self.logger.error(f"Vector search error: {str(e)}")
            # Fall back to keyword search on any error
            return self.perform_keyword_search(query, set([query]))

    def perform_hybrid_search(
        self, query: str, expanded_query: Optional[Union[str, Set[str]]] = None
    ):
        """
        Perform hybrid search combining both vector and keyword search approaches

        Args:
            query: Search query string
            expanded_query: Expanded query terms (optional)

        Returns:
            SQLAlchemy query object with document IDs
        """
        try:
            # Get results from both search methods
            keyword_results = self.perform_keyword_search(query, expanded_query)
            vector_results = self.perform_vector_search(query)

            # Combine results (union)
            combined_results = keyword_results.union(vector_results)

            return combined_results
        except Exception as e:
            self.logger.error(f"Error in hybrid search: {str(e)}", exc_info=True)
            # Fall back to keyword search
            return self.perform_keyword_search(query, expanded_query)

    @cache.memoize(timeout=CACHE_TIMEOUTS["TAXONOMY"])
    def expand_query(self, query: str) -> Union[str, Set[str]]:
        """
        Expand search query with related terms from taxonomy

        Args:
            query: Original search query

        Returns:
            Expanded query as string or set of strings
        """
        if not query or len(query.strip()) < 3:
            return query  # Don't expand very short queries

        expanded_terms = set([query.lower()])  # Start with original query

        try:
            # Find direct matches in taxonomy
            direct_matches = KeywordTaxonomy.query.filter(
                KeywordTaxonomy.term.ilike(f"%{query}%")
            ).all()

            # Find matches in synonyms
            synonym_matches = (
                db.session.query(KeywordTaxonomy)
                .join(KeywordSynonym, KeywordTaxonomy.id == KeywordSynonym.taxonomy_id)
                .filter(KeywordSynonym.synonym.ilike(f"%{query}%"))
                .all()
            )

            # Combine unique matches
            all_matches = {term.id: term for term in direct_matches + synonym_matches}

            # Add matched terms and synonyms to expanded terms
            for term_id, term in all_matches.items():
                expanded_terms.add(term.term.lower())

                # Find and add all synonyms
                synonyms = KeywordSynonym.query.filter_by(taxonomy_id=term.id).all()
                for syn in synonyms:
                    expanded_terms.add(syn.synonym.lower())

                # If we have a subcategory, add related terms in the same subcategory
                if term.subcategory:
                    related_terms = KeywordTaxonomy.query.filter_by(
                        primary_category=term.primary_category,
                        subcategory=term.subcategory,
                    ).all()

                    for related in related_terms:
                        expanded_terms.add(related.term.lower())

            # Remove very short terms (less than 3 chars) and the original query
            expanded_terms = {term for term in expanded_terms if len(term) >= 3}

            # Add original query back if it was removed
            expanded_terms.add(query.lower())

            self.logger.info(f"Expanded query '{query}' to: {expanded_terms}")

            # For PostgreSQL full-text search, format properly
            if hasattr(Document, "search_vector"):
                # Use the | operator for OR in tsquery
                return " | ".join(expanded_terms)
            else:
                # For ILIKE queries, we'll use the expanded terms list directly
                return expanded_terms

        except Exception as e:
            self.logger.error(f"Error in query expansion: {str(e)}")
            return query  # Fall back to original query on error

    @cache.memoize(timeout=CACHE_TIMEOUTS["TAXONOMY"])
    def generate_taxonomy_facets(
        self, selected_primary=None, selected_subcategory=None, selected_term=None
    ):
        """
        Generate taxonomy facets for sidebar filtering with terms using LLMKeywords
        """
        try:
            # Query for primary categories through LLMKeyword relationship
            primary_categories = (
                db.session.query(
                    KeywordTaxonomy.primary_category,
                    func.count(LLMKeyword.id.distinct()).label("count"),
                )
                .join(LLMKeyword, KeywordTaxonomy.id == LLMKeyword.taxonomy_id)
                .group_by(KeywordTaxonomy.primary_category)
                .filter(
                    KeywordTaxonomy.primary_category.isnot(
                        None
                    )  # Ensure non-null values
                )
                .order_by(KeywordTaxonomy.primary_category)
                .all()
            )

            # Log for debugging
            self.logger.info(
                f"Found {len(primary_categories)} primary categories from LLMKeywords"
            )

            # If no results, try direct query on KeywordTaxonomy without joins
            if not primary_categories:
                self.logger.warning(
                    "No primary categories found with LLMKeyword join, trying direct query"
                )
                primary_categories = (
                    db.session.query(
                        KeywordTaxonomy.primary_category,
                        func.count(KeywordTaxonomy.id).label("count"),
                    )
                    .filter(KeywordTaxonomy.primary_category.isnot(None))
                    .group_by(KeywordTaxonomy.primary_category)
                    .order_by(KeywordTaxonomy.primary_category)
                    .all()
                )

                self.logger.info(
                    f"Direct query found {len(primary_categories)} primary categories"
                )

            # Get subcategories if primary category selected
            subcategories_data = []
            if selected_primary:
                # Get all distinct subcategories defined under the selected primary category
                defined_subcategories = (
                    db.session.query(KeywordTaxonomy.subcategory)
                    .filter(
                        KeywordTaxonomy.primary_category == selected_primary,
                        KeywordTaxonomy.subcategory.isnot(None),
                    )
                    .distinct()
                    .order_by(KeywordTaxonomy.subcategory)
                    .all()
                )

                for subcat_tuple in defined_subcategories:
                    subcat_name = subcat_tuple[0]
                    if not subcat_name:  # Skip if subcategory name is None or empty
                        continue
                    # Count documents linked to this primary_category and subcategory via LLMKeyword
                    count = (
                        db.session.query(func.count(LLMKeyword.document_id.distinct()))
                        .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
                        .join(
                            KeywordTaxonomy,
                            LLMKeyword.taxonomy_id == KeywordTaxonomy.id,
                        )
                        .filter(
                            KeywordTaxonomy.primary_category == selected_primary,
                            KeywordTaxonomy.subcategory == subcat_name,
                        )
                        .scalar()
                        or 0
                    )  # Ensure count is 0 if scalar() returns None
                    subcategories_data.append(
                        {
                            "name": subcat_name,
                            "count": count,
                            "selected": subcat_name == selected_subcategory,
                        }
                    )

            # Get terms if both primary and subcategory selected
            terms_data = []
            if selected_primary and selected_subcategory:
                # Get all distinct terms defined under the selected primary and subcategory
                defined_terms = (
                    db.session.query(KeywordTaxonomy.term)
                    .filter(
                        KeywordTaxonomy.primary_category == selected_primary,
                        KeywordTaxonomy.subcategory == selected_subcategory,
                        KeywordTaxonomy.term.isnot(None),
                    )
                    .distinct()
                    .order_by(KeywordTaxonomy.term)
                    .all()
                )

                for term_tuple in defined_terms:
                    term_name = term_tuple[0]
                    if not term_name:  # Skip if term name is None or empty
                        continue
                    # Count documents linked to this primary_category, subcategory, and term via LLMKeyword
                    count = (
                        db.session.query(func.count(LLMKeyword.document_id.distinct()))
                        .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
                        .join(
                            KeywordTaxonomy,
                            LLMKeyword.taxonomy_id == KeywordTaxonomy.id,
                        )
                        .filter(
                            KeywordTaxonomy.primary_category == selected_primary,
                            KeywordTaxonomy.subcategory == selected_subcategory,
                            KeywordTaxonomy.term == term_name,
                        )
                        .scalar()
                        or 0
                    )  # Ensure count is 0 if scalar() returns None
                    terms_data.append(
                        {
                            "name": term_name,
                            "count": count,
                            "selected": term_name == selected_term,
                        }
                    )

            # Format results
            result = {
                "primary_categories": [
                    {"name": cat, "count": count, "selected": cat == selected_primary}
                    for cat, count in primary_categories
                    if cat  # Skip empty categories
                ],
                "subcategories": subcategories_data,
                "terms": terms_data,
            }

            return result
        except Exception as e:
            self.logger.error(
                f"Error generating taxonomy facets: {str(e)}", exc_info=True
            )
            # Return empty but properly structured result on error
            return {"primary_categories": [], "subcategories": [], "terms": []}

    def _apply_filters(self, query, **filters):
        """
        Apply filters to the search query

        Args:
            query: Base SQLAlchemy query
            **filters: Filter parameters

        Returns:
            SQLAlchemy query with filters applied
        """
        # Extract filter parameters
        filter_type = filters.get("filter_type", "")
        filter_year = filters.get("filter_year", "")
        filter_location = filters.get("filter_location", "")
        primary_category = filters.get("primary_category", "")
        subcategory = filters.get("subcategory", "")
        specific_term = filters.get("specific_term", "")

        # Apply document type filter
        if filter_type:
            query = query.join(
                LLMAnalysis, Document.id == LLMAnalysis.document_id, isouter=True
            )
            if "," in filter_type:
                doc_type_list = filter_type.split(",")
                query = query.filter(LLMAnalysis.document_tone.in_(doc_type_list))
            else:
                query = query.filter(LLMAnalysis.document_tone == filter_type)

        # Apply year filter
        if filter_year:
            if not filter_type:  # Only join if not already joined
                query = query.join(
                    LLMAnalysis, Document.id == LLMAnalysis.document_id, isouter=True
                )
            query = query.filter(LLMAnalysis.election_year == filter_year)

        # Apply location filter
        if filter_location:
            query = query.join(
                DesignElement, Document.id == DesignElement.document_id, isouter=True
            ).filter(
                func.lower(DesignElement.geographic_location).like(
                    f"%{filter_location.lower()}%"
                )
            )

        # Apply taxonomy filters with improved performance
        if primary_category:
            # Use a subquery to get document IDs that match the taxonomy criteria
            # Corrected to query LLMAnalysis.document_id and join appropriately
            taxonomy_query = (
                db.session.query(LLMAnalysis.document_id)
                .select_from(LLMKeyword)
                .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
                .join(KeywordTaxonomy, LLMKeyword.taxonomy_id == KeywordTaxonomy.id)
                .filter(KeywordTaxonomy.primary_category == primary_category)
            )

            if subcategory:
                taxonomy_query = taxonomy_query.filter(
                    KeywordTaxonomy.subcategory == subcategory
                )

            if specific_term:
                taxonomy_query = taxonomy_query.filter(
                    KeywordTaxonomy.term == specific_term
                )

            # Use EXISTS for better performance by applying distinct and subquery
            taxonomy_ids = taxonomy_query.distinct().subquery()
            query = query.filter(Document.id.in_(taxonomy_ids))

        return query

    def _apply_sorting(self, query, sort_by, sort_direction):
        """
        Apply sorting to the query

        Args:
            query: SQLAlchemy query
            sort_by: Field to sort by
            sort_direction: Direction to sort (asc/desc)

        Returns:
            Sorted SQLAlchemy query
        """
        if sort_by == "filename":
            if sort_direction == "desc":
                return query.order_by(Document.filename.desc())
            else:
                return query.order_by(Document.filename.asc())
        else:  # Default to upload_date
            if sort_direction == "desc":
                return query.order_by(Document.upload_date.desc())
            else:
                return query.order_by(Document.upload_date.asc())

    def _apply_taxonomy_filter(
        self, query, primary_category=None, subcategory=None, specific_term=None
    ):
        """Apply taxonomy filter to the search query"""
        if not primary_category:
            return query

        # Use a subquery to get document IDs with taxonomy matches using LLMKeyword
        taxonomy_query = (
            db.session.query(LLMKeyword.document_id)
            .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
            .join(KeywordTaxonomy, LLMKeyword.taxonomy_id == KeywordTaxonomy.id)
            .filter(KeywordTaxonomy.primary_category == primary_category)
        )

        if subcategory:
            taxonomy_query = taxonomy_query.filter(
                KeywordTaxonomy.subcategory == subcategory
            )

        if specific_term:
            taxonomy_query = taxonomy_query.filter(
                KeywordTaxonomy.term == specific_term
            )

        # Get document IDs from the subquery
        taxonomy_ids = taxonomy_query.distinct().subquery()

        # Filter the main query with these IDs
        query = query.filter(Document.id.in_(taxonomy_ids))

        return query

    def _fetch_documents_with_relationships(self, document_ids):
        """
        Fetch documents with all necessary relationships for display

        Args:
            document_ids: List of document IDs

        Returns:
            List of document objects with relationships
        """
        documents = (
            Document.query.filter(Document.id.in_(document_ids))
            .options(
                joinedload(Document.llm_analysis).joinedload(LLMAnalysis.keywords),
                joinedload(Document.entity),
                joinedload(Document.design_elements),
                joinedload(Document.communication_focus),
                joinedload(Document.extracted_text),
            )
            .all()
        )

        # Convert to a dictionary keyed by ID for correct ordering
        id_to_doc = {doc.id: doc for doc in documents}

        # Return documents in the same order as document_ids
        return [id_to_doc[doc_id] for doc_id in document_ids if doc_id in id_to_doc]

    def _format_documents_for_display(self, documents, all_keywords):
        """
        Format documents for display with all necessary data
        """
        formatted_docs = []
        for doc in documents:
            try:
                # Get preview if possible
                preview = None
                try:
                    preview = self.preview_service.get_preview(doc.filename)
                except Exception as e:
                    self.logger.error(
                        f"Preview generation failed for {doc.filename}: {str(e)}"
                    )

                # Format document data
                document_data = {
                    "id": doc.id,
                    "filename": doc.filename,
                    "upload_date": doc.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": doc.status,
                    "preview": preview,
                    # LLM Analysis data
                    "summary": (
                        doc.llm_analysis.summary_description
                        if hasattr(doc, "llm_analysis") and doc.llm_analysis
                        else ""
                    ),
                    "document_type": (
                        doc.llm_analysis.campaign_type
                        if hasattr(doc, "llm_analysis") and doc.llm_analysis
                        else ""
                    ),
                    "election_year": (
                        doc.llm_analysis.election_year
                        if hasattr(doc, "llm_analysis") and doc.llm_analysis
                        else ""
                    ),
                    "document_tone": (
                        doc.llm_analysis.document_tone
                        if hasattr(doc, "llm_analysis") and doc.llm_analysis
                        else ""
                    ),
                    # Entity data
                    "client": (
                        doc.entity.client_name
                        if hasattr(doc, "entity") and doc.entity
                        else ""
                    ),
                    "opponent": (
                        doc.entity.opponent_name
                        if hasattr(doc, "entity") and doc.entity
                        else ""
                    ),
                    # Design elements
                    "location": (
                        doc.design_elements.geographic_location
                        if hasattr(doc, "design_elements") and doc.design_elements
                        else ""
                    ),
                    "target_audience": (
                        doc.design_elements.target_audience
                        if hasattr(doc, "design_elements") and doc.design_elements
                        else ""
                    ),
                    # Communication focus
                    "primary_issue": (
                        doc.communication_focus.primary_issue
                        if hasattr(doc, "communication_focus")
                        and doc.communication_focus
                        else ""
                    ),
                    # Extract text
                    "main_message": (
                        doc.extracted_text.main_message
                        if hasattr(doc, "extracted_text") and doc.extracted_text
                        else ""
                    ),
                    # Hierarchical keywords - format LLMKeywords
                    "hierarchical_keywords": [
                        {
                            "term": kw.keyword,
                            "primary_category": kw.category,
                            "subcategory": "",  # LLMKeyword doesn't have subcategory
                            "relevance_score": (
                                kw.relevance_score / 100 if kw.relevance_score else 0
                            ),
                        }
                        for kw in (
                            doc.llm_analysis.keywords
                            if hasattr(doc, "llm_analysis")
                            and doc.llm_analysis
                            and hasattr(doc.llm_analysis, "keywords")
                            else []
                        )
                    ],
                }

                # Log the hierarchical keywords for debugging
                self.logger.debug(
                    f"Document {doc.id} hierarchical keywords: {document_data['hierarchical_keywords']}"
                )

                formatted_docs.append(document_data)
            except Exception as e:
                self.logger.error(f"Error formatting document {doc.id}: {str(e)}")
                # Skip documents that can't be formatted
                continue

        return formatted_docs

    # Also update the get_document_hierarchical_keywords_bulk method to ensure it uses the new manager
    def get_document_hierarchical_keywords_bulk(
        self, document_ids: List[int]
    ) -> Dict[int, List[Dict]]:
        """
        Efficiently get hierarchical keywords for multiple documents at once

        Args:
            document_ids: List of document IDs

        Returns:
            Dictionary mapping document IDs to their keywords
        """
        try:
            # Use the DocumentKeywordManager for consistent keyword retrieval
            from src.catalog.services.keyword_manager import DocumentKeywordManager

            return DocumentKeywordManager.get_bulk_document_keywords(document_ids)
        except Exception as e:
            self.logger.error(f"Error getting hierarchical keywords: {str(e)}")
            return {doc_id: [] for doc_id in document_ids}

    def _queue_missing_previews(self, filenames):
        """
        Queue preview generation for files that don't have cached previews

        Args:
            filenames: List of filenames to check
        """
        try:
            missing_previews = []
            for filename in filenames:
                cache_key = f"preview:{filename}"
                if not cache.get(cache_key):
                    missing_previews.append(filename)

            if missing_previews:
                try:
                    from tasks.preview_tasks import generate_preview

                    for filename in missing_previews:
                        generate_preview.delay(filename)
                except Exception as e:
                    self.logger.error(f"Error queueing preview generation: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error checking for missing previews: {str(e)}")

    def _create_pagination_info(self, page, per_page, total_count):
        """
        Create pagination information dictionary

        Args:
            page: Current page number
            per_page: Items per page
            total_count: Total item count

        Returns:
            Dictionary with pagination information
        """
        pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0

        return {
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "pages": pages,
            "has_prev": page > 1,
            "has_next": page < pages,
            "prev_page": page - 1 if page > 1 else None,
            "next_page": page + 1 if page < pages else None,
        }

    # Add these methods to the SearchService class

    def get_taxonomy_suggestions(self, query):
        """
        Get taxonomy term suggestions for autocomplete

        Args:
            query: Search query string

        Returns:
            List of suggestion dictionaries
        """
        try:
            if not query or len(query) < 2:
                return []

            # Search for matching taxonomy terms
            terms = (
                KeywordTaxonomy.query.filter(KeywordTaxonomy.term.ilike(f"%{query}%"))
                .limit(10)
                .all()
            )

            # Search for matching synonyms
            synonym_matches = (
                db.session.query(KeywordTaxonomy)
                .join(KeywordSynonym, KeywordTaxonomy.id == KeywordSynonym.taxonomy_id)
                .filter(KeywordSynonym.synonym.ilike(f"%{query}%"))
                .limit(10)
                .all()
            )

            # Combine and deduplicate
            unique_terms = {term.id: term for term in terms + synonym_matches}

            # Format for autocomplete
            suggestions = []
            for term in unique_terms.values():
                suggestions.append(
                    {
                        "id": term.id,
                        "value": term.term,
                        "label": f"{term.term} ({term.primary_category}: {term.subcategory})",
                        "category": term.primary_category,
                        "subcategory": term.subcategory,
                    }
                )

            return suggestions
        except Exception as e:
            self.logger.error(f"Error getting taxonomy suggestions: {str(e)}")
            return []

    def get_related_taxonomy_terms(self, term_id):
        """
        Get related taxonomy terms for a given term ID

        Args:
            term_id: Taxonomy term ID

        Returns:
            List of related term dictionaries
        """
        try:
            term = KeywordTaxonomy.query.get_or_404(term_id)

            # Get all related terms (parent, children, siblings)
            related_terms = []

            # Add parent if exists
            if term.parent_id:
                parent = KeywordTaxonomy.query.get(term.parent_id)
                if parent:
                    related_terms.append(parent)

            # Add siblings (other terms with same parent)
            if term.parent_id:
                siblings = KeywordTaxonomy.query.filter(
                    KeywordTaxonomy.parent_id == term.parent_id,
                    KeywordTaxonomy.id != term.id,
                ).all()
                related_terms.extend(siblings)

            # Add children
            children = KeywordTaxonomy.query.filter(
                KeywordTaxonomy.parent_id == term.id
            ).all()
            related_terms.extend(children)

            # Format for response
            result = [self._format_taxonomy_term(t) for t in related_terms]
            return result
        except Exception as e:
            self.logger.error(f"Error getting related terms: {str(e)}")
            raise

    def _format_taxonomy_term(self, term):
        """Format a taxonomy term for API response"""
        return {
            "id": term.id,
            "term": term.term,
            "primary_category": term.primary_category,
            "subcategory": term.subcategory,
            "specific_term": term.specific_term,
            "parent_id": term.parent_id,
            "synonyms": [s.synonym for s in term.synonyms] if term.synonyms else [],
        }

    def record_search_feedback(self, data):
        """
        Record search feedback from users

        Args:
            data: Feedback data dictionary

        Returns:
            Result dictionary
        """
        try:
            # Add debug logging
            logger = logging.getLogger(__name__)
            logger.info(f"Processing feedback data: {data}")

            # Validate required fields
            if "document_id" not in data or not data["document_id"]:
                logger.warning("Missing document_id in feedback data")
                return {"status": "error", "message": "Missing document ID"}

            if "feedback_type" not in data or not data["feedback_type"]:
                logger.warning("Missing feedback_type in feedback data")
                return {"status": "error", "message": "Missing feedback type"}

            # Get document to verify it exists
            document = Document.query.get(data["document_id"])
            if not document:
                logger.warning(f"Document not found: {data['document_id']}")
                return {
                    "status": "error",
                    "message": f"Document with ID {data['document_id']} not found",
                }

            # Create feedback record
            from src.catalog.models import SearchFeedback

            feedback = SearchFeedback(
                # Use empty string if not provided
                search_query=data.get("search_query", ""),
                document_id=data["document_id"],
                feedback_type=data["feedback_type"],
                # Use empty string if not provided
                user_comment=data.get("comment", ""),
                feedback_date=datetime.utcnow(),  # Make sure to set the date
            )

            logger.info(f"Creating feedback record: {feedback.__dict__}")

            db.session.add(feedback)
            db.session.commit()

            logger.info(f"Successfully recorded feedback with ID: {feedback.id}")

            return {
                "status": "success",
                "message": "Feedback recorded successfully",
                "feedback_id": feedback.id,
            }
        except Exception as e:
            logger.error(f"Error recording search feedback: {str(e)}", exc_info=True)
            db.session.rollback()
            return {"status": "error", "message": f"Database error: {str(e)}"}
