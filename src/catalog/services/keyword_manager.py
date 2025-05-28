from src.catalog import db
from src.catalog.models import (
    Document,
    LLMKeyword,
    KeywordTaxonomy,
    KeywordSynonym,
    LLMAnalysis,
)
from datetime import datetime
import logging
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class DocumentKeywordManager:
    """Manager for document keywords with improved taxonomy integration"""

    @staticmethod
    def process_document_keywords(
        document_id: int, keyword_data: List[Dict[str, Any]], max_keywords: int = 10
    ) -> bool:
        """
        Process and store keywords for a document, limited to top N keywords

        Args:
            document_id: The document ID
            keyword_data: List of keyword data from LLM
            max_keywords: Maximum number of keywords to store (default: 10)

        Returns:
            Success flag
        """
        try:
            llm_analysis = LLMAnalysis.query.filter_by(document_id=document_id).first()
            if not llm_analysis:
                logger.error(
                    f"No LLMAnalysis found for document_id {document_id}. Cannot process keywords."
                )
                return False

            llm_analysis_id = llm_analysis.id

            # Clear existing keywords for this llm_analysis_id to avoid duplication
            existing_keywords = LLMKeyword.query.filter_by(
                llm_analysis_id=llm_analysis_id
            ).all()
            if existing_keywords:
                logger.info(
                    f"Removing {len(existing_keywords)} existing keywords for LLMAnalysis {llm_analysis_id} (document {document_id})"
                )
                for kw_to_delete in existing_keywords:
                    db.session.delete(kw_to_delete)
                db.session.commit()

            # Validate and sort keywords by relevance
            valid_keywords = []
            for idx, kw in enumerate(keyword_data):
                if not isinstance(kw, dict):
                    continue

                # Extract required fields
                term = kw.get("specific_term")
                if not term:
                    continue

                primary_category = kw.get("primary_category", "")
                subcategory = kw.get("subcategory", "")
                relevance_score = float(kw.get("relevance_score", 0.5))

                valid_keywords.append(
                    {
                        "term": term,
                        "primary_category": primary_category,
                        "subcategory": subcategory,
                        "relevance_score": relevance_score,
                        "synonyms": kw.get("synonyms", []),
                        "original_index": idx,  # Preserve original order as fallback
                    }
                )

            # Sort by relevance (highest first)
            valid_keywords.sort(key=lambda x: x["relevance_score"], reverse=True)

            # Limit to max_keywords
            top_keywords = valid_keywords[:max_keywords]

            # Process and store each keyword
            stored_keywords = []
            for idx, kw in enumerate(top_keywords):
                try:
                    # Find or create taxonomy term
                    taxonomy_term = KeywordTaxonomy.query.filter(
                        KeywordTaxonomy.term == kw["term"],
                        KeywordTaxonomy.primary_category == kw["primary_category"],
                    ).first()

                    # If no exact match, check for similar terms
                    if not taxonomy_term:
                        similar_term = KeywordTaxonomy.query.filter(
                            KeywordTaxonomy.term.ilike(f"%{kw['term']}%"),
                            KeywordTaxonomy.primary_category == kw["primary_category"],
                        ).first()

                        if similar_term:
                            taxonomy_term = similar_term
                            logger.info(
                                f"Using similar taxonomy term: {similar_term.term}"
                            )
                        else:
                            # Create new term
                            taxonomy_term = KeywordTaxonomy(
                                term=kw["term"],
                                primary_category=kw["primary_category"],
                                subcategory=kw["subcategory"],
                                specific_term=kw["term"],
                            )
                            db.session.add(taxonomy_term)
                            db.session.flush()  # Get the ID

                            # Add synonyms if provided
                            synonyms = kw.get("synonyms", [])
                            if synonyms:
                                for syn_text in synonyms:
                                    if syn_text:
                                        synonym = KeywordSynonym(
                                            taxonomy_id=taxonomy_term.id,
                                            synonym=syn_text,
                                        )
                                        db.session.add(synonym)

                    # Create LLMKeyword instance
                    # LLMKeyword.relevance_score is BigInteger, manager uses float. Cast to int (0-100 assumed).
                    relevance_score_int = (
                        int(kw["relevance_score"] * 100)
                        if isinstance(kw["relevance_score"], float)
                        else int(kw["relevance_score"])
                    )

                    llm_db_keyword = LLMKeyword(
                        llm_analysis_id=llm_analysis_id,
                        keyword=kw["term"],  # Maps to LLMKeyword.keyword
                        category=kw["primary_category"],  # Maps to LLMKeyword.category
                        relevance_score=relevance_score_int,
                        taxonomy_id=taxonomy_term.id,
                        # LLMKeyword does not have extraction_date or display_order from original DocumentKeyword
                    )
                    db.session.add(llm_db_keyword)
                    stored_keywords.append(llm_db_keyword)

                except Exception as e:
                    logger.error(
                        f"Error processing keyword {kw['term']} for document {document_id}: {str(e)}"
                    )
                    continue

            # Commit all changes
            db.session.commit()
            logger.info(
                f"Successfully stored {len(stored_keywords)} keywords for LLMAnalysis {llm_analysis_id} (document {document_id})"
            )

            # Verify storage
            verification_count = LLMKeyword.query.filter_by(
                llm_analysis_id=llm_analysis_id
            ).count()
            logger.info(
                f"Verification: {verification_count} keywords in database for LLMAnalysis {llm_analysis_id} (document {document_id})"
            )

            return True

        except Exception as e:
            logger.error(
                f"Error processing document keywords for document {document_id}: {str(e)}"
            )
            db.session.rollback()
            return False

    @staticmethod
    def get_document_keywords(document_id: int) -> List[Dict[str, Any]]:
        """
        Get formatted keywords for a document

        Args:
            document_id: The document ID

        Returns:
            List of formatted keywords for display
        """
        try:
            llm_analysis = LLMAnalysis.query.filter_by(document_id=document_id).first()
            if not llm_analysis:
                logger.warning(
                    f"No LLMAnalysis found for document_id {document_id} when getting keywords."
                )
                return []

            llm_analysis_id = llm_analysis.id

            # Query LLMKeywords with taxonomy join, ordered by relevance_score (desc)
            # as display_order is not in LLMKeyword
            keywords_with_taxonomy = (
                db.session.query(LLMKeyword, KeywordTaxonomy)
                .join(
                    KeywordTaxonomy,
                    LLMKeyword.taxonomy_id == KeywordTaxonomy.id,
                    isouter=True,  # Use outer join in case taxonomy_id is null
                )
                .filter(LLMKeyword.llm_analysis_id == llm_analysis_id)
                .order_by(LLMKeyword.relevance_score.desc())  # Order by relevance
                .all()
            )

            # Format for display
            result = []
            for llm_kw, taxonomy in keywords_with_taxonomy:
                # LLMKeyword.relevance_score is BigInteger (0-100), convert back to float (0.0-1.0)
                relevance_score_float = (
                    float(llm_kw.relevance_score) / 100.0
                    if llm_kw.relevance_score is not None
                    else 0.0
                )

                term_display = (
                    taxonomy.term if taxonomy else llm_kw.keyword
                )  # Fallback to LLMKeyword.keyword if no taxonomy
                primary_cat_display = (
                    taxonomy.primary_category if taxonomy else llm_kw.category
                )  # Fallback
                subcat_display = taxonomy.subcategory if taxonomy else None

                result.append(
                    {
                        "id": taxonomy.id if taxonomy else None,
                        "term": term_display,
                        "primary_category": primary_cat_display,
                        "subcategory": subcat_display,
                        "relevance_score": relevance_score_float,
                    }
                )
            return result

        except Exception as e:
            logger.error(
                f"Error getting keywords for document {document_id} (LLMAnalysis {llm_analysis_id if 'llm_analysis_id' in locals() else 'N/A'}): {str(e)}"
            )
            return []

    @staticmethod
    def get_bulk_document_keywords(
        document_ids: List[int],
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Efficiently get keywords for multiple documents at once

        Args:
            document_ids: List of document IDs

        Returns:
            Dictionary mapping document IDs to their keywords
        """
        try:
            # Get llm_analysis_ids for the given document_ids
            analysis_map = {
                analysis.document_id: analysis.id
                for analysis in LLMAnalysis.query.filter(
                    LLMAnalysis.document_id.in_(document_ids)
                ).all()
            }

            llm_analysis_ids = [id for id in analysis_map.values() if id is not None]

            if not llm_analysis_ids:
                logger.warning(
                    f"No LLMAnalysis found for document_ids: {document_ids} in get_bulk_document_keywords."
                )
                return {doc_id: [] for doc_id in document_ids}

            # Single query to get all LLMKeywords for all relevant analyses
            keywords_with_taxonomy = (
                db.session.query(LLMKeyword, KeywordTaxonomy, LLMAnalysis.document_id)
                .join(LLMAnalysis, LLMKeyword.llm_analysis_id == LLMAnalysis.id)
                .join(
                    KeywordTaxonomy,
                    LLMKeyword.taxonomy_id == KeywordTaxonomy.id,
                    isouter=True,  # Outer join for taxonomy
                )
                .filter(LLMKeyword.llm_analysis_id.in_(llm_analysis_ids))
                .order_by(
                    LLMAnalysis.document_id,
                    LLMKeyword.relevance_score.desc(),  # Order by relevance
                )
                .all()
            )

            # Organize by document ID
            results = {doc_id: [] for doc_id in document_ids}

            for llm_kw, taxonomy, doc_id_from_query in keywords_with_taxonomy:
                # LLMKeyword.relevance_score is BigInteger (0-100), convert back to float (0.0-1.0)
                relevance_score_float = (
                    float(llm_kw.relevance_score) / 100.0
                    if llm_kw.relevance_score is not None
                    else 0.0
                )

                term_display = taxonomy.term if taxonomy else llm_kw.keyword
                primary_cat_display = (
                    taxonomy.primary_category if taxonomy else llm_kw.category
                )
                subcat_display = taxonomy.subcategory if taxonomy else None

                results[doc_id_from_query].append(
                    {
                        "id": taxonomy.id if taxonomy else None,
                        "term": term_display,
                        "primary_category": primary_cat_display,
                        "subcategory": subcat_display,
                        "relevance_score": relevance_score_float,
                    }
                )
            return results

        except Exception as e:
            logger.error(
                f"Error getting bulk keywords for documents {document_ids}: {str(e)}"
            )
            return {doc_id: [] for doc_id in document_ids}
