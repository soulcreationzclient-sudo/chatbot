
import os
import sys

# Mock Django setup not needed for this isolated test if we just import the logic
# But to be safe, I'll just copy the logic here to avoid dependency hell

def test_conversion():
    try:
        from pdf2image import convert_from_path, convert_from_bytes
        print("pdf2image imported successfully")
    except ImportError:
        print("Error: pdf2image not installed")
        return

    poppler_path = r"C:\Users\Meet\.gemini\poppler-25.12.0\Library\bin"
    print(f"Checking poppler path: {poppler_path}")
    if os.path.exists(poppler_path):
        print("Poppler path exists")
        print(f"Contents: {os.listdir(poppler_path)[:5]}") 
    else:
        print("Poppler path DOES NOT exist")
        return

    # Create a dummy PDF for testing if one doesn't exist
    # OR better, tell me if I should assume a file exists. 
    # I'll try to convert a simple bytes object representing a valid empty PDF header
    # Minimal PDF:
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Resources << >>\n>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n223\n%%EOF\n"
    
    print("Attempting conversion of dummy PDF...")
    try:
        images = convert_from_bytes(dummy_pdf, poppler_path=poppler_path)
        print(f"Success! Converted {len(images)} images.")
    except Exception as e:
        print(f"Conversion FAILED: {e}")

if __name__ == "__main__":
    test_conversion()
