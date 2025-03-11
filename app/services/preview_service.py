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
        
    def get_preview(self, filename):
        """Generate preview for different file types"""
        try:
            logger.info(f"Generating preview for {filename}")
            
            # Use MinIOStorage to get the file data
            from app.services.storage_service import MinIOStorage
            storage = MinIOStorage()
            
            try:
                file_data = storage.get_file(filename)
                if not file_data:
                    logger.error(f"No file data received for {filename}")
                    return None
            except Exception as e:
                logger.error(f"Error retrieving file from storage: {str(e)}")
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
            logger.error(f"Preview generation error for {filename}: {str(e)}")
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