# app/services/preview_service.py

import os
from pdf2image import convert_from_bytes
from PIL import Image
import io
import base64
from app.services.storage_service import MinIOStorage
import logging
import tempfile
from werkzeug.utils import secure_filename

class PreviewService:
    def __init__(self):
        self.storage = MinIOStorage()
        self.supported_images = ['.jpg', '.jpeg', '.png', '.gif']
        self.supported_pdfs = ['.pdf']
        self.logger = logging.getLogger(__name__)
        
    def get_preview(self, filename):
        """Generate preview for different file types"""
        try:
            self.logger.info(f"Generating preview for {filename}")
            file_ext = os.path.splitext(filename)[1].lower()
            
            # Get file data from MinIO
            try:
                file_data = self.storage.get_file(filename)
                if not file_data:
                    self.logger.error(f"No file data received for {filename}")
                    return None
                self.logger.info(f"Retrieved file data for {filename}, size: {len(file_data)} bytes")
            except Exception as e:
                self.logger.error(f"Error retrieving file from storage: {str(e)}")
                return None
                
            # Generate preview based on file type
            if file_ext in self.supported_images:
                return self._generate_image_preview(file_data)
            elif file_ext in self.supported_pdfs:
                return self._generate_pdf_preview(file_data)
            else:
                self.logger.warning(f"Unsupported file type: {file_ext}")
                return None
                
        except Exception as e:
            self.logger.error(f"Preview generation error for {filename}: {str(e)}", exc_info=True)
            return None

    def _generate_image_preview(self, file_data):
        """Generate preview for image files"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_path = temp_file.name
                temp_file.write(file_data)
            
            try:
                # Open the image file
                image = Image.open(temp_path)
                
                # Convert RGBA to RGB if necessary
                if image.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[-1])
                    image = background
                
                # Resize maintaining aspect ratio
                max_size = (300, 300)
                image.thumbnail(max_size, Image.LANCZOS)
                
                # Save as JPEG for smaller size
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG", quality=85, optimize=True)
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                self.logger.info(f"Successfully generated image preview, size: {len(img_str)} chars")
                return f"data:image/jpeg;base64,{img_str}"
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
        except Exception as e:
            self.logger.error(f"Image preview generation error: {str(e)}", exc_info=True)
            return None

    def _generate_pdf_preview(self, file_data):
        """Generate preview for PDF files"""
        try:
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_path = temp_file.name
                temp_file.write(file_data)
            
            try:
                # Convert first page only with lower DPI for speed
                images = convert_from_bytes(
                    file_data,
                    first_page=1,
                    last_page=1,
                    dpi=72,  # Lower DPI for preview
                    fmt='jpeg',
                    size=(300, None) 
                )
                
                if not images:
                    self.logger.error("No images extracted from PDF")
                    return None
                    
                image = images[0]
                
                # Save as JPEG for smaller size
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG", quality=85, optimize=True)
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                self.logger.info(f"Successfully generated PDF preview, size: {len(img_str)} chars")
                return f"data:image/jpeg;base64,{img_str}"
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
        except Exception as e:
            self.logger.error(f"PDF preview generation error: {str(e)}", exc_info=True)
            return None