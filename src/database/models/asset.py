# src/database/models/asset.py
from src.database.models.asset import Asset
from flask import Blueprint, render_template
from app import db
from datetime import datetime


class Asset(db.Model):
    """Model for storing design assets metadata"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    campaign_name = db.Column(db.String(255))
    client_name = db.Column(db.String(255))
    color_scheme = db.Column(db.String(255))
    theme = db.Column(db.String(255))

    def __repr__(self):
        return f'<Asset {self.filename}>'


# src/api/endpoints/main.py

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Render the main page with all assets"""
    assets = Asset.query.all()
    return render_template('index.html', assets=assets)
