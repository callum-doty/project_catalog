from minio import Minio
from minio.error import S3Error
import os
import shutil
from urllib3 import PoolManager
import io
import logging
from datetime import timedelta


class LocalFileStorage:
    def __init__(self, base_path="/tmp/mock_storage"):
        self.base_path = base_path
        self.logger = logging.getLogger(__name__)
        os.makedirs(self.base_path, exist_ok=True)

    def bucket_exists(self, bucket_name):
        self.logger.info(
            f"Local storage: Checking if bucket '{bucket_name}' exists (always true)."
        )
        return True

    def make_bucket(self, bucket_name):
        self.logger.info(f"Local storage: Creating bucket '{bucket_name}'.")
        os.makedirs(os.path.join(self.base_path, bucket_name), exist_ok=True)

    def upload_file(self, filepath, filename):
        self.logger.info(f"Local storage: Uploading '{filepath}' to '{filename}'.")
        # Store in documents bucket by default
        dest_path = os.path.join(self.base_path, "documents", filename)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(filepath, dest_path)
        return dest_path

    def fput_object(self, bucket_name, object_name, file_path):
        self.logger.info(
            f"Local storage: fput_object from '{file_path}' to '{object_name}'."
        )
        dest_path = os.path.join(self.base_path, bucket_name, object_name)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(file_path, dest_path)

    def get_file(self, filename):
        self.logger.info(f"Local storage: Getting file '{filename}'.")
        # Try both with and without bucket prefix
        file_path = os.path.join(self.base_path, filename)
        if not os.path.exists(file_path):
            # Try with documents bucket prefix
            file_path = os.path.join(self.base_path, "documents", filename)
            if not os.path.exists(file_path):
                self.logger.error(f"File not found in storage: {filename}")
                return None
        with open(file_path, "rb") as f:
            return f.read()

    def get_object(self, bucket_name, object_name):
        self.logger.info(
            f"Local storage: get_object for '{object_name}' in bucket '{bucket_name}'."
        )
        file_path = os.path.join(self.base_path, bucket_name, object_name)
        if not os.path.exists(file_path):
            raise S3Error(
                code="NoSuchKey",
                message="No such key",
                resource="",
                request_id="",
                host_id="",
                response=None,
            )
        return open(file_path, "rb")

    def download_file(self, filename, download_path):
        self.logger.info(
            f"Local storage: Downloading '{filename}' to '{download_path}'."
        )
        # Try both with and without bucket prefix
        src_path = os.path.join(self.base_path, filename)
        if not os.path.exists(src_path):
            # Try with documents bucket prefix
            src_path = os.path.join(self.base_path, "documents", filename)
            if not os.path.exists(src_path):
                self.logger.error(f"File not found for download: {filename}")
                raise FileNotFoundError(f"File not found: {filename}")
        shutil.copy(src_path, download_path)
        return download_path

    def list_files(self):
        self.logger.info("Local storage: Listing files.")
        files = []
        for root, _, filenames in os.walk(self.base_path):
            for filename in filenames:
                files.append(
                    os.path.relpath(os.path.join(root, filename), self.base_path)
                )
        return files

    def get_presigned_url(self, object_name, bucket_name=None, expires_seconds=3600):
        self.logger.info(
            f"Local storage: Generating presigned URL for '{object_name}'."
        )
        return f"file://{os.path.join(self.base_path, object_name)}"

    def stat_object(self, bucket_name, object_name):
        self.logger.info(
            f"Local storage: stat_object for '{object_name}' in bucket '{bucket_name}'."
        )
        file_path = os.path.join(self.base_path, bucket_name, object_name)
        if not os.path.exists(file_path):
            raise S3Error(
                code="NoSuchKey",
                message="No such key",
                resource="",
                request_id="",
                host_id="",
                response=None,
            )
        return os.stat(file_path)


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
            self.logger = logging.getLogger(__name__)
            flask_env = os.getenv("FLASK_ENV")

            use_minio_in_dev = os.getenv("USE_MINIO_IN_DEV", "").lower() in [
                "true",
                "1",
                "yes",
            ]
            if flask_env == "development" and not use_minio_in_dev:
                self.logger.info("Development: Using LocalFileStorage")
                self._client = LocalFileStorage()
                self.bucket = "documents"
                return

            self.shared_http_pool = PoolManager(timeout=10.0, retries=3)
            self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioaccess")
            self.secret_key = os.getenv("MINIO_SECRET_KEY", "miniosecret")

            if flask_env == "development":
                endpoint_to_use = "minio:9000"
                minio_secure = False
                self.logger.info(
                    f"Development: Using Minio endpoint: {endpoint_to_use}"
                )
            else:  # production
                minio_internal_s3_host = os.getenv("MINIO_INTERNAL_S3_HOST")
                minio_internal_s3_port = os.getenv("MINIO_INTERNAL_S3_PORT")
                if minio_internal_s3_host and minio_internal_s3_port:
                    endpoint_to_use = (
                        f"{minio_internal_s3_host}:{minio_internal_s3_port}"
                    )
                    minio_secure = False
                    self.logger.info(
                        f"Production: Using Minio endpoint: {endpoint_to_use}"
                    )
                else:
                    self.logger.error(
                        "Production environment variables for Minio are not set."
                    )
                    endpoint_to_use = None

            if endpoint_to_use:
                self._client = Minio(
                    endpoint=endpoint_to_use,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=minio_secure,
                    http_client=self.shared_http_pool,
                )
                self.bucket = os.getenv("S3_BUCKET_NAME", "documents")

                try:
                    if not self._client.bucket_exists(self.bucket):
                        self.logger.info(f"Creating bucket: {self.bucket}")
                        self._client.make_bucket(self.bucket)
                    else:
                        self.logger.info(f"Bucket exists: {self.bucket}")
                except Exception as e:
                    self.logger.error(f"Error checking/creating bucket: {str(e)}")
            else:
                self.logger.error("CRITICAL: MinIO client could not be initialized.")

    @property
    def client(self):
        return self._client

    def bucket_exists(self, bucket_name):
        """Check if bucket exists"""
        if hasattr(self._client, "bucket_exists"):
            return self._client.bucket_exists(bucket_name)
        else:
            # For LocalFileStorage
            return self._client.bucket_exists(bucket_name)

    def make_bucket(self, bucket_name):
        """Create bucket"""
        if hasattr(self._client, "make_bucket"):
            return self._client.make_bucket(bucket_name)
        else:
            # For LocalFileStorage
            return self._client.make_bucket(bucket_name)

    def upload_file(self, filepath, filename):
        """Upload file to storage"""
        if hasattr(self._client, "fput_object"):
            # Real MinIO client
            self._client.fput_object(self.bucket, filename, filepath)
            return f"{self.bucket}/{filename}"
        else:
            # LocalFileStorage
            return self._client.upload_file(filepath, filename)

    def fput_object(self, bucket_name, object_name, file_path):
        """Upload file using fput_object interface"""
        if hasattr(self._client, "fput_object"):
            return self._client.fput_object(bucket_name, object_name, file_path)
        else:
            return self._client.fput_object(bucket_name, object_name, file_path)

    def get_file(self, filename):
        """Get file data from storage"""
        if hasattr(self._client, "get_object"):
            # Real MinIO client
            try:
                response = self._client.get_object(self.bucket, filename)
                return response.read()
            except Exception as e:
                self.logger.error(f"Error getting file {filename}: {str(e)}")
                return None
        else:
            # LocalFileStorage
            return self._client.get_file(filename)

    def get_object(self, bucket_name, object_name):
        """Get object from storage"""
        if hasattr(self._client, "get_object"):
            return self._client.get_object(bucket_name, object_name)
        else:
            return self._client.get_object(bucket_name, object_name)

    def stat_object(self, bucket_name, object_name):
        """Get object statistics"""
        if hasattr(self._client, "stat_object"):
            return self._client.stat_object(bucket_name, object_name)
        else:
            return self._client.stat_object(bucket_name, object_name)

    def download_file(self, filename, download_path):
        """Download file from storage to a local path"""
        if hasattr(self._client, "fget_object"):
            # Real MinIO client
            self._client.fget_object(self.bucket, filename, download_path)
            return download_path
        else:
            # LocalFileStorage
            return self._client.download_file(filename, download_path)

    def list_files(self):
        """List all files in the bucket"""
        if hasattr(self._client, "list_objects"):
            # Real MinIO client
            objects = self._client.list_objects(self.bucket, recursive=True)
            return [obj.object_name for obj in objects]
        else:
            # LocalFileStorage
            return self._client.list_files()

    def get_presigned_url(self, object_name, bucket_name=None, expires_seconds=3600):
        """Get a presigned URL for an object"""
        if bucket_name is None:
            bucket_name = self.bucket

        if hasattr(self._client, "presigned_get_object"):
            # Real MinIO client
            from datetime import timedelta

            return self._client.presigned_get_object(
                bucket_name, object_name, expires=timedelta(seconds=expires_seconds)
            )
        else:
            # LocalFileStorage
            return self._client.get_presigned_url(
                object_name, bucket_name, expires_seconds
            )
