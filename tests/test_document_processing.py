# tests/test_document_processing.py

import pytest
import time
import os
from datetime import datetime
from unittest.mock import MagicMock, patch
from dropbox.files import FileMetadata

from app import create_app
from app.extensions import db
from app.models.models import Document, LLMAnalysis, DesignElement, Classification, LLMKeyword, DropboxSync
from tasks.dropbox_task import sync_dropbox
from tasks.document_tasks import process_document
from app.services.dropbox_service import DropboxService

class MockFileMetadata(FileMetadata):
    """Mock Dropbox file metadata for testing"""
    def __init__(self):
        super().__init__(name="test_document.pdf",
                         path_lower="/documents/test_document.pdf",
                         id="id:12345",
                         size=1024,
                         server_modified=datetime.utcnow())

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['CELERY_TEST'] = True  # Enable eager task execution
    return app

@pytest.fixture
def mock_dropbox(monkeypatch):
    """Mock Dropbox service dependencies"""
    monkeypatch.setenv('DROPBOX_ACCESS_TOKEN', 'test_token')
    monkeypatch.setenv('DROPBOX_FOLDER_PATH', '/documents')

    # Mock MinIO upload
    with patch('app.services.storage_service.MinIOStorage.upload_file') as mock_upload:
        mock_upload.return_value = "minio_path/test_document.pdf"
        yield

    # Cleanup mocks
    db.session.query(DropboxSync).delete()
    db.session.query(Document).delete()
    db.session.commit()

def test_full_dropbox_pipeline(app, mock_dropbox):
    """
    Test complete integration flow:
    Dropbox → MinIO → Processing → Database
    """
    with app.app_context():
        test_filename = "test_document.pdf"
        doc = None
        
        try:
            # Mock Dropbox file listing
            with patch.object(DropboxService, 'list_new_files') as mock_list:
                mock_list.return_value = [MockFileMetadata()]
                
                # 1. Trigger Dropbox sync
                print("\n=== Starting Dropbox sync ===")
                result = sync_dropbox.delay()
                print(f"Sync task ID: {result.id}")
                assert result.status == "SUCCESS"

                # 2. Verify initial document creation
                doc = Document.query.filter_by(filename=test_filename).first()
                assert doc is not None, "Document not created from Dropbox sync"
                print(f"\nInitial document status: {doc.status}")
                assert doc.status == "PENDING"

                # 3. Verify MinIO upload and Dropbox sync record
                sync_record = DropboxSync.query.filter_by(document_id=doc.id).first()
                assert sync_record is not None, "Dropbox sync record missing"
                assert sync_record.status == "SYNCED"

                # 4. Trigger document processing
                print("\n=== Starting document processing ===")
                process_result = process_document.delay(
                    test_filename, 
                    f"documents/{test_filename}", 
                    doc.id
                )
                print(f"Processing task ID: {process_result.id}")

                # 5. Monitor processing status
                timeout = 60
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    db.session.refresh(doc)
                    print(f"Current status: {doc.status}")
                    
                    if doc.status in ['COMPLETED', 'FAILED']:
                        break
                    time.sleep(2)

                # 6. Final assertions
                print("\n=== Final verification ===")
                assert doc.status == "COMPLETED", f"Processing failed with status: {doc.status}"
                
                # Verify analysis data
                analysis = LLMAnalysis.query.filter_by(document_id=doc.id).first()
                assert analysis is not None, "LLM analysis missing"
                assert analysis.summary_description is not None
                
                # Verify design elements
                design = DesignElement.query.filter_by(document_id=doc.id).first()
                assert design is not None, "Design elements missing"
                
                # Verify classification
                classification = Classification.query.filter_by(document_id=doc.id).first()
                assert classification is not None, "Classification missing"
                
                # Verify keywords
                keywords = LLMKeyword.query.filter_by(llm_analysis_id=analysis.id).all()
                assert len(keywords) > 0, "No keywords extracted"

                print("\n=== All pipeline stages verified ===")

        finally:
            # Cleanup test data
            if doc and doc.id:
                try:
                    # Delete related records
                    db.session.query(LLMKeyword).filter(
                        LLMKeyword.llm_analysis_id.in_(
                            db.session.query(LLMAnalysis.id).filter_by(document_id=doc.id)
                        )
                    ).delete(synchronize_session=False)
                    
                    db.session.query(LLMAnalysis).filter_by(document_id=doc.id).delete()
                    db.session.query(DesignElement).filter_by(document_id=doc.id).delete()
                    db.session.query(Classification).filter_by(document_id=doc.id).delete()
                    db.session.query(DropboxSync).filter_by(document_id=doc.id).delete()
                    db.session.query(Document).filter_by(id=doc.id).delete()
                    db.session.commit()
                except Exception as e:
                    print(f"Cleanup error: {str(e)}")
                    db.session.rollback()

def test_failed_processing_scenario(app, mock_dropbox):
    """Test error handling in document processing pipeline"""
    with app.app_context():
        test_filename = "corrupted_file.pdf"
        
        with patch.object(DropboxService, 'list_new_files') as mock_list:
            mock_list.return_value = [MockFileMetadata(name=test_filename)]
            
            with patch('tasks.document_tasks.process_document') as mock_process:
                # Simulate processing failure
                mock_process.side_effect = Exception("PDF processing error")

                # Trigger sync and processing
                sync_dropbox.delay().get()
                doc = Document.query.filter_by(filename=test_filename).first()
                
                # Verify error handling
                assert doc.status == "FAILED"
                assert doc.filename == test_filename
                
                # Verify error logging
                failed_sync = DropboxSync.query.filter_by(document_id=doc.id).first()
                assert failed_sync.status == "SYNCED"  # Sync succeeded, processing failed

def test_duplicate_file_handling(app, mock_dropbox):
    """Test prevention of duplicate file processing"""
    with app.app_context():
        test_filename = "duplicate_file.pdf"
        
        # First sync
        with patch.object(DropboxService, 'list_new_files') as mock_list:
            mock_list.return_value = [MockFileMetadata(name=test_filename)]
            sync_dropbox.delay().get()
            
        # Second sync with same file
        with patch.object(DropboxService, 'list_new_files') as mock_list:
            mock_list.return_value = [MockFileMetadata(name=test_filename)]
            result = sync_dropbox.delay().get()
            
            # Verify no new documents created
            documents = Document.query.filter_by(filename=test_filename).all()
            assert len(documents) == 1
            assert "0 new files" in result