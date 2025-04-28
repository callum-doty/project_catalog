# app/models/__init__.py
from .models import *
from app.extensions import db
from .keyword_models import KeywordTaxonomy, KeywordSynonym, DocumentKeyword, SearchFeedback
from .scoring_models import DocumentScorecard

__all__ = [
    "Document", "BatchJob", "LLMAnalysis", "ExtractedText", 
    "DesignElement", "Classification", "LLMKeyword", "Client",
    "KeywordTaxonomy", "KeywordSynonym", "DocumentKeyword", "SearchFeedback", 
    "DocumentScorecard"
]