from src.database.models.asset import Asset
from src.api import db


class AssetRepository:
    """Repository for handling Asset database operations"""

    def get_all(self):
        """Retrieve all assets"""
        return Asset.query.all()

    def get_by_id(self, id):
        """Retrieve an asset by ID"""
        return Asset.query.get_or_404(id)

    def create(self, data):
        """Create a new asset"""
        asset = Asset(**data)
        db.session.add(asset)
        db.session.commit()
        return asset

    def update(self, id, data):
        """Update an existing asset"""
        asset = self.get_by_id(id)
        for key, value in data.items():
            setattr(asset, key, value)
        db.session.commit()
        return asset
