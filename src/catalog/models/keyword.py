from src.catalog import db
from datetime import datetime
import json


class KeywordTaxonomy(db.Model):
    """
    Hierarchical taxonomy of keywords with managed vocabulary.
    This provides the structure for organizing keywords into a searchable hierarchy.
    """

    __tablename__ = "keyword_taxonomy"
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.Text, nullable=False)
    primary_category = db.Column(db.Text, nullable=False)
    subcategory = db.Column(db.Text)
    description = db.Column(db.Text)
    created_date = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    parent_id = db.Column(db.Integer, db.ForeignKey("keyword_taxonomy.id"))
    children = db.relationship(
        "KeywordTaxonomy",
        backref=db.backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
    )

    synonyms = db.relationship(
        "KeywordSynonym", backref="taxonomy_term", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<KeywordTaxonomy {self.primary_category}/{self.subcategory}/{self.term}>"
        )

    def to_dict(self):
        """Convert taxonomy term to dictionary with hierarchy info"""
        return {
            "id": self.id,
            "term": self.term,
            "primary_category": self.primary_category,
            "subcategory": self.subcategory,
            "parent_id": self.parent_id,
            "description": self.description,
            "synonyms": [s.synonym for s in self.synonyms],
        }

    @classmethod
    def find_matching_terms(cls, search_term):
        """Find taxonomy terms matching the search term or its synonyms"""

        direct_matches = cls.query.filter(cls.term.ilike(f"%{search_term}%")).all()

        synonym_matches = (
            cls.query.join(KeywordSynonym)
            .filter(KeywordSynonym.synonym.ilike(f"%{search_term}%"))
            .all()
        )

        all_matches = {term.id: term for term in direct_matches + synonym_matches}
        return list(all_matches.values())

    def get_all_related_terms(self):
        """Get all terms related to this one (parent, children, siblings)"""
        related = []

        if self.parent:
            related.append(self.parent)

        if self.parent:
            siblings = KeywordTaxonomy.query.filter(
                KeywordTaxonomy.parent_id == self.parent_id,
                KeywordTaxonomy.id != self.id,
            ).all()
            related.extend(siblings)

        related.extend(self.children)

        return related


class LLMKeyword(db.Model):
    """
    Represents a specific keyword or phrase mentioned in a document,
    as identified by the LLM, and maps it to the canonical taxonomy.
    """

    __tablename__ = "llm_keywords"
    id = db.Column(db.Integer, primary_key=True)
    llm_analysis_id = db.Column(
        db.Integer, db.ForeignKey("llm_analysis.id"), nullable=False
    )
    taxonomy_id = db.Column(
        db.Integer, db.ForeignKey("keyword_taxonomy.id"), nullable=True
    )
    verbatim_term = db.Column(
        db.Text, nullable=False
    )  # The actual keyword text from database
    relevance_score = db.Column(db.Float)
    created_date = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    taxonomy_term = db.relationship("KeywordTaxonomy")
    llm_analysis = db.relationship("LLMAnalysis")

    # Property to provide backward compatibility for 'keyword' access
    @property
    def keyword(self):
        return self.verbatim_term

    @keyword.setter
    def keyword(self, value):
        self.verbatim_term = value

    # Property to provide 'category' access from taxonomy relationship
    @property
    def category(self):
        if self.taxonomy_term:
            return self.taxonomy_term.primary_category
        return None

    def __repr__(self):
        return f"<LLMKeyword keyword='{self.keyword}' category='{self.category}'>"


class KeywordSynonym(db.Model):
    """
    Synonyms for taxonomy terms to support variations in search terminology.
    """

    __tablename__ = "keyword_synonyms"
    id = db.Column(db.Integer, primary_key=True)
    taxonomy_id = db.Column(db.Integer, db.ForeignKey("keyword_taxonomy.id"))
    synonym = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<KeywordSynonym {self.synonym}>"


class SearchFeedback(db.Model):
    """
    User feedback on search results for improving search functionality.
    """

    __tablename__ = "search_feedback"
    id = db.Column(db.Integer, primary_key=True)
    search_query = db.Column(db.Text, nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))

    feedback_type = db.Column(db.String(50))
    feedback_date = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    user_comment = db.Column(db.Text)

    document = db.relationship("Document")

    def __repr__(self):
        return (
            f"<SearchFeedback query='{self.search_query}' type='{self.feedback_type}'>"
        )
