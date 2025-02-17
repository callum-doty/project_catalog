from minio import Minio
import os
from urllib3 import PoolManager
import io
import redis
import hashlib
import logging

logger = logging.getLogger(__name__)

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
            self._client = Minio(
                endpoint="minio:9000",
                access_key=os.getenv("MINIO_ACCESS_KEY", "minioaccess"),
                secret_key=os.getenv("MINIO_SECRET_KEY", "miniosecret"),
                secure=False,
                http_client=http_client
            )
            self.bucket = os.getenv("MINIO_BUCKET", "documents")
            self.redis_client = redis.Redis(host='redis', port=6379, db=1)
            self.cache_ttl = 3600  # 1 hour
            
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
    
    @property
    def client(self):
        return self._client

    def _get_cache_key(self, filename):
        """Generate a cache key for a filename"""
        return f"minio:{hashlib.md5(filename.encode()).hexdigest()}"

    def upload_file(self, filepath, filename):
        """Upload file to MinIO and invalidate cache"""
        try:
            self.client.fput_object(
                bucket_name=self.bucket,
                object_name=filename,
                file_path=filepath
            )
            
            # Invalidate cache
            cache_key = self._get_cache_key(filename)
            self.redis_client.delete(cache_key)
            
            return f"{self.bucket}/{filename}"
        except Exception as e:
            logger.error(f"MinIO upload failed: {str(e)}")
            raise

    def get_file(self, filename):
        """Get file with caching"""
        cache_key = self._get_cache_key(filename)
        
        # Try to get from cache
        cached_data = self.redis_client.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # Get from MinIO
            data = io.BytesIO()
            response = self.client.get_object(self.bucket, filename)
            for d in response.stream(32*1024):
                data.write(d)
            data.seek(0)
            file_data = data.getvalue()
            
            # Cache the result
            self.redis_client.setex(cache_key, self.cache_ttl, file_data)
            
            return file_data
        except Exception as e:
            logger.error(f"MinIO download failed: {str(e)}")
            raise

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
            logger.error(f"MinIO download failed: {str(e)}")
            raise