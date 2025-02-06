# tests/conftest.py

import pytest
from app import create_app
from app.extensions import db as _db
import os

@pytest.fixture
def app():
    # Set test configurations
    os.environ['DROPBOX_ACCESS_TOKEN'] = 'test_token'
    os.environ['DROPBOX_FOLDER_PATH'] = '/test'
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://custom_user:strong_password@db:5432/test_db'
    
    app = create_app()
    return app

@pytest.fixture
def db(app):
    """Database fixture for tests."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()