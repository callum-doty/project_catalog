# app/routes/main_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from app.services.storage_service import MinIOStorage
from app.extensions import db 
from app.models.models import Document

main_routes = Blueprint('main_routes', __name__, template_folder='../templates')
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
        
        # Import task here to avoid circular import
        from tasks.document_tasks import process_document
        process_document.delay(filename, minio_path, document.id)
        
        os.remove(temp_path)
        flash('File uploaded successfully', 'success')
        return redirect(url_for('main_routes.index'))

    except Exception as e:
        flash(f'Error uploading file: {str(e)}', 'error')
        return redirect(url_for('main_routes.index'))