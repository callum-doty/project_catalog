# app/services/preview_service.py
import os
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import logging
from app.services.storage_service import MinIOStorage

logger = logging.getLogger(__name__)

class PreviewService:
    def __init__(self):
        self.storage = MinIOStorage()
        self.supported_images = ['.jpg', '.jpeg', '.png', '.gif']
        self.supported_pdfs = ['.pdf']
        self.logger = logger
    
    def get_preview(self, filename):
        """Generate a simple preview for any file type"""
        try:
            # First try to get the file
            try:
                file_data = self.storage.get_file(filename)
                if not file_data:
                    logger.warning(f"File not found: {filename}")
                    return self._generate_text_preview(filename, "File not found")
            except Exception as e:
                logger.warning(f"Error retrieving file {filename}: {str(e)}")
                return self._generate_text_preview(filename, "Error retrieving file")
            
            # For simplicity, generate a basic text preview for all files
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext in self.supported_images:
                try:
                    return self._generate_image_preview(file_data)
                except Exception as e:
                    logger.error(f"Image preview error: {str(e)}")
                    return self._generate_text_preview(filename, "Image")
            else:
                # For PDFs and other files, just generate a text preview
                return self._generate_text_preview(filename, "Document")
                
        except Exception as e:
            logger.error(f"Preview generation failed for {filename}: {str(e)}")
            return None
    
    def _generate_image_preview(self, file_data):
        """Generate a thumbnail for image data"""
        try:
            # Convert bytes to image
            image = Image.open(io.BytesIO(file_data))
            
            # Handle alpha channel
            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            
            # Resize to thumbnail
            image.thumbnail((300, 300))
            
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=70)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
        except Exception as e:
            logger.error(f"Image preview generation error: {str(e)}")
            raise
    
    def _generate_text_preview(self, filename, file_type="Document"):
        """Generate a simple text-based preview"""
        try:
            # Create a basic colored rectangle with text
            width, height = 300, 200
            img = Image.new('RGB', (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(img)
            
            # Draw a border
            draw.rectangle([(0, 0), (width-1, height-1)], outline=(200, 200, 200))
            
            # Add filename text
            font_size = min(18, 600 // len(filename)) if len(filename) > 0 else 18
            draw.text((width//2, height//2 - 20), filename, 
                     fill=(100, 100, 100), anchor="mm")
            
            # Add file type
            draw.text((width//2, height//2 + 20), f"{file_type}", 
                     fill=(150, 150, 150), anchor="mm")
            
            # Convert to base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
        except Exception as e:
            logger.error(f"Text preview generation error: {str(e)}")
            # If all else fails, return None
            return None