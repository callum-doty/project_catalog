"""
Fixed preview service that works in local development
"""

import os
from pdf2image import convert_from_bytes
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class FixedPreviewService:
    """Fixed preview service for local development"""
    
    def __init__(self, storage_path: str = "./dev_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        logger.info(f"Preview service using storage: {self.storage_path}")
    
    def generate_preview(self, filename: str) -> str:
        """Generate preview for a document"""
        try:
            file_path = self.storage_path / filename
            
            if not file_path.exists():
                logger.error(f"File not found: {filename}")
                return self._generate_placeholder_preview("File not found")
            
            file_data = file_path.read_bytes()
            
            # Determine file type
            if filename.lower().endswith('.pdf'):
                return self._generate_pdf_preview(file_data, filename)
            elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                return self._generate_image_preview(file_data, filename)
            else:
                return self._generate_placeholder_preview("Unsupported file type")
                
        except Exception as e:
            logger.error(f"Error generating preview for {filename}: {e}")
            return self._generate_placeholder_preview("Error generating preview")
    
    def _generate_pdf_preview(self, file_data: bytes, filename: str) -> str:
        """Generate preview for PDF files"""
        try:
            # Convert first page to image
            images = convert_from_bytes(
                file_data,
                first_page=1,
                last_page=1,
                dpi=150,
                size=(400, None)
            )
            
            if not images:
                return self._generate_placeholder_preview("Could not convert PDF")
            
            image = images[0]
            
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"PDF preview error for {filename}: {e}")
            return self._generate_placeholder_preview("PDF conversion failed")
    
    def _generate_image_preview(self, file_data: bytes, filename: str) -> str:
        """Generate preview for image files"""
        try:
            image = Image.open(io.BytesIO(file_data))
            
            # Convert RGBA to RGB if necessary
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            
            # Resize maintaining aspect ratio
            max_size = (400, 400)
            image.thumbnail(max_size, Image.LANCZOS)
            
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Image preview error for {filename}: {e}")
            return self._generate_placeholder_preview("Image processing failed")
    
    def _generate_placeholder_preview(self, message: str = "No preview available") -> str:
        """Generate a placeholder image"""
        try:
            # Create a simple placeholder
            width, height = 400, 300
            image = Image.new("RGB", (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(image)
            
            # Draw document icon
            icon_box = [
                (width / 2 - 50, height / 2 - 60),
                (width / 2 + 50, height / 2 + 30),
            ]
            draw.rectangle(icon_box, fill=(220, 220, 220), outline=(180, 180, 180), width=2)
            
            # Add text
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            text_bbox = draw.textbbox((0, 0), message, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_position = ((width - text_width) / 2, height / 2 + 50)
            draw.text(text_position, message, font=font, fill=(100, 100, 100))
            
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Error generating placeholder: {e}")
            # Return a simple SVG as ultimate fallback
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#f0f0f0"/><text x="200" y="150" font-family="sans-serif" font-size="14" text-anchor="middle" fill="#666">{message}</text></svg>'
            return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"
