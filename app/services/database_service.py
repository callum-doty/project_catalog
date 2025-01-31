from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    extracted_text = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=False)

class DatabaseService:
    def store_document(self, filename, extracted_text, summary):
        """Store document metadata in PostgreSQL"""
        doc = Document(filename=filename, extracted_text=extracted_text, summary=summary)
        db.session.add(doc)
        db.session.commit()

    def search_documents(self, query):
        """Search for documents based on extracted text"""
        return Document.query.filter(Document.extracted_text.ilike(f"%{query}%")).all()
