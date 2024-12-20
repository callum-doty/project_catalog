from datetime import datetime
from src.database.db import db

# Document model


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.Text, nullable=False)
    upload_date = db.Column(db.DateTime(timezone=True),
                            nullable=False, default=datetime.utcnow)
    file_size = db.Column(db.BigInteger, nullable=False)
    page_count = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Text, nullable=False)
