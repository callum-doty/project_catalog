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
        if self._client is None:  # Ensure this runs only once for the main client
            self.logger = logging.getLogger(__name__)
            # Store http_client, access_key, secret_key on self for reuse
            self.shared_http_pool = PoolManager(timeout=10.0, retries=3)
            self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioaccess")
            self.secret_key = os.getenv("MINIO_SECRET_KEY", "miniosecret")

            flask_env = os.getenv("FLASK_ENV")
            minio_secure = False
            endpoint_to_use = None

            if flask_env == "production":
                # In production (Render), use specific internal host and port from env vars
                minio_internal_s3_host = os.getenv("MINIO_INTERNAL_S3_HOST")
                minio_internal_s3_port = os.getenv("MINIO_INTERNAL_S3_PORT")

                if minio_internal_s3_host and minio_internal_s3_port:
                    endpoint_to_use = (
                        f"{minio_internal_s3_host}:{minio_internal_s3_port}"
                    )
                    minio_secure = False  # Internal traffic on Render is typically HTTP
                    self.logger.info(
                        f"Production: Using MINIO_INTERNAL_S3_HOST ({minio_internal_s3_host}) and MINIO_INTERNAL_S3_PORT ({minio_internal_s3_port}). Endpoint: {endpoint_to_use}, Secure: {minio_secure}"
                    )
                else:
                    # Fallback if the specific Render S3 host/port vars are not set (should not happen with correct render.yaml)
                    # Try the generic MINIO_ENDPOINT or MINIO_INTERNAL_HOST (assuming port 9000)
                    minio_endpoint_env = os.getenv("MINIO_ENDPOINT")
                    minio_internal_host_env = os.getenv("MINIO_INTERNAL_HOST")
                    fixed_internal_minio_port = "9000"

                    self.logger.warning(
                        f"Production: MINIO_INTERNAL_S3_HOST or MINIO_INTERNAL_S3_PORT not set. Falling back. MINIO_ENDPOINT='{minio_endpoint_env}', MINIO_INTERNAL_HOST='{minio_internal_host_env}'"
                    )
                    if minio_endpoint_env:  # e.g. http://minio-storage:9000
                        if minio_endpoint_env.startswith("http://"):
                            endpoint_to_use = minio_endpoint_env.replace("http://", "")
                        else:  # Should not happen for internal endpoint
                            endpoint_to_use = minio_endpoint_env
                        minio_secure = False
                    elif minio_internal_host_env:  # Just hostname, assume port 9000
                        endpoint_to_use = (
                            f"{minio_internal_host_env}:{fixed_internal_minio_port}"
                        )
                        minio_secure = False
                    else:  # Ultimate fallback
                        endpoint_to_use = f"minio-storage:{fixed_internal_minio_port}"
                        minio_secure = False
                    self.logger.info(
                        f"Production Fallback Endpoint: {endpoint_to_use}, Secure: {minio_secure}"
                    )

            else:
                # Local development: use MINIO_ENDPOINT or MINIO_URL or default to minio:9000
                minio_endpoint_env = os.getenv("MINIO_ENDPOINT")
                minio_url_env = os.getenv("MINIO_URL")
                # Default to minio:9000 which is common for local Docker Compose setups
                raw_local_endpoint = minio_endpoint_env or minio_url_env or "minio:9000"

                if raw_local_endpoint.startswith("https://"):
                    endpoint_to_use = raw_local_endpoint.replace("https://", "")
                    minio_secure = True
                elif raw_local_endpoint.startswith("http://"):
                    endpoint_to_use = raw_local_endpoint.replace("http://", "")
                    minio_secure = False
                else:
                    endpoint_to_use = raw_local_endpoint  # Assumes host:port format
                self.logger.info(
                    f"Local/Dev: Using endpoint {raw_local_endpoint}. Resolved to: {endpoint_to_use}, Secure: {minio_secure}"
                )

            if not endpoint_to_use:  # Should not happen if logic above is correct
                self.logger.error(
                    "CRITICAL: MinIO endpoint could not be determined. Defaulting to localhost:9000"
                )
                endpoint_to_use = "localhost:9000"
                minio_secure = False

            self.logger.info(
                f"Initializing main Minio client with endpoint: {endpoint_to_use}, secure: {minio_secure}"
            )
            # Using print for critical debug output during startup
            print(f"DEBUG_PRINT: FLASK_ENV='{flask_env}'")
            print(
                f"DEBUG_PRINT: MINIO_INTERNAL_S3_HOST='{os.getenv('MINIO_INTERNAL_S3_HOST')}'"
            )
            print(
                f"DEBUG_PRINT: MINIO_INTERNAL_S3_PORT='{os.getenv('MINIO_INTERNAL_S3_PORT')}'"
            )
            print(
                f"DEBUG_PRINT: MINIO_ENDPOINT (fallback/local)='{os.getenv('MINIO_ENDPOINT')}'"
            )
            print(
                f"DEBUG_PRINT: Final Minio client endpoint: {endpoint_to_use}, secure: {minio_secure}"
            )

            self._client = Minio(
                endpoint=endpoint_to_use,
                access_key=self.access_key,  # Use stored access key
                secret_key=self.secret_key,  # Use stored secret key
                secure=minio_secure,  # Dynamically set based on parsed scheme
                http_client=self.shared_http_pool,  # Use stored http_client
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
        """Get a presigned URL for a file in MinIO, ensuring it uses the public endpoint."""
        try:
            # Prioritize MINIO_PUBLIC_ENDPOINT, then fall back to MINIO_ENDPOINT
            public_endpoint_str = os.getenv("MINIO_PUBLIC_ENDPOINT")
            if not public_endpoint_str:
                self.logger.info(
                    "MINIO_PUBLIC_ENDPOINT not set, falling back to MINIO_ENDPOINT for presigned URL."
                )
                public_endpoint_str = os.getenv("MINIO_ENDPOINT")

            if not public_endpoint_str:
                self.logger.error(
                    "Neither MINIO_PUBLIC_ENDPOINT nor MINIO_ENDPOINT environment variable is set. Cannot generate public presigned URL."
                )
                return None

            # Parse the public endpoint string
            public_host = public_endpoint_str
            public_secure = False  # Default to False
            # Render's `property: url` for a service includes the scheme (https://)
            if public_endpoint_str.startswith("https://"):
                public_host = public_endpoint_str.replace("https://", "")
                public_secure = True
            elif public_endpoint_str.startswith(
                "http://"
            ):  # Handle http just in case, though Render usually provides https
                public_host = public_endpoint_str.replace("http://", "")
                public_secure = False

            # If the public_host still contains a port (e.g., from a local MINIO_ENDPOINT like localhost:9000),
            # Minio client handles it correctly. No need to strip it here.

            # Ensure essential attributes like self.access_key are initialized
            # This check is important if get_presigned_url could somehow be called before _init_client completes
            # for the singleton, though unlikely with current structure.
            if (
                not hasattr(self, "access_key")
                or not hasattr(self, "secret_key")
                or not hasattr(self, "shared_http_pool")
            ):
                self.logger.warning(
                    "Main client attributes not fully initialized. Attempting _init_client for MinioStorage instance."
                )
                self._init_client()  # Should ideally not re-run if _client already exists, but good for safety.
                if not hasattr(self, "access_key"):  # Still not there after re-attempt
                    self.logger.error(
                        "Failed to initialize MinioStorage attributes needed for presigned URL."
                    )
                    return None

            # Create a temporary client configured with the public endpoint
            temp_public_client = Minio(
                endpoint=public_host,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=public_secure,
                http_client=self.shared_http_pool,
                region=os.getenv("MINIO_REGION", "us-east-2"),  # Default to Ohio region
            )

            self.logger.info(
                f"Generating presigned URL for {filename} using public endpoint: {public_host}, secure: {public_secure}"
            )

            url = temp_public_client.presigned_get_object(
                self.bucket, filename, expires=timedelta(seconds=expires_seconds)
            )
            self.logger.info(
                f"Successfully generated public presigned URL for {filename}: {url}"
            )
            return url
        except Exception as e:
            self.logger.error(
                f"Error generating public presigned URL for {filename}: {str(e)}",
                exc_info=True,
            )
            return None
