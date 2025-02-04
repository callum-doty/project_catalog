# app/routes/main_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from app.services.storage_service import MinIOStorage
from app.extensions import db 
from app.models.models import Document, LLMAnalysis, LLMKeyword
from sqlalchemy import or_
from tasks.document_tasks import process_document

main_routes = Blueprint('main_routes', __name__)
storage = MinIOStorage()

@main_routes.route('/')
def index():
    try:
        documents = Document.query.order_by(Document.upload_date.desc()).limit(10).all()
        return render_template('index.html', documents=documents)
    except Exception as e:
        current_app.logger.error(f"Error fetching documents: {str(e)}")
        return render_template('index.html', documents=[])

@main_routes.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('main_routes.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main_routes.index'))

    try:
        filename = secure_filename(file.filename)
        temp_path = os.path.join('/tmp', filename)
        file.save(temp_path)
        
        document = Document(
            filename=filename,
            upload_date=datetime.utcnow(),
            file_size=os.path.getsize(temp_path),
            status='PENDING',
            page_count=1
        )
        db.session.add(document)
        db.session.commit()

        minio_path = storage.upload_file(temp_path, filename)
        process_document.delay(filename, minio_path, document.id)
        
        os.remove(temp_path)
        flash('File uploaded successfully', 'success')
        return redirect(url_for('main_routes.index'))

    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash(f'Error uploading file: {str(e)}', 'error')
        return redirect(url_for('main_routes.index'))

@main_routes.route('/search')
def search_documents():
    query = request.args.get('q', '')
    current_app.logger.info(f"Search query: {query}")  # Add logging
    
    try:
        if not query:
            documents = Document.query.order_by(Document.upload_date.desc()).all()
        else:
            documents = Document.query\
                .outerjoin(LLMAnalysis)\
                .outerjoin(LLMKeyword)\
                .filter(
                    or_(
                        Document.filename.ilike(f'%{query}%'),
                        LLMAnalysis.summary_description.ilike(f'%{query}%'),
                        LLMKeyword.keyword.ilike(f'%{query}%')
                    )
                )\
                .distinct()\
                .all()
        
        current_app.logger.info(f"Found {len(documents)} documents")  # Add logging
        
        results = []
        for doc in documents:
            analysis = LLMAnalysis.query.filter_by(document_id=doc.id).first()
            keywords = LLMKeyword.query.join(LLMAnalysis).filter(LLMAnalysis.document_id == doc.id).all()
            
            results.append({
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'summary': analysis.summary_description if analysis else '',
                'keywords': [{'text': k.keyword, 'category': k.category} for k in keywords] if keywords else []
            })
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(results)
        
        return render_template('search.html', documents=results, query=query)
        
    except Exception as e:
        current_app.logger.error(f"Search error: {str(e)}")  # Add logging
        flash(f'Error performing search: {str(e)}', 'error')
        return render_template('search.html', documents=[], query=query)