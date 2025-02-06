# app/services/preview_service.py

import os
from pdf2image import convert_from_bytes
from PIL import Image
import io
import base64
from app.services.storage_service import MinIOStorage
import logging

class PreviewService:
    def __init__(self):
        self.storage = MinIOStorage()
        self.supported_images = ['.jpg', '.jpeg', '.png', '.gif']
        self.supported_pdfs = ['.pdf']
        self.logger = logging.getLogger(__name__)
        
    def get_preview(self, filename):
        """Generate preview for different file types"""
        try:
            file_data = self.storage.get_file(filename)
            if not file_data:
                self.logger.error(f"No file data received for {filename}")
                return None
                
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext in self.supported_images:
                return self._generate_image_preview(file_data)
            elif file_ext in self.supported_pdfs:
                return self._generate_pdf_preview(file_data)
            else:
                self.logger.warning(f"Unsupported file type: {file_ext}")
                return None
                
        except Exception as e:
            self.logger.error(f"Preview generation error for {filename}: {str(e)}")
            return None

    def _generate_image_preview(self, file_data):
        """Generate preview for image files"""
        try:
            # Open image bytes
            image = Image.open(io.BytesIO(file_data))
            
            # Convert RGBA to RGB if necessary
            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            
            # Resize maintaining aspect ratio
            image.thumbnail((300, 300), Image.LANCZOS)
            
            # Save as JPEG for smaller size
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85, optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
        except Exception as e:
            self.logger.error(f"Image preview generation error: {str(e)}")
            return None

    def _generate_pdf_preview(self, file_data):
        """Generate preview for PDF files"""
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
                return None
                
            image = images[0]
            
            # Save as JPEG for smaller size
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85, optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
        except Exception as e:
            self.logger.error(f"PDF preview generation error: {str(e)}")
            return None