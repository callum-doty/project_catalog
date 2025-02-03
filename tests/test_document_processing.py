# tests/test_document_processing.py

import pytest
from app import create_app
from app.extensions import db
from app.models.models import Document, LLMAnalysis, DesignElement, Classification, LLMKeyword
import time
from datetime import datetime

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

def test_document_processing(app):
    """
    Test the core document processing pipeline:
    1. Pull from MinIO
    2. Send to LLM
    3. Store metadata in database
    """
    with app.app_context():
        try:
            # 1. Create document record
            test_filename = 'Cruz_G03_Negative_Agony-PRESS.pdf'
            doc = Document(
                filename=test_filename,
                upload_date=datetime.utcnow(),
                file_size=4012011,  # Actual file size
                status='PENDING',
                page_count=1
            )
            db.session.add(doc)
            db.session.commit()
            
            # 2. Process document
            from tasks.document_tasks import process_document
            print(f"\nStarting document processing for {test_filename}...")
            result = process_document.apply(args=[test_filename, f"documents/{test_filename}", doc.id])
            print(f"Task ID: {result.id}")
            
            # 3. Wait for processing to complete
            timeout = 120  # Increased timeout for full processing
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                db.session.refresh(doc)
                print(f"Status: {doc.status}")
                if doc.status in ['COMPLETED', 'FAILED']:
                    break
                time.sleep(5)  # Longer sleep interval
                
            print(f"\nFinal status: {doc.status}")
            
            # 4. Verify results
            assert doc.status != 'FAILED', "Document processing failed"
            assert doc.status == 'COMPLETED', f"Processing incomplete. Status: {doc.status}"
            
            # 5. Check metadata was stored
            analysis = LLMAnalysis.query.filter_by(document_id=doc.id).first()
            assert analysis is not None, "No LLM analysis created"
            if analysis:
                print(f"\nAnalysis summary: {analysis.summary_description}")
            
            design = DesignElement.query.filter_by(document_id=doc.id).first()
            assert design is not None, "No design elements created"
            
            classification = Classification.query.filter_by(document_id=doc.id).first()
            assert classification is not None, "No classification created"
            
        finally:
            # Cleanup test data
            if 'doc' in locals() and doc.id:
                try:
                    db.session.query(LLMKeyword).filter(
                        LLMKeyword.llm_analysis_id.in_(
                            db.session.query(LLMAnalysis.id).filter_by(document_id=doc.id)
                        )
                    ).delete(synchronize_session=False)
                    db.session.query(LLMAnalysis).filter_by(document_id=doc.id).delete()
                    db.session.query(DesignElement).filter_by(document_id=doc.id).delete()
                    db.session.query(Classification).filter_by(document_id=doc.id).delete()
                    db.session.query(Document).filter_by(id=doc.id).delete()
                    db.session.commit()
                except Exception as e:
                    print(f"Cleanup error: {str(e)}")
                    db.session.rollback()