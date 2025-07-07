#!/usr/bin/env python3
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
