from minio import Minio
import os
from urllib3 import PoolManager
import io
import logging


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
            http_client = PoolManager(timeout=10.0, retries=3)
            # Use MINIO_ENDPOINT to match render.yaml; fallback for local dev
            endpoint = os.getenv("MINIO_ENDPOINT", os.getenv("MINIO_URL", "minio:9000"))
            access_key = os.getenv("MINIO_ACCESS_KEY", "minioaccess")
            secret_key = os.getenv("MINIO_SECRET_KEY", "miniosecret")

            # Enhanced logging for environment variables
            minio_endpoint_env = os.getenv("MINIO_ENDPOINT")
            minio_url_env = os.getenv("MINIO_URL")

            # Using print for guaranteed output, and logger
            print(f"DEBUG_PRINT: MINIO_ENDPOINT from env: '{minio_endpoint_env}'")
            print(f"DEBUG_PRINT: MINIO_URL from env: '{minio_url_env}'")
            print(f"DEBUG_PRINT: Resolved endpoint for Minio client: {endpoint}")

            self.logger.info(
                f"DEBUG_LOGGER: MINIO_ENDPOINT from env: '{minio_endpoint_env}'"
            )
            self.logger.info(f"DEBUG_LOGGER: MINIO_URL from env: '{minio_url_env}'")
            self.logger.info(
                f"Initializing Minio client with resolved endpoint: {endpoint}"
            )

            self._client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=False,  # In Render, communication is internal, often HTTP
                http_client=http_client,
            )
            # Use S3_BUCKET_NAME to match render.yaml; fallback for local dev
            self.bucket = os.getenv(
                "S3_BUCKET_NAME", os.getenv("MINIO_BUCKET", "documents")
            )

            # Make sure bucket exists
            try:
                if not self._client.bucket_exists(self.bucket):
                    self.logger.info(f"Creating bucket: {self.bucket}")
                    self._client.make_bucket(self.bucket)
                else:
                    self.logger.info(f"Bucket exists: {self.bucket}")
            except Exception as e:
                self.logger.error(f"Error checking/creating bucket: {str(e)}")

    @property
    def client(self):
        return self._client

    def upload_file(self, filepath, filename):
        """Upload file to MinIO"""
        try:
            self.logger.info(f"Uploading file to MinIO: {filename}")

            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File not found: {filepath}")

            self.client.fput_object(
                bucket_name=self.bucket, object_name=filename, file_path=filepath
            )

            # Verify the file was uploaded
            try:
                self.client.stat_object(self.bucket, filename)
                self.logger.info(f"Successfully uploaded file: {filename}")
            except Exception as e:
                self.logger.error(f"File upload verification failed: {str(e)}")
                raise

            return f"{self.bucket}/{filename}"
        except Exception as e:
            self.logger.error(f"MinIO upload failed: {str(e)}")
            raise Exception(f"MinIO upload failed: {str(e)}")

    def get_file(self, filename):
        """Get file data from MinIO"""
        try:
            self.logger.info(f"Getting file from MinIO: {filename}")

            # Check if file exists first
            try:
                self.client.stat_object(self.bucket, filename)
            except Exception as e:
                self.logger.error(f"File does not exist in MinIO: {filename}")
                # Return a default placeholder image if file doesn't exist
                return self._get_placeholder_image()

            data = io.BytesIO()
            response = self.client.get_object(self.bucket, filename)

            for d in response.stream(32 * 1024):
                data.write(d)
            data.seek(0)

            self.logger.info(f"Successfully retrieved file: {filename}")
            return data.getvalue()
        except Exception as e:
            self.logger.error(f"MinIO download failed: {str(e)}")
            # Return a default placeholder image for errors
            return self._get_placeholder_image()

    def _get_placeholder_image(self):
        """Return a placeholder image for missing files"""
        # Path to a default placeholder image in your static directory
        placeholder_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static",
            "img",
            "placeholder.png",
        )

        # If the placeholder exists, return it
        if os.path.exists(placeholder_path):
            with open(placeholder_path, "rb") as f:
                return f.read()

        # Otherwise generate a simple blank image using PIL
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (300, 300), color=(240, 240, 240))
            d = ImageDraw.Draw(img)
            d.text((100, 140), "No Image", fill=(120, 120, 120))

            img_io = io.BytesIO()
            img.save(img_io, "PNG")
            img_io.seek(0)
            return img_io.getvalue()
        except Exception:
            # If all else fails, return empty bytes
            return b""

    def download_file(self, filename, download_path):
        """Download file from MinIO to a local path"""
        try:
            self.logger.info(f"Downloading file from MinIO: {filename}")
            self.client.fget_object(
                bucket_name=self.bucket, object_name=filename, file_path=download_path
            )

            if os.path.exists(download_path):
                self.logger.info(f"Successfully downloaded file: {filename}")
                return download_path
            else:
                raise FileNotFoundError(
                    f"Download failed - file not created: {download_path}"
                )
        except Exception as e:
            self.logger.error(f"MinIO download failed: {str(e)}")
            raise Exception(f"MinIO download failed: {str(e)}")

    def list_files(self):
        """List all files in the bucket"""
        files = []
        try:
            objects = self.client.list_objects(self.bucket, recursive=True)
            for obj in objects:
                files.append(obj.object_name)
            return files
        except Exception as e:
            self.logger.error(f"Error listing MinIO files: {str(e)}")
            return []
