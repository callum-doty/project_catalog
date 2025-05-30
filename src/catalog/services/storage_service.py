from minio import Minio
from minio.error import S3Error  # Import S3Error
import os
from urllib3 import PoolManager
import io
import logging
from datetime import timedelta


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

            # Determine endpoint with production-specific override if MINIO_ENDPOINT is missing
            minio_internal_host_env = os.getenv("MINIO_INTERNAL_HOST")
            # MINIO_INTERNAL_PORT is no longer used from env, port is fixed to 9000 for internal comms
            minio_endpoint_env = os.getenv("MINIO_ENDPOINT")  # Fallback
            fixed_internal_minio_port = (
                "9000"  # MinIO S3 API is now fixed to this port internally
            )
            minio_url_env = os.getenv("MINIO_URL")  # For local dev primarily
            flask_env = os.getenv("FLASK_ENV")

            minio_secure = False
            endpoint_to_use = None

            if flask_env == "production":
                self.logger.info(
                    f"Prod Mode Check: MINIO_INTERNAL_HOST='{minio_internal_host_env}', MINIO_ENDPOINT='{minio_endpoint_env}'"
                )
                if minio_internal_host_env:
                    self.logger.info(
                        f"Using MINIO_INTERNAL_HOST: {minio_internal_host_env} with fixed internal port: {fixed_internal_minio_port}"
                    )
                    # Render's internal hostnames are usually just the host, no scheme.
                    # Communication within Render's private network is typically HTTP.
                    endpoint_to_use = (
                        f"{minio_internal_host_env}:{fixed_internal_minio_port}"
                    )
                    minio_secure = False  # Assume http for internal host
                elif minio_endpoint_env:
                    self.logger.info(
                        f"Falling back to MINIO_ENDPOINT: {minio_endpoint_env}"
                    )
                    if minio_endpoint_env.startswith("https://"):
                        endpoint_to_use = minio_endpoint_env.replace("https://", "")
                        minio_secure = True
                    elif minio_endpoint_env.startswith("http://"):
                        endpoint_to_use = minio_endpoint_env.replace("http://", "")
                        minio_secure = False
                    else:
                        endpoint_to_use = minio_endpoint_env  # Assume host:port
                else:
                    self.logger.warning(
                        "Neither MINIO_INTERNAL_HOST nor MINIO_ENDPOINT set in production. Defaulting to 'minio-storage:{fixed_internal_minio_port}'."
                    )
                    endpoint_to_use = f"minio-storage:{fixed_internal_minio_port}"
                    minio_secure = False
            else:  # Local development or other environments
                raw_local_endpoint = (
                    minio_endpoint_env
                    or minio_url_env
                    or f"minio:{fixed_internal_minio_port}"
                )
                if raw_local_endpoint.startswith("https://"):
                    endpoint_to_use = raw_local_endpoint.replace("https://", "")
                    minio_secure = True
                elif raw_local_endpoint.startswith("http://"):
                    endpoint_to_use = raw_local_endpoint.replace("http://", "")
                    minio_secure = False
                else:
                    endpoint_to_use = raw_local_endpoint

            access_key = os.getenv("MINIO_ACCESS_KEY", "minioaccess")
            secret_key = os.getenv("MINIO_SECRET_KEY", "miniosecret")

            # Using print for guaranteed output, and logger
            print(f"DEBUG_PRINT: FLASK_ENV from env: '{flask_env}'")
            print(
                f"DEBUG_PRINT: MINIO_INTERNAL_HOST from env: '{minio_internal_host_env}'"
            )
            # MINIO_INTERNAL_PORT print removed
            print(
                f"DEBUG_PRINT: MINIO_ENDPOINT (fallback) from env: '{minio_endpoint_env}'"
            )
            print(f"DEBUG_PRINT: MINIO_URL from env: '{minio_url_env}'")
            print(
                f"DEBUG_PRINT: Resolved endpoint for Minio client: {endpoint_to_use}, secure: {minio_secure}"
            )

            self.logger.info(f"DEBUG_LOGGER: FLASK_ENV from env: '{flask_env}'")
            self.logger.info(
                f"DEBUG_LOGGER: MINIO_INTERNAL_HOST from env: '{minio_internal_host_env}'"
            )
            # MINIO_INTERNAL_PORT log removed
            self.logger.info(
                f"DEBUG_LOGGER: MINIO_ENDPOINT (fallback) from env: '{minio_endpoint_env}'"
            )
            self.logger.info(f"DEBUG_LOGGER: MINIO_URL from env: '{minio_url_env}'")
            self.logger.info(
                f"Initializing Minio client with resolved endpoint: {endpoint_to_use}, secure: {minio_secure}"
            )

            self._client = Minio(
                endpoint=endpoint_to_use,
                access_key=access_key,
                secret_key=secret_key,
                secure=minio_secure,  # Dynamically set based on parsed scheme
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
            except S3Error as s3_err:
                if s3_err.code == "NoSuchKey":
                    self.logger.warning(
                        f"File {filename} not found in MinIO (NoSuchKey). Returning placeholder."
                    )
                    return self._get_placeholder_image()
                else:
                    # Other S3 errors (permissions, etc.)
                    self.logger.error(
                        f"S3 error calling stat_object for {filename} in MinIO: {s3_err.code} - {str(s3_err)}"
                    )
                    return None  # Return None on other S3 errors during stat
            except Exception as e:  # Catch other exceptions like connection errors
                self.logger.error(
                    f"Non-S3 error (e.g., connection issue) calling stat_object for {filename} in MinIO: {str(e)}",
                    exc_info=True,
                )
                return None  # Return None on other errors during stat

            # If stat_object was successful, proceed to get the object
            data = io.BytesIO()
            # This get_object call can also raise S3Error or connection errors
            response = self.client.get_object(self.bucket, filename)

            for d in response.stream(32 * 1024):
                data.write(d)
            data.seek(0)

            self.logger.info(f"Successfully retrieved file: {filename}")
            return data.getvalue()
        # This outer except block will catch errors from the get_object call itself,
        # or re-raised errors from the stat_object block.
        except S3Error as s3_err_get:
            self.logger.error(
                f"MinIO S3 error during get_object for {filename}: {s3_err_get.code} - {str(s3_err_get)}",
                exc_info=True,
            )
            return None  # Return None on S3 errors during get_object
        except Exception as e_get:
            self.logger.error(
                f"MinIO non-S3 error (e.g. connection) during get_object for {filename}: {str(e_get)}",
                exc_info=True,
            )
            return None  # Return None on other errors during get_object

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

    def get_presigned_url(self, filename, expires_seconds=3600):
        """Get a presigned URL for a file in MinIO"""
        try:
            # Ensure client is initialized (though singleton should handle this)
            if not self._client:
                self.logger.warning(
                    "MinIO client not initialized in get_presigned_url, attempting re-init."
                )
                self._init_client()

            if not self._client:  # Still not initialized
                self.logger.error(
                    "MinIO client failed to initialize for get_presigned_url."
                )
                return None

            url = self._client.presigned_get_object(
                self.bucket, filename, expires=timedelta(seconds=expires_seconds)
            )
            self.logger.info(f"Successfully generated presigned URL for {filename}")
            return url
        except Exception as e:
            self.logger.error(
                f"Error generating presigned URL for {filename}: {str(e)}",
                exc_info=True,
            )
            return None
