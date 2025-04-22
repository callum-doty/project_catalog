# app/services/preview_service.py

import os
from pdf2image import convert_from_bytes
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from app.services.storage_service import MinIOStorage
import logging
import tempfile
from werkzeug.utils import secure_filename
import traceback
from app.extensions import cache, db
from app.constants import CACHE_TIMEOUTS, SUPPORTED_FILE_TYPES

class PreviewService:
    def __init__(self):
        self.storage = MinIOStorage()
        self.supported_images = SUPPORTED_FILE_TYPES['IMAGES']
        self.supported_pdfs = SUPPORTED_FILE_TYPES['DOCUMENTS']
        self.logger = logging.getLogger(__name__)
    
    @cache.memoize(timeout=CACHE_TIMEOUTS['PREVIEW'])
        
    def get_preview(self, filename):
        """Get preview for a file, first checking cache"""
        try:
            # Check cache first
            cache_key = f"preview:{filename}"
            cached_preview = cache.get(cache_key)
            
            if cached_preview:
                self.logger.info(f"Using cached preview for {filename}")
                return cached_preview
            
            # If not in cache, check if a preview generation is already in progress
            in_progress_key = f"preview_in_progress:{filename}"
            if cache.get(in_progress_key):
                self.logger.info(f"Preview generation for {filename} already in progress, returning placeholder")
                return self._generate_placeholder_preview("Preview being generated...")
            
            # Mark as in progress (1 minute timeout to prevent deadlocks)
            cache.set(in_progress_key, True, timeout=60)
            
            # Queue background task for preview generation
            from tasks.preview_tasks import generate_preview
            generate_preview.delay(filename)
            
            # Generate preview synchronously for immediate display just this once
            return self._generate_preview_internal(filename)
            
        except Exception as e:
            self.logger.error(f"Preview error for {filename}: {str(e)}", exc_info=True)
            return self._generate_placeholder_preview("Error generating preview")

    def _generate_image_preview(self, file_data, filename):
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
            except Exception as e:
                self.logger.error(f"Error processing image: {str(e)}")
                return self._generate_placeholder_preview(f"Error processing: {os.path.basename(filename)}")
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
        except Exception as e:
            self.logger.error(f"Image preview generation error: {str(e)}", exc_info=True)
            return self._generate_placeholder_preview(f"Error: {os.path.basename(filename)}")

    def _generate_pdf_preview(self, file_data, filename):
        """Generate preview for PDF files"""
        try:
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_path = temp_file.name
                temp_file.write(file_data)
            
            try:
                # Convert first page only with lower DPI for speed
                try:
                    images = convert_from_bytes(
                        file_data,
                        first_page=1,
                        last_page=1,
                        dpi=72,  # Lower DPI for preview
                        size=(300, None) 
                    )
                except Exception as e:
                    self.logger.error(f"PDF conversion failed: {str(e)}")
                    return self._generate_placeholder_preview(f"PDF conversion failed: {os.path.basename(filename)}")
                
                if not images:
                    self.logger.error("No images extracted from PDF")
                    return self._generate_placeholder_preview(f"Empty PDF: {os.path.basename(filename)}")
                    
                image = images[0]
                
                # Save as JPEG for smaller size
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG", quality=85, optimize=True)
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                self.logger.info(f"Successfully generated PDF preview, size: {len(img_str)} chars")
                return f"data:image/jpeg;base64,{img_str}"
            except Exception as e:
                self.logger.error(f"PDF preview error: {str(e)}")
                tb = traceback.format_exc()
                self.logger.error(f"PDF preview traceback: {tb}")
                return self._generate_placeholder_preview(f"Error: {os.path.basename(filename)}")
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
        except Exception as e:
            self.logger.error(f"PDF preview generation error: {str(e)}", exc_info=True)
            return self._generate_placeholder_preview(f"Error: {os.path.basename(filename)}")
            
    def _generate_placeholder_preview(self, message="No preview available"):
        """Generate a placeholder image when preview generation fails"""
        try:
            # Create a blank image with text
            width, height = 300, 300
            image = Image.new('RGB', (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(image)
            
            # Draw a document icon
            icon_box = [(width/2-50, height/2-60), (width/2+50, height/2+30)]
            draw.rectangle(icon_box, fill=(220, 220, 220), outline=(180, 180, 180), width=2)
            
            # Add lines to represent text
            for i in range(3):
                line_y = height/2 - 30 + i*15
                draw.line([(width/2-30, line_y), (width/2+30, line_y)], fill=(180, 180, 180), width=2)
            
            # Add message text
            try:
                # Try to use a system font
                font = ImageFont.truetype("Arial", 12)
            except:
                # Fall back to default font
                font = ImageFont.load_default()
                
            text_width = draw.textlength(message, font=font)
            text_position = ((width - text_width) / 2, height/2 + 50)
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
            svg += 'No preview available'
            svg += '</text></svg>'
            
            return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"

    def _generate_preview_internal(self, filename):
        """Generate preview for a file"""
        try:
            # Get the file data from storage
            file_data = self.storage.get_file(filename)
            
            if not file_data:
                self.logger.error(f"File not found in storage: {filename}")
                return self._generate_placeholder_preview(f"File not found: {filename}")
            
            # Determine file type and generate preview
            ext = os.path.splitext(filename.lower())[1]
            
            if ext in self.supported_images:
                return self._generate_image_preview(file_data, filename)
                
            elif ext in self.supported_pdfs:
                return self._generate_pdf_preview(file_data, filename)
                
            else:
                return self._generate_placeholder_preview(f"Unsupported file type: {ext}")
                
        except Exception as e:
            self.logger.error(f"Error generating preview for {filename}: {str(e)}", exc_info=True)
            return self._generate_placeholder_preview("Error generating preview")