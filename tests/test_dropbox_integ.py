# tests/test_dropbox_integ.py

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from app.services.dropbox_service import DropboxService
from app.models.models import Document, DropboxSync
from app.extensions import db
from dropbox.files import FileMetadata

@pytest.fixture
def mock_dropbox():
    with patch('dropbox.Dropbox') as mock_dbx:
        # Create a mock response for files_list_folder
        mock_file = FileMetadata(
            id='id1',
            name='test_document.pdf',
            path_display='/test/test_document.pdf',
            client_modified=datetime.now(),
            server_modified=datetime.now(),
            size=1024,
            rev='123456789',  # Rev must be at least 9 characters
            is_downloadable=True,
            content_hash='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'  # Must be 32 chars
        )
        mock_dbx.return_value.files_list_folder.return_value.entries = [mock_file]
        
        # Mock the file download response
        mock_response = Mock()
        mock_response.content = b'test file content'
        mock_dbx.return_value.files_download.return_value = (mock_file, mock_response)
        
        yield mock_dbx

@pytest.fixture
def mock_minio():
    with patch('app.services.storage_service.MinIOStorage') as mock_storage:
        mock_storage.return_value.upload_file.return_value = 'documents/test_document.pdf'
        yield mock_storage

@pytest.fixture
def app_context(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()

def test_list_new_files(mock_dropbox, app_context):
    service = DropboxService()
    new_files = service.list_new_files()
    
    assert len(new_files) == 1
    assert new_files[0].name == 'test_document.pdf'
    assert new_files[0].path_display == '/test/test_document.pdf'

def test_process_file(mock_dropbox, mock_minio, app_context):
    service = DropboxService()
    file_metadata = mock_dropbox.return_value.files_list_folder.return_value.entries[0]
    
    # Process the file
    document, minio_path = service.process_file(file_metadata)
    
    # Verify document was created
    assert document is not None
    assert document.filename == 'test_document.pdf'
    assert document.status == 'PENDING'
    
    # Verify sync record was created
    db.session.refresh(document)  # Refresh the document from the database
    sync_record = DropboxSync.query.filter_by(document_id=document.id).first()
    assert sync_record is not None
    assert sync_record.dropbox_file_id == 'id1'
    assert sync_record.dropbox_path == '/test/test_document.pdf'

def test_duplicate_file_handling(mock_dropbox, mock_minio, app_context):
    service = DropboxService()
    file_metadata = mock_dropbox.return_value.files_list_folder.return_value.entries[0]
    
    # Process the same file twice
    doc1, path1 = service.process_file(file_metadata)
    doc2, path2 = service.process_file(file_metadata)
    
    # Second attempt should return None due to duplicate file_id
    assert doc1 is not None
    assert doc2 is None

def test_error_handling(mock_dropbox, mock_minio, app_context):
    # Simulate Dropbox API error
    mock_dropbox.return_value.files_download.side_effect = Exception("API Error")
    
    service = DropboxService()
    file_metadata = mock_dropbox.return_value.files_list_folder.return_value.entries[0]
    
    document, minio_path = service.process_file(file_metadata)
    assert document is None
    assert minio_path is None