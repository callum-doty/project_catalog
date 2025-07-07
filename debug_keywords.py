#!/usr/bin/env python3

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.catalog import create_app, db
from src.catalog.models import Document, LLMAnalysis, LLMKeyword, KeywordTaxonomy
from src.catalog.services.keyword_manager import DocumentKeywordManager


def debug_document_keywords():
    app = create_app()

    with app.app_context():
        # Find a document with the filename mentioned by the user
        doc = Document.query.filter(Document.filename.like("%Sweely%")).first()

        if not doc:
            print("Sweely document not found. Let's check all documents:")
            docs = Document.query.limit(5).all()
            for d in docs:
                print(f"ID: {d.id}, Filename: {d.filename}, Status: {d.status}")

            # Use the first document for testing regardless of status
            doc = Document.query.first()
            if not doc:
                print("No documents found at all")
                return
            print(
                f"\nUsing document for testing: ID={doc.id}, Filename={doc.filename}, Status={doc.status}"
            )

        print(
            f"Found document: ID={doc.id}, Filename={doc.filename}, Status={doc.status}"
        )

        # Check if it has LLM analysis
        if doc.llm_analysis:
            print(f"LLM Analysis ID: {doc.llm_analysis.id}")
            print(
                f"Summary: {doc.llm_analysis.summary_description[:100] if doc.llm_analysis.summary_description else 'None'}..."
            )

            # Check raw LLMKeywords
            raw_keywords = LLMKeyword.query.filter_by(
                llm_analysis_id=doc.llm_analysis.id
            ).all()
            print(f"Raw LLMKeywords count: {len(raw_keywords)}")

            for kw in raw_keywords[:5]:  # Show first 5
                print(
                    f"  - Keyword: {kw.keyword}, Category: {kw.category}, Taxonomy ID: {kw.taxonomy_id}"
                )
                if kw.taxonomy_term:
                    print(
                        f"    Taxonomy: {kw.taxonomy_term.primary_category} > {kw.taxonomy_term.subcategory} > {kw.taxonomy_term.term}"
                    )
        else:
            print("No LLM analysis found")

        # Test the DocumentKeywordManager
        print("\n--- Testing DocumentKeywordManager ---")
        keywords = DocumentKeywordManager.get_document_keywords(doc.id)
        print(f"DocumentKeywordManager returned {len(keywords)} keywords:")
        for kw in keywords:
            print(f"  - {kw}")

        # Test the SearchService method
        print("\n--- Testing SearchService ---")
        from src.catalog.services.search_service import SearchService

        search_service = SearchService()
        hierarchical_keywords = search_service._get_document_hierarchical_keywords(doc)
        print(
            f"SearchService returned {len(hierarchical_keywords)} hierarchical keywords:"
        )
        for kw in hierarchical_keywords:
            print(f"  - {kw}")


if __name__ == "__main__":
    debug_document_keywords()
