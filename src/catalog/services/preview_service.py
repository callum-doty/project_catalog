import os
from pdf2image import convert_from_bytes
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from src.catalog.services.storage_service import MinIOStorage
import logging
import tempfile
from werkzeug.utils import secure_filename
import traceback
from src.catalog import cache, db
from src.catalog.constants import CACHE_TIMEOUTS, SUPPORTED_FILE_TYPES
from pathlib import Path


class LocalStorageFallback:
    """Local storage fallback when MinIO is not available"""

    def __init__(self, storage_path="./dev_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Using local storage fallback: {self.storage_path}")

    def get_file(self, filename):
        """Get file from local storage"""
        try:
            file_path = self.storage_path / filename
            if file_path.exists():
                return file_path.read_bytes()
            else:
                self.logger.warning(f"File not found in local storage: {filename}")
                return None
        except Exception as e:
            self.logger.error(f"Error reading file from local storage: {e}")
            return None

    def get_presigned_url(self, filename, bucket_name=None):
        """Get URL for local file"""
        file_path = self.storage_path / filename
        if file_path.exists():
            return f"/api/files/{filename}"
        return None


class PreviewService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Try to initialize MinIO storage, fall back to local storage if it fails
        try:
            self.storage = MinIOStorage()
            self.use_local_fallback = False
            self.logger.info("Using MinIO storage for previews")
        except Exception as e:
            self.logger.warning(f"MinIO storage failed, using local fallback: {e}")
            self.storage = LocalStorageFallback()
            self.use_local_fallback = True

        self.supported_images = SUPPORTED_FILE_TYPES["IMAGES"]
        self.supported_pdfs = SUPPORTED_FILE_TYPES["DOCUMENTS"]

    # @cache.memoize(timeout=CACHE_TIMEOUTS["PREVIEW"]) # Caching needs to consider document_id if it's part of the key
    # For now, let's remove memoize here as the key would need document_id, or make filename globally unique.
    # If filename is already globally unique and tied to a document, original caching might be fine.
    # Let's assume filename is unique enough for now for the cache key, but pass document_id to task.
    def get_preview(self, document_id, filename):  # Added document_id
        """Get preview for a file, first checking cache"""
        try:
            # Check cache first
            # Cache key might need to include document_id if filenames are not globally unique
            cache_key = f"preview:doc_{document_id}:{filename}"
            cached_preview = cache.get(cache_key)

            if cached_preview:
                self.logger.info(f"Using cached preview for {filename}")
                return cached_preview

            # If not in cache, check if a preview generation is already in progress
            in_progress_key = f"preview_in_progress:doc_{document_id}:{filename}"  # Made key more specific
            if cache.get(in_progress_key):
                self.logger.info(
                    f"Preview generation for doc_id {document_id}, filename {filename} already in progress, returning placeholder"
                )
                return self._generate_placeholder_preview("Preview being generated...")

            # Mark as in progress (1 minute timeout to prevent deadlocks)
            cache.set(in_progress_key, True, timeout=60)
            self.logger.info(f"Set {in_progress_key} in cache for doc_id {document_id}")

            # Queue background task for preview generation
            from src.catalog.tasks.preview_tasks import generate_preview

            generate_preview.delay(document_id, filename)
            self.logger.info(
                f"Queued Celery task generate_preview for doc_id {document_id}, filename {filename}"
            )

            # Attempt to generate preview synchronously for immediate display if possible,
            # but ensure _generate_preview_internal can handle document_id if needed.
            # For now, assuming _generate_preview_internal primarily uses filename for data fetching.
            # If _generate_preview_internal strictly needs document_id for fetching, its signature and calls must change.
            # The current signature is _generate_preview_internal(self, filename)
            # Let's assume filename is unique enough for storage.get_file(filename) for now.
            # If not, _generate_preview_internal needs to be refactored.
            # The Celery task also calls _generate_preview_internal(filename)

            # For now, let's call it as is, but be aware this might be a point of failure if filename isn't globally unique for fetching.
            # If this synchronous call fails and returns a placeholder, the UI will show that.
            # The async task will then (hopefully) generate the real one.
            synchronous_preview = self._generate_preview_internal(
                filename, document_id=document_id
            )
            self.logger.info(
                f"Synchronous _generate_preview_internal for doc_id {document_id} returned: {type(synchronous_preview)}"
            )

            # If a dictionary is returned, it contains an s3_key, which the frontend
            # is not equipped to handle directly. Return a placeholder and let the
            # async polling handle fetching the S3 URL.
            if isinstance(synchronous_preview, dict):
                return self._generate_placeholder_preview("Generating preview...")

            return synchronous_preview

        except Exception as e:
            self.logger.error(
                f"Preview error for doc_id {document_id}, filename {filename}: {str(e)}",
                exc_info=True,
            )
            return self._generate_placeholder_preview("Error generating preview")

    def _generate_image_preview(self, file_data, filename):
        """Generate preview for image files"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                temp_path = temp_file.name
                temp_file.write(file_data)

            try:
                # Open the image file
                image = Image.open(temp_path)

                # Convert RGBA to RGB if necessary
                if image.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[-1])
                    image = background

                # Resize maintaining aspect ratio
                max_size = (300, 300)
                image.thumbnail(max_size, Image.LANCZOS)

                # Save as JPEG for smaller size
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG", quality=85, optimize=True)
                img_str = base64.b64encode(buffered.getvalue()).decode()

                self.logger.info(
                    f"Successfully generated image preview, size: {len(img_str)} chars"
                )
                return f"data:image/jpeg;base64,{img_str}"
            except Exception as e:
                self.logger.error(f"Error processing image: {str(e)}")
                return self._generate_placeholder_preview(
                    f"Error processing: {os.path.basename(filename)}"
                )
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            self.logger.error(
                f"Image preview generation error: {str(e)}", exc_info=True
            )
            return self._generate_placeholder_preview(
                f"Error: {os.path.basename(filename)}"
            )

    def _generate_pdf_preview(self, file_data, filename):
        """Generate preview for PDF files"""
        try:
            self.logger.info(
                f"Starting PDF preview for {filename}. File data type: {type(file_data)}, Length: {len(file_data) if file_data else 'N/A'}"
            )
            if file_data and len(file_data) > 8:
                self.logger.info(
                    f"First 8 bytes of file_data for {filename}: {file_data[:8]}"
                )
            elif file_data:
                self.logger.info(f"File_data for {filename} is too short: {file_data}")
            else:
                self.logger.warning(
                    f"File_data for {filename} is None or empty. Triggering fallback."
                )
                return "fallback_to_direct_url"  # Fallback for empty file data

            # Create a temporary file for the PDF - This is actually not needed if using convert_from_bytes
            # with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            #     temp_path = temp_file.name
            #     temp_file.write(file_data)
            # temp_path is not used with convert_from_bytes, so removing related logic.

            try:
                # Convert first page only with lower DPI for speed
                try:
                    self.logger.info(f"Attempting convert_from_bytes for {filename}")
                    images = convert_from_bytes(
                        file_data,  # Pass bytes directly
                        first_page=1,
                        last_page=1,
                        dpi=72,  # Lower DPI for preview
                        size=(300, None),
                        poppler_path="/usr/bin",  # Explicitly set Poppler path
                        timeout=10,  # Add a timeout
                    )
                    self.logger.info(
                        f"convert_from_bytes successful for {filename}, images found: {len(images)}"
                    )
                except Exception as e_convert:
                    self.logger.error(
                        f"PDF conversion (convert_from_bytes) failed for {filename}: {str(e_convert)}",
                        exc_info=True,
                    )
                    # Log specific pdf2image errors if possible
                    if hasattr(e_convert, "stdout") and e_convert.stdout:
                        self.logger.error(
                            f"pdf2image stdout for {filename}: {e_convert.stdout.decode(errors='ignore')}"
                        )
                    if hasattr(e_convert, "stderr") and e_convert.stderr:
                        self.logger.error(
                            f"pdf2image stderr for {filename}: {e_convert.stderr.decode(errors='ignore')}"
                        )
                    # If PDF conversion fails, signal to fallback to direct URL
                    return "fallback_to_direct_url"

                if not images:
                    self.logger.error(
                        f"No images extracted from PDF for {filename}. Triggering fallback."
                    )
                    return "fallback_to_direct_url"  # Fallback if no images extracted

                image = images[0]

                # Save as JPEG for smaller size
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG", quality=85, optimize=True)
                preview_image_bytes = buffered.getvalue()

                preview_image_bytes = buffered.getvalue()

                # Define S3 object name for the preview
                base, ext = os.path.splitext(filename)
                s3_object_name_base = secure_filename(
                    base
                )  # Original filename base, sanitized
                s3_object_name = f"previews/{s3_object_name_base}.jpg"  # This is the key within the bucket

                # Save bytes to a temporary file to use with storage.upload_file
                temp_preview_filepath = (
                    None  # Initialize to ensure it's defined for finally
                )
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".jpg"
                    ) as temp_preview_file:
                        temp_preview_file.write(preview_image_bytes)
                        temp_preview_filepath = temp_preview_file.name
                    self.logger.info(
                        f"PDF preview temporary file created at: {temp_preview_filepath} for {filename}"
                    )

                    # upload_file expects filepath and the object name (key in bucket)
                    self.logger.info(
                        f"Attempting to upload PDF preview {temp_preview_filepath} to S3 as {s3_object_name} for {filename}"
                    )
                    self.storage.upload_file(temp_preview_filepath, s3_object_name)
                    self.logger.info(
                        f"Successfully generated and uploaded PDF preview for {filename} to S3 object: {s3_object_name}"
                    )
                    # The Celery task expects just the S3 key (object name)
                    return {"s3_key": s3_object_name}
                except Exception as e_s3_upload:
                    self.logger.error(
                        f"Failed to upload PDF preview for {filename} to S3: {str(e_s3_upload)}",
                        exc_info=True,
                    )
                    return "fallback_to_direct_url"
                finally:
                    if temp_preview_filepath and os.path.exists(temp_preview_filepath):
                        os.remove(temp_preview_filepath)

            except (
                Exception
            ) as e_process:  # More specific exception for image processing part
                self.logger.error(
                    f"Error processing extracted image for PDF {filename}: {str(e_process)}",
                    exc_info=True,
                )
                self.logger.warning(
                    f"Error processing PDF image for {filename}. Triggering fallback."
                )
                return "fallback_to_direct_url"  # Fallback for image processing error
            # Removed the finally block as temp_path is no longer used with convert_from_bytes

        except Exception as e_outer:  # Catch-all for the outer try block
            self.logger.error(
                f"Outer PDF preview generation error for {filename}: {str(e_outer)}",
                exc_info=True,
            )
            self.logger.warning(
                f"Outer PDF preview error for {filename}. Triggering fallback."
            )
            return "fallback_to_direct_url"  # Fallback for any other outer error

    def _get_real_file_type(self, file_data):
        """Detects file type based on magic numbers."""
        if not file_data:
            return None
        if file_data.startswith(b"%PDF-"):
            return "pdf"
        elif file_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        elif file_data.startswith(b"\xff\xd8\xff"):  # Covers JPEG, JPG
            return "jpeg"
        elif file_data.startswith(b"GIF87a") or file_data.startswith(b"GIF89a"):
            return "gif"
        elif file_data.startswith(b"BM"):
            return "bmp"
        elif file_data.startswith(b"II*\x00") or file_data.startswith(b"MM\x00*"):
            return "tiff"
        return None

    def _generate_placeholder_preview(self, message="No preview available"):
        """Generate a placeholder image when preview generation fails"""
        try:
            # Create a blank image with text
            width, height = 300, 300
            image = Image.new("RGB", (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(image)

            # Draw a document icon
            icon_box = [
                (width / 2 - 50, height / 2 - 60),
                (width / 2 + 50, height / 2 + 30),
            ]
            draw.rectangle(
                icon_box, fill=(220, 220, 220), outline=(180, 180, 180), width=2
            )

            # Add lines to represent text
            for i in range(3):
                line_y = height / 2 - 30 + i * 15
                draw.line(
                    [(width / 2 - 30, line_y), (width / 2 + 30, line_y)],
                    fill=(180, 180, 180),
                    width=2,
                )

            # Add message text
            try:
                # Try to use a system font
                font = ImageFont.truetype("Arial", 12)
            except:
                # Fall back to default font
                font = ImageFont.load_default()

            text_width = draw.textlength(message, font=font)
            text_position = ((width - text_width) / 2, height / 2 + 50)
            draw.text(text_position, message, font=font, fill=(100, 100, 100))

            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            return f"data:image/png;base64,{img_str}"

        except Exception as e:
            self.logger.error(f"Error generating placeholder: {str(e)}")
            # Return a data URI for a very simple SVG as ultimate fallback
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300">'
            svg += '<rect width="300" height="300" fill="#f0f0f0"/>'
            svg += '<text x="150" y="150" font-family="sans-serif" font-size="12" text-anchor="middle" fill="#646464">'
            svg += "No preview available"
            svg += "</text></svg>"

            return (
                f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"
            )

    def _generate_preview_internal(self, filename, document_id=None):
        """
        Generate preview for a file.

        Args:
            filename (str): The name of the file to process.
            document_id (int, optional): The ID of the document. Defaults to None.

        Returns:
            A string containing a data URI or a dictionary with an s3_key.
        """
        try:
            # Get the file data from storage
            file_data = self.storage.get_file(filename)

            if not file_data:
                self.logger.error(f"File not found in storage: {filename}")
                # Check if this is a new document that hasn't been uploaded to S3 yet
                if document_id:
                    from src.catalog.models import Document

                    doc = Document.query.get(document_id)
                    if doc and doc.status in ["PENDING", "PROCESSING"]:
                        return self._generate_placeholder_preview(
                            "File is being processed"
                        )

                return self._generate_placeholder_preview(f"File not found: {filename}")

            # Determine file type and generate preview
            real_file_type = self._get_real_file_type(file_data)
            ext = os.path.splitext(filename.lower())[1]

            # Use real file type if detected, otherwise fall back to extension
            if real_file_type in ["png", "jpeg", "gif", "bmp", "tiff"]:
                self.logger.info(
                    f"Detected file type by content: {real_file_type} for {filename}"
                )
                return self._generate_image_preview(file_data, filename)
            elif real_file_type == "pdf":
                self.logger.info(
                    f"File {filename} is a PDF (by content), attempting server-side image conversion."
                )
                return self._generate_pdf_preview(file_data, filename)

            # Fallback to extension if content sniffing fails
            self.logger.warning(
                f"Could not detect file type for {filename} by content, falling back to extension '{ext}'"
            )
            if ext in self.supported_images:
                return self._generate_image_preview(file_data, filename)
            elif ext in self.supported_pdfs:
                self.logger.info(
                    f"File {filename} is a PDF (by extension), attempting server-side image conversion."
                )
                return self._generate_pdf_preview(file_data, filename)
            else:
                return self._generate_placeholder_preview(
                    f"Unsupported file type: {ext}"
                )

        except Exception as e:
            self.logger.error(
                f"Error generating preview for {filename}: {str(e)}", exc_info=True
            )
            return self._generate_placeholder_preview("Error generating preview")
