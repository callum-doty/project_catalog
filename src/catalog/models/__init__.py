
# Main document models
from src.catalog.models.document import (
    Document, BatchJob, LLMAnalysis, ExtractedText,
    DesignElement, Classification, LLMKeyword, Client,
    Entity, CommunicationFocus, DropboxSync
)

# Keyword and taxonomy models
from src.catalog.models.keyword import (
    KeywordTaxonomy, KeywordSynonym, DocumentKeyword, SearchFeedback
)

# Score and quality models - import after Document is loaded
from src.catalog.models.scoring import DocumentScorecard

# Export all model classes
__all__ = [
    "Document", "BatchJob", "LLMAnalysis", "ExtractedText",
    "DesignElement", "Classification", "LLMKeyword", "Client",
    "Entity", "CommunicationFocus", "KeywordTaxonomy", "KeywordSynonym",
    "DocumentKeyword", "SearchFeedback", "DocumentScorecard", "DropboxSync"
]
