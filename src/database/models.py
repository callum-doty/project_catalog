from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False,
                            default=datetime.utcnow)
    file_size = db.Column(db.BigInteger, nullable=False)
    page_count = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'upload_date': self.upload_date.isoformat(),
            'file_size': self.file_size,
            'page_count': self.page_count,
            'status': self.status
        }
