#!/usr/bin/env python3
"""
Fix script for document preview system issues
This script addresses common preview rendering problems
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if required dependencies are installed"""
    missing_deps = []

    try:
        import pdf2image

        logger.info("✓ pdf2image is available")
    except ImportError:
        missing_deps.append("pdf2image")
        logger.error("✗ pdf2image is missing")

    try:
        from PIL import Image

        logger.info("✓ Pillow is available")
    except ImportError:
        missing_deps.append("Pillow")
        logger.error("✗ Pillow is missing")

    # Check for poppler (required by pdf2image)
    poppler_paths = [
        "/usr/bin/pdftoppm",
        "/usr/local/bin/pdftoppm",
        "/opt/homebrew/bin/pdftoppm",
        "/usr/bin/poppler",
        "/usr/local/bin/poppler",
    ]

    poppler_found = any(os.path.exists(path) for path in poppler_paths)
    if poppler_found:
        logger.info("✓ Poppler utilities found")
    else:
        logger.error("✗ Poppler utilities not found")
        logger.info(
            "Install with: brew install poppler (macOS) or apt-get install poppler-utils (Ubuntu)"
        )

    return missing_deps, poppler_found


def fix_storage_config():
    """Fix storage configuration for local development"""
    env_file = project_root / ".env"

    if not env_file.exists():
        logger.warning("No .env file found, creating one...")
        env_content = """# Storage Configuration for Local Development
STORAGE_TYPE=local
STORAGE_PATH=./dev_storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents
MINIO_SECURE=false

# Database
DATABASE_URL=sqlite:///./documents.db

# Cache
CACHE_TYPE=simple
"""
        env_file.write_text(env_content)
        logger.info("Created .env file with local development settings")
    else:
        logger.info("✓ .env file exists")


def create_local_storage_service():
    """Create a local storage service for development"""
    local_storage_file = (
        project_root / "src" / "catalog" / "services" / "local_storage_service.py"
    )

    content = '''"""
Local storage service for development
Handles file storage without requiring MinIO/S3
"""

import os
import shutil
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class LocalStorageService:
    """Local file storage service for development"""
    
    def __init__(self, storage_path: str = "./dev_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        logger.info(f"Initialized local storage at: {self.storage_path}")
    
    def get_file(self, filename: str) -> Optional[bytes]:
        """Get file content as bytes"""
        try:
            file_path = self.storage_path / filename
            if file_path.exists():
                return file_path.read_bytes()
            else:
                logger.warning(f"File not found: {filename}")
                return None
        except Exception as e:
            logger.error(f"Error reading file {filename}: {e}")
            return None
    
    def upload_file(self, local_path: str, filename: str) -> str:
        """Upload file to local storage"""
        try:
            source = Path(local_path)
            destination = self.storage_path / filename
            
            shutil.copy2(source, destination)
            logger.info(f"Uploaded file: {filename}")
            return str(destination)
        except Exception as e:
            logger.error(f"Error uploading file {filename}: {e}")
            raise
    
    def get_presigned_url(self, filename: str, bucket_name: str = None) -> Optional[str]:
        """Get URL for file access (for local development, return file path)"""
        file_path = self.storage_path / filename
        if file_path.exists():
            return f"/api/files/{filename}"
        return None
    
    def file_exists(self, filename: str) -> bool:
        """Check if file exists"""
        return (self.storage_path / filename).exists()
'''

    local_storage_file.write_text(content)
    logger.info("Created local storage service")


def create_preview_fix():
    """Create a fixed preview service"""
    preview_fix_file = (
        project_root / "src" / "catalog" / "services" / "preview_service_fixed.py"
    )

    content = '''"""
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
'''

    preview_fix_file.write_text(content)
    logger.info("Created fixed preview service")


def create_test_preview_route():
    """Create a test route for previews"""
    test_route_file = project_root / "test_preview_route.py"

    content = '''#!/usr/bin/env python3
"""
Test script for document previews
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.catalog.services.preview_service_fixed import FixedPreviewService

def test_preview():
    """Test preview generation"""
    preview_service = FixedPreviewService()
    
    # Check for documents in dev_storage
    storage_path = Path("./dev_storage")
    if not storage_path.exists():
        print("No dev_storage directory found")
        return
    
    pdf_files = list(storage_path.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in dev_storage")
        return
    
    # Test with first PDF
    test_file = pdf_files[0]
    print(f"Testing preview generation for: {test_file.name}")
    
    preview_data = preview_service.generate_preview(test_file.name)
    
    if preview_data.startswith("data:image"):
        print("✓ Preview generated successfully!")
        print(f"Preview data length: {len(preview_data)} characters")
        
        # Save as HTML for testing
        html_content = f"""<!DOCTYPE html>
<html>
<head><title>Preview Test</title></head>
<body>
    <h1>Preview Test: {test_file.name}</h1>
    <img src="{preview_data}" style="max-width: 100%; border: 1px solid #ccc;">
</body>
</html>"""
        
        with open("preview_test.html", "w") as f:
            f.write(html_content)
        
        print("✓ Saved test preview as preview_test.html")
        print("Open preview_test.html in your browser to see the result")
    else:
        print("✗ Preview generation failed")
        print(f"Result: {preview_data[:100]}...")

if __name__ == "__main__":
    test_preview()
'''

    test_route_file.write_text(content)
    test_route_file.chmod(0o755)
    logger.info("Created test preview script")


def main():
    """Main fix function"""
    logger.info("🔧 Starting document preview system fix...")

    # Check dependencies
    logger.info("1. Checking dependencies...")
    missing_deps, poppler_found = check_dependencies()

    if missing_deps:
        logger.error(f"Missing dependencies: {missing_deps}")
        logger.info("Install with: pip install " + " ".join(missing_deps))

    if not poppler_found:
        logger.error("Poppler utilities not found")
        logger.info("Install with: brew install poppler (macOS)")

    # Fix configuration
    logger.info("2. Fixing storage configuration...")
    fix_storage_config()

    # Create local services
    logger.info("3. Creating local storage service...")
    create_local_storage_service()

    logger.info("4. Creating fixed preview service...")
    create_preview_fix()

    logger.info("5. Creating test script...")
    create_test_preview_route()

    logger.info("✅ Fix complete!")
    logger.info("\nNext steps:")
    logger.info("1. Install missing dependencies if any")
    logger.info("2. Run: python test_preview_route.py")
    logger.info("3. Check if preview_test.html shows a document preview")

    # Check if we have documents to test with
    dev_storage = Path("./dev_storage")
    if dev_storage.exists():
        pdf_files = list(dev_storage.glob("*.pdf"))
        if pdf_files:
            logger.info(f"Found {len(pdf_files)} PDF files for testing")
        else:
            logger.info(
                "No PDF files found in dev_storage - copy some PDFs there for testing"
            )

    # Check simplified app storage
    simplified_storage = Path("./simplified_app/dev_storage")
    if simplified_storage.exists():
        pdf_files = list(simplified_storage.glob("*.pdf"))
        if pdf_files:
            logger.info(
                f"Found {len(pdf_files)} PDF files in simplified_app/dev_storage"
            )
            logger.info("You can copy these to ./dev_storage for testing")


if __name__ == "__main__":
    main()
