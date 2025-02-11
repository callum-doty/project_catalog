# app/services/storage_service.py
from minio import Minio
import os
from urllib3 import PoolManager
import io

class MinIOStorage:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MinIOStorage, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance
    
    def _init_client(self):
        if self._client is None:
            http_client = PoolManager(timeout=5.0, retries=3)
            print("Initializing Minio client with:")
            print(f"Endpoint: minio:9000")
            print(f"Access Key: {os.getenv('MINIO_ACCESS_KEY', 'minioaccess')}")
            self._client = Minio(
                endpoint="minio:9000",
                access_key=os.getenv("MINIO_ACCESS_KEY", "minioaccess"),
                secret_key=os.getenv("MINIO_SECRET_KEY", "miniosecret"),
                secure=False,
                http_client=http_client
            )
            self.bucket = os.getenv("MINIO_BUCKET", "documents")
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
    
    @property
    def client(self):
        return self._client

    def upload_file(self, filepath, filename):
        """Upload file to MinIO"""
        try:
            self.client.fput_object(
                bucket_name=self.bucket,
                object_name=filename,
                file_path=filepath
            )
            return f"{self.bucket}/{filename}"
        except Exception as e:
            raise Exception(f"MinIO upload failed: {str(e)}")

    def get_file(self, filename):
        """Get file data from MinIO"""
        try:
            data = io.BytesIO()
            response = self.client.get_object(self.bucket, filename)
            for d in response.stream(32*1024):
                data.write(d)
            data.seek(0)
            return data.getvalue()
        except Exception as e:
            raise Exception(f"MinIO download failed: {str(e)}")

    def download_file(self, filename, download_path):
        """Download file from MinIO to a local path"""
        try:
            self.client.fget_object(
                bucket_name=self.bucket,
                object_name=filename,
                file_path=download_path
            )
            return download_path
        except Exception as e:
            raise Exception(f"MinIO download failed: {str(e)}")