from datetime import datetime
from src.catalog import db


class DocumentScorecard(db.Model):
    """Stores quality assessment scores for document processing"""
    __tablename__ = 'document_scorecards'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey(
        'documents.id'), nullable=False)

    # Batch 1 scores (40 points total)
    metadata_score = db.Column(db.Integer, default=0)  # Out of 20
    text_extraction_score = db.Column(db.Integer, default=0)  # Out of 20

    # Batch 2 scores (35 points total)
    classification_score = db.Column(db.Integer, default=0)  # Out of 10
    entity_score = db.Column(db.Integer, default=0)  # Out of 10
    design_score = db.Column(db.Integer, default=0)  # Out of 15

    # Batch 3 scores (25 points total)
    keyword_score = db.Column(db.Integer, default=0)  # Out of 15
    communication_score = db.Column(db.Integer, default=0)  # Out of 10

    # Overall quality indicators
    total_score = db.Column(db.Integer, default=0)  # Out of 100
    requires_review = db.Column(db.Boolean, default=False)
    review_reason = db.Column(db.Text)

    # Processing success indicators
    batch1_success = db.Column(db.Boolean, default=False)
    batch2_success = db.Column(db.Boolean, default=False)
    batch3_success = db.Column(db.Boolean, default=False)

    # Component-specific flags
    metadata_flags = db.Column(db.Text)  # JSON string of specific issues
    text_flags = db.Column(db.Text)  # JSON string of specific issues
    classification_flags = db.Column(db.Text)  # JSON string of specific issues
    entity_flags = db.Column(db.Text)  # JSON string of specific issues
    design_flags = db.Column(db.Text)  # JSON string of specific issues
    keyword_flags = db.Column(db.Text)  # JSON string of specific issues
    communication_flags = db.Column(db.Text)  # JSON string of specific issues

    # Review and feedback
    reviewed = db.Column(db.Boolean, default=False)
    review_date = db.Column(db.DateTime(timezone=True))
    reviewer_notes = db.Column(db.Text)
    corrections_made = db.Column(db.Text)  # JSON string of corrections

    # Timestamps
    created_date = db.Column(db.DateTime(
        timezone=True), default=datetime.utcnow)
    updated_date = db.Column(db.DateTime(timezone=True),
                             default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to document - REMOVE THE BACKREF HERE
    # We'll just use the relationship defined in Document class
    document = db.relationship('Document')  # No backref parameter

    def __repr__(self):
        return f"<DocumentScorecard document_id={self.document_id} score={self.total_score}>"

    def calculate_total_score(self):
        """Calculate the total score based on component scores"""
        self.total_score = (
            self.metadata_score +
            self.text_extraction_score +
            self.classification_score +
            self.entity_score +
            self.design_score +
            self.keyword_score +
            self.communication_score
        )

        # Set review flag if score is below threshold
        if self.total_score < 70:
            self.requires_review = True
            self.review_reason = "Total score below threshold (70)"

        return self.total_score

    def check_batch_success(self):
        """Check if each batch met minimum success criteria"""
        # Batch 1 (needs 20/40 points)
        batch1_score = self.metadata_score + self.text_extraction_score
        self.batch1_success = batch1_score >= 20

        # Batch 2 (needs 18/35 points)
        batch2_score = self.classification_score + self.entity_score + self.design_score
        self.batch2_success = batch2_score >= 18

        # Batch 3 (needs 15/25 points)
        batch3_score = self.keyword_score + self.communication_score
        self.batch3_success = batch3_score >= 15

        return {
            'batch1': self.batch1_success,
            'batch2': self.batch2_success,
            'batch3': self.batch3_success
        }

    def to_dict(self):
        """Convert scorecard to dictionary for API responses"""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'scores': {
                'metadata': self.metadata_score,
                'text_extraction': self.text_extraction_score,
                'classification': self.classification_score,
                'entity': self.entity_score,
                'design': self.design_score,
                'keyword': self.keyword_score,
                'communication': self.communication_score,
                'total': self.total_score
            },
            'success': {
                'batch1': self.batch1_success,
                'batch2': self.batch2_success,
                'batch3': self.batch3_success,
                'overall': self.batch1_success and (self.batch2_success or self.batch3_success)
            },
            'review': {
                'required': self.requires_review,
                'reason': self.review_reason,
                'completed': self.reviewed,
                'date': self.review_date.isoformat() if self.review_date else None
            },
            'created_date': self.created_date.isoformat(),
            'updated_date': self.updated_date.isoformat()
        }
