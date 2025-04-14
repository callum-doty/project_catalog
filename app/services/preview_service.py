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

class PreviewService:
    def __init__(self):
        self.storage = MinIOStorage()
        self.supported_images = ['.jpg', '.jpeg', '.png', '.gif']
        self.supported_pdfs = ['.pdf']
        self.logger = logging.getLogger(__name__)
    
    @cache.memoize(timeout=3600)
        
    def get_preview(self, filename):
        """Generate preview for different file types"""
        try:
            self.logger.info(f"Generating preview for {filename}")
            
            if not filename:
                self.logger.warning("Empty filename provided")
                return self._generate_placeholder_preview("No filename")
                
            file_ext = os.path.splitext(filename)[1].lower()
            
            # Get file data from MinIO
            try:
                file_data = self.storage.get_file(filename)
                if not file_data or len(file_data) == 0:
                    self.logger.error(f"No file data received for {filename}")
                    return self._generate_placeholder_preview(f"Missing: {filename}")
                self.logger.info(f"Retrieved file data for {filename}, size: {len(file_data)} bytes")
            except Exception as e:
                self.logger.error(f"Error retrieving file from storage: {str(e)}")
                return self._generate_placeholder_preview(f"Error: {os.path.basename(filename)}")
                
            # Generate preview based on file type
            if file_ext in self.supported_images:
                return self._generate_image_preview(file_data, filename)
            elif file_ext in self.supported_pdfs:
                return self._generate_pdf_preview(file_data, filename)
            else:
                self.logger.warning(f"Unsupported file type: {file_ext}")
                return self._generate_placeholder_preview(f"Unsupported: {file_ext}")
                
        except Exception as e:
            self.logger.error(f"Preview generation error for {filename}: {str(e)}", exc_info=True)
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