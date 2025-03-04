# app/services/storage_service.py
import os
import io
import boto3
from botocore.exceptions import ClientError
from urllib3 import PoolManager
import logging

logger = logging.getLogger(__name__)

class StorageService:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StorageService, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance
    
    def _init_client(self):
        if self._client is None:
            # Determine if we're in Railway deployment or local development
            storage_type = os.getenv("STORAGE_TYPE", "local")
            
            if storage_type == "s3":
                # Use S3 or S3-compatible service
                logger.info("Initializing S3 storage client")
                self._client = boto3.client(
                    's3',
                    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
                    aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
                    aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
                    region_name=os.getenv("S3_REGION", "us-east-1")
                )
            else:
                # Use MinIO for local development
                logger.info("Initializing MinIO client for local development")
                try:
                    from minio import Minio
                    http_client = PoolManager(timeout=5.0, retries=3)
                    self._client = Minio(
                        endpoint=os.getenv("MINIO_URL", "minio:9000"),
                        access_key=os.getenv("MINIO_ACCESS_KEY", "minioaccess"),
                        secret_key=os.getenv("MINIO_SECRET_KEY", "miniosecret"),
                        secure=False,
                        http_client=http_client
                    )
                except ImportError:
                    logger.error("MinIO package not available, falling back to S3")
                    self._client = boto3.client(
                        's3',
                        endpoint_url=os.getenv("MINIO_URL", "http://minio:9000"),
                        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioaccess"),
                        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "miniosecret")
                    )
            
            self.bucket = os.getenv("STORAGE_BUCKET", "documents")
            self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the bucket exists"""
        try:
            if isinstance(self._client, boto3.client):
                try:
                    self._client.head_bucket(Bucket=self.bucket)
                except ClientError:
                    self._client.create_bucket(Bucket=self.bucket)
            else:
                # MinIO client
                if not self._client.bucket_exists(self.bucket):
                    self._client.make_bucket(self.bucket)
            logger.info(f"Using storage bucket: {self.bucket}")
        except Exception as e:
            logger.error(f"Error ensuring bucket exists: {str(e)}")
            raise
    
    @property
    def client(self):
        return self._client

    def upload_file(self, filepath, filename):
        """Upload file to storage"""
        try:
            if isinstance(self._client, boto3.client):
                with open(filepath, 'rb') as file_data:
                    self._client.upload_fileobj(file_data, self.bucket, filename)
            else:
                # MinIO client
                self._client.fput_object(
                    bucket_name=self.bucket,
                    object_name=filename,
                    file_path=filepath
                )
            logger.info(f"Uploaded file: {filename}")
            return f"{self.bucket}/{filename}"
        except Exception as e:
            logger.error(f"Upload failed for {filename}: {str(e)}")
            raise Exception(f"Storage upload failed: {str(e)}")

    def get_file(self, filename):
        """Get file data from storage"""
        try:
            data = io.BytesIO()
            if isinstance(self._client, boto3.client):
                self._client.download_fileobj(self.bucket, filename, data)
            else:
                # MinIO client
                response = self._client.get_object(self.bucket, filename)
                for d in response.stream(32*1024):
                    data.write(d)
            data.seek(0)
            return data.getvalue()
        except Exception as e:
            logger.error(f"Download failed for {filename}: {str(e)}")
            raise Exception(f"Storage download failed: {str(e)}")

    def download_file(self, filename, download_path):
        """Download file from storage to a local path"""
        try:
            if isinstance(self._client, boto3.client):
                self._client.download_file(self.bucket, filename, download_path)
            else:
                # MinIO client
                self._client.fget_object(
                    bucket_name=self.bucket,
                    object_name=filename,
                    file_path=download_path
                )
            return download_path
        except Exception as e:
            logger.error(f"Download failed for {filename} to {download_path}: {str(e)}")
            raise Exception(f"Storage download failed: {str(e)}")

# For backward compatibility
MinIOStorage = StorageService