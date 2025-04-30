from src.catalog import db
from src.catalog.models import Document, DocumentKeyword, KeywordTaxonomy, KeywordSynonym
from datetime import datetime
import logging
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class DocumentKeywordManager:
    """Manager for document keywords with improved taxonomy integration"""

    @staticmethod
    def process_document_keywords(document_id: int, keyword_data: List[Dict[str, Any]], max_keywords: int = 10) -> bool:
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
            # Clear existing keywords for this document to avoid duplication
            existing = DocumentKeyword.query.filter_by(
                document_id=document_id).all()
            if existing:
                logger.info(
                    f"Removing {len(existing)} existing keywords for document {document_id}")
                for kw in existing:
                    db.session.delete(kw)
                db.session.commit()

            # Validate and sort keywords by relevance
            valid_keywords = []
            for idx, kw in enumerate(keyword_data):
                if not isinstance(kw, dict):
                    continue

                # Extract required fields
                term = kw.get('specific_term')
                if not term:
                    continue

                primary_category = kw.get('primary_category', '')
                subcategory = kw.get('subcategory', '')
                relevance_score = float(kw.get('relevance_score', 0.5))

                valid_keywords.append({
                    'term': term,
                    'primary_category': primary_category,
                    'subcategory': subcategory,
                    'relevance_score': relevance_score,
                    'synonyms': kw.get('synonyms', []),
                    'original_index': idx  # Preserve original order as fallback
                })

            # Sort by relevance (highest first)
            valid_keywords.sort(
                key=lambda x: x['relevance_score'], reverse=True)

            # Limit to max_keywords
            top_keywords = valid_keywords[:max_keywords]

            # Process and store each keyword
            stored_keywords = []
            for idx, kw in enumerate(top_keywords):
                try:
                    # Find or create taxonomy term
                    taxonomy_term = KeywordTaxonomy.query.filter(
                        KeywordTaxonomy.term == kw['term'],
                        KeywordTaxonomy.primary_category == kw['primary_category']
                    ).first()

                    # If no exact match, check for similar terms
                    if not taxonomy_term:
                        similar_term = KeywordTaxonomy.query.filter(
                            KeywordTaxonomy.term.ilike(f"%{kw['term']}%"),
                            KeywordTaxonomy.primary_category == kw['primary_category']
                        ).first()

                        if similar_term:
                            taxonomy_term = similar_term
                            logger.info(
                                f"Using similar taxonomy term: {similar_term.term}")
                        else:
                            # Create new term
                            taxonomy_term = KeywordTaxonomy(
                                term=kw['term'],
                                primary_category=kw['primary_category'],
                                subcategory=kw['subcategory'],
                                specific_term=kw['term']
                            )
                            db.session.add(taxonomy_term)
                            db.session.flush()  # Get the ID

                            # Add synonyms if provided
                            synonyms = kw.get('synonyms', [])
                            if synonyms:
                                for syn_text in synonyms:
                                    if syn_text:
                                        synonym = KeywordSynonym(
                                            taxonomy_id=taxonomy_term.id,
                                            synonym=syn_text
                                        )
                                        db.session.add(synonym)

                    # Create document keyword with display order
                    doc_keyword = DocumentKeyword(
                        document_id=document_id,
                        taxonomy_id=taxonomy_term.id,
                        relevance_score=kw['relevance_score'],
                        extraction_date=datetime.utcnow(),
                        display_order=idx  # Use 0-9 for the display order
                    )
                    db.session.add(doc_keyword)
                    stored_keywords.append(doc_keyword)

                except Exception as e:
                    logger.error(
                        f"Error processing keyword {kw['term']}: {str(e)}")
                    continue

            # Commit all changes
            db.session.commit()
            logger.info(
                f"Successfully stored {len(stored_keywords)} keywords for document {document_id}")

            # Verify storage
            verification_count = DocumentKeyword.query.filter_by(
                document_id=document_id).count()
            logger.info(
                f"Verification: {verification_count} keywords in database for document {document_id}")

            return True

        except Exception as e:
            logger.error(f"Error processing document keywords: {str(e)}")
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
            # Query keywords with taxonomy join, ordered by display_order
            keywords = db.session.query(
                DocumentKeyword, KeywordTaxonomy
            ).join(
                KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
            ).filter(
                DocumentKeyword.document_id == document_id
            ).order_by(
                DocumentKeyword.display_order
            ).all()

            # Format for display
            result = []
            for doc_kw, taxonomy in keywords:
                result.append({
                    'id': taxonomy.id,
                    'term': taxonomy.term,
                    'primary_category': taxonomy.primary_category,
                    'subcategory': taxonomy.subcategory,
                    'relevance_score': doc_kw.relevance_score
                })

            return result

        except Exception as e:
            logger.error(
                f"Error getting keywords for document {document_id}: {str(e)}")
            return []

    @staticmethod
    def get_bulk_document_keywords(document_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Efficiently get keywords for multiple documents at once

        Args:
            document_ids: List of document IDs

        Returns:
            Dictionary mapping document IDs to their keywords
        """
        try:
            # Single query to get all keywords for all documents
            keywords_data = db.session.query(
                DocumentKeyword, KeywordTaxonomy
            ).join(
                KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
            ).filter(
                DocumentKeyword.document_id.in_(document_ids)
            ).order_by(
                DocumentKeyword.document_id,
                DocumentKeyword.display_order
            ).all()

            # Organize by document ID
            results = {doc_id: [] for doc_id in document_ids}

            for doc_kw, taxonomy in keywords_data:
                results[doc_kw.document_id].append({
                    'id': taxonomy.id,
                    'term': taxonomy.term,
                    'primary_category': taxonomy.primary_category,
                    'subcategory': taxonomy.subcategory,
                    'relevance_score': doc_kw.relevance_score
                })

            return results

        except Exception as e:
            logger.error(f"Error getting bulk keywords: {str(e)}")
            return {doc_id: [] for doc_id in document_ids}
