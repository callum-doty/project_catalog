from flask import Blueprint, render_template
from src.database.models.asset import Asset
from src.database.repositories.asset_repository import AssetRepository

bp = Blueprint('main', __name__)
repo = AssetRepository()


@bp.route('/')
def index():
    """Render the main page with all assets"""
    assets = repo.get_all()
    return render_template('index.html', assets=assets)


@bp.route('/asset/<int:id>')
def asset_detail(id):
    """Show details for a specific asset"""
    asset = repo.get_by_id(id)
    return render_template('asset_detail.html', asset=asset)
