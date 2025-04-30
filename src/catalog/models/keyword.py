
from src.catalog import db
from datetime import datetime
import json


class KeywordTaxonomy(db.Model):
    """
    Hierarchical taxonomy of keywords with managed vocabulary.
    This provides the structure for organizing keywords into a searchable hierarchy.
    """
    __tablename__ = 'keyword_taxonomy'
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.Text, nullable=False)
    primary_category = db.Column(db.Text, nullable=False)
    subcategory = db.Column(db.Text)
    specific_term = db.Column(db.Text)
    description = db.Column(db.Text)
    created_date = db.Column(db.DateTime(
        timezone=True), default=datetime.utcnow)

    # Self-referential relationship for hierarchy
    parent_id = db.Column(db.Integer, db.ForeignKey('keyword_taxonomy.id'))
    children = db.relationship('KeywordTaxonomy',
                               backref=db.backref('parent', remote_side=[id]),
                               cascade="all, delete-orphan")

    # Relationship to synonyms
    synonyms = db.relationship('KeywordSynonym',
                               backref='taxonomy_term',
                               cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KeywordTaxonomy {self.primary_category}/{self.subcategory}/{self.term}>"

    def to_dict(self):
        """Convert taxonomy term to dictionary with hierarchy info"""
        return {
            'id': self.id,
            'term': self.term,
            'primary_category': self.primary_category,
            'subcategory': self.subcategory,
            'specific_term': self.specific_term,
            'parent_id': self.parent_id,
            'description': self.description,
            'synonyms': [s.synonym for s in self.synonyms]
        }

    @classmethod
    def find_matching_terms(cls, search_term):
        """Find taxonomy terms matching the search term or its synonyms"""
        # Direct match on term
        direct_matches = cls.query.filter(
            cls.term.ilike(f"%{search_term}%")).all()

        # Match on synonyms
        synonym_matches = cls.query.join(KeywordSynonym).filter(
            KeywordSynonym.synonym.ilike(f"%{search_term}%")
        ).all()

        # Combine unique results
        all_matches = {
            term.id: term for term in direct_matches + synonym_matches}
        return list(all_matches.values())

    def get_all_related_terms(self):
        """Get all terms related to this one (parent, children, siblings)"""
        related = []

        # Get parent if exists
        if self.parent:
            related.append(self.parent)

        # Get siblings (other children of parent)
        if self.parent:
            siblings = KeywordTaxonomy.query.filter(
                KeywordTaxonomy.parent_id == self.parent_id,
                KeywordTaxonomy.id != self.id
            ).all()
            related.extend(siblings)

        # Get children
        related.extend(self.children)

        return related


class KeywordSynonym(db.Model):
    """
    Synonyms for taxonomy terms to support variations in search terminology.
    """
    __tablename__ = 'keyword_synonyms'
    id = db.Column(db.Integer, primary_key=True)
    taxonomy_id = db.Column(db.Integer, db.ForeignKey('keyword_taxonomy.id'))
    synonym = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<KeywordSynonym {self.synonym}>"


class DocumentKeyword(db.Model):
    """
    Enhanced keyword association for documents with hierarchical information
    and display order.
    """
    __tablename__ = 'document_keywords'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    taxonomy_id = db.Column(db.Integer, db.ForeignKey('keyword_taxonomy.id'))
    relevance_score = db.Column(db.Float)
    extraction_date = db.Column(db.DateTime(
        timezone=True), default=datetime.utcnow)
    display_order = db.Column(db.Integer, default=0)  # New field for ordering

    # Relationships
    document = db.relationship('Document', backref='document_keywords')
    taxonomy_term = db.relationship('KeywordTaxonomy')

    def __repr__(self):
        return f"<DocumentKeyword doc_id={self.document_id} term={self.taxonomy_term.term if self.taxonomy_term else 'None'} order={self.display_order}>"


class SearchFeedback(db.Model):
    """
    User feedback on search results for improving search functionality.
    """
    __tablename__ = 'search_feedback'
    id = db.Column(db.Integer, primary_key=True)
    search_query = db.Column(db.Text, nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    # 'relevant', 'not_relevant', 'missing'
    feedback_type = db.Column(db.String(50))
    feedback_date = db.Column(db.DateTime(
        timezone=True), default=datetime.utcnow)
    user_comment = db.Column(db.Text)

    # Relationship to document
    document = db.relationship('Document')

    def __repr__(self):
        return f"<SearchFeedback query='{self.search_query}' type='{self.feedback_type}'>"
