from minio import Minio
import os
from urllib3 import PoolManager


class MinIOStorage:
    def __init__(self):
        http_client = PoolManager(trust_env=False)
        print("Initializing Minio client with:")
        print(f"Endpoint: minio:9000")
        print(f"Access Key: {os.getenv('MINIO_ACCESS_KEY', 'minioaccess')}")
        self.client = Minio(
            endpoint="minio:9000",
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioaccess"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "miniosecret"),
            secure=False
        )

        self.bucket = os.getenv("MINIO_BUCKET", "documents")
        
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

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

    def download_file(self, filename, download_path):
        """Download file from MinIO"""
        try:
            self.client.fget_object(
                bucket_name=self.bucket,
                object_name=filename,
                file_path=download_path
            )
            return download_path
        except Exception as e:
            raise Exception(f"MinIO download failed: {str(e)}")