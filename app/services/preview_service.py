import os
from functools import lru_cache
from pdf2image import convert_from_bytes
from PIL import Image
import io
import base64
import hashlib
from app.services.storage_service import MinIOStorage
import redis
import pickle
import logging
import uuid
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

class PreviewService:
    def __init__(self):
        self.storage = MinIOStorage()
        self.redis_client = redis.Redis(host='redis', port=6379, db=1)
        self.cache_ttl = 3600  # 1 hour
        self.supported_images = ['.jpg', '.jpeg', '.png', '.gif']
        self.supported_pdfs = ['.pdf']
        
    def _get_cache_key(self, filename):
        """Generate a cache key for a filename"""
        return f"preview:{hashlib.md5(filename.encode()).hexdigest()}"
        
    def _generate_pdf_preview(self, file_data):
        """Generate preview for PDF files"""
        try:
            # Log the process
            logger.info("Starting PDF preview generation")
            
            # Save file to temp location
            temp_pdf = os.path.join('/tmp', f"temp_{uuid.uuid4().hex}.pdf")
            with open(temp_pdf, 'wb') as f:
                f.write(file_data)
            
            try:
                # Check if poppler is available
                logger.info("Converting PDF to image...")
                images = convert_from_path(
                    temp_pdf,
                    first_page=1,
                    last_page=1,
                    dpi=72,
                    fmt='jpeg',
                    size=(300, None)
                )
                
                if not images:
                    logger.warning("No images generated from PDF")
                    return None
                    
                image = images[0]
                
                # Save as JPEG for smaller size
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG", quality=85, optimize=True)
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                logger.info("Successfully generated PDF preview")
                return f"data:image/jpeg;base64,{img_str}"
                
            except Exception as e:
                logger.error(f"PDF conversion error: {str(e)}")
                # For PDFs, generate a generic preview if conversion fails
                return self._generate_generic_preview("PDF Document")
        
        except Exception as e:
            logger.error(f"PDF preview generation error: {str(e)}")
            return None
        
    def _generate_generic_preview(self, label="Document"):
        """Generate a simple text-based preview when image conversion fails"""
        try:
            # Create a simple image with PIL
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new('RGB', (300, 300), color=(240, 240, 240))
            d = ImageDraw.Draw(img)
            d.text((150, 150), label, fill=(100, 100, 100), anchor="mm")
            
            # Convert to base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
        except Exception as e:
            logger.error(f"Generic preview generation failed: {str(e)}")
            return None
        
    def _generate_preview(self, filename):
        """Generate preview for different file types"""
        try:
            file_data = self.storage.get_file(filename)
            if not file_data:
                logger.error(f"No file data received for {filename}")
                return None
                
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext in self.supported_images:
                return self._generate_image_preview(file_data)
            elif file_ext in self.supported_pdfs:
                return self._generate_pdf_preview(file_data)
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return None
                
        except Exception as e:
            logger.error(f"Preview generation error: {str(e)}")
            return None

    def _generate_image_preview(self, file_data):
        """Generate preview for image files"""
        try:
            image = Image.open(io.BytesIO(file_data))
            
            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            
            image.thumbnail((300, 300), Image.LANCZOS)
            
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85, optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Image preview generation error: {str(e)}")
            return None

    def _generate_pdf_preview(self, file_data):
        """Generate preview for PDF files"""
        try:
            images = convert_from_bytes(
                file_data,
                first_page=1,
                last_page=1,
                dpi=72,
                fmt='jpeg',
                size=(300, None)
            )
            
            if not images:
                return None
                
            image = images[0]
            
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85, optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"PDF preview generation error: {str(e)}")
            return None