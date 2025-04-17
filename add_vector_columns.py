# add_vector_columns.py
import sys
import os
from app import create_app
from app.extensions import db
from sqlalchemy import text

def add_vector_columns():
    app = create_app()
    with app.app_context():
        # Create the vector extension if it doesn't exist
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        
        # Check if the columns already exist
        inspect = db.inspect(db.engine)
        doc_columns = [c['name'] for c in inspect.get_columns('documents')]
        analysis_columns = [c['name'] for c in inspect.get_columns('llm_analysis')]
        
        # Add vector column to documents if needed
        if 'embeddings' not in doc_columns:
            print("Adding embeddings column to documents table...")
            db.session.execute(text("ALTER TABLE documents ADD COLUMN embeddings vector(1536);"))
        
        # Add vector column to llm_analysis if needed
        if 'embeddings' not in analysis_columns:
            print("Adding embeddings column to llm_analysis table...")
            db.session.execute(text("ALTER TABLE llm_analysis ADD COLUMN embeddings vector(1536);"))
        
        # Create indexes for fast vector similarity search
        db.session.execute(text(
            "CREATE INDEX IF NOT EXISTS documents_embeddings_idx "
            "ON documents USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100)"
        ))
        
        db.session.execute(text(
            "CREATE INDEX IF NOT EXISTS llm_analysis_embeddings_idx "
            "ON llm_analysis USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100)"
        ))
        
        # Commit the changes
        db.session.commit()
        
        print("Vector columns and indexes added successfully!")

if __name__ == "__main__":
    add_vector_columns()