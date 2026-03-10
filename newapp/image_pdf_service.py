"""
Image and PDF Analysis Service for WhatsApp Chatbot
Uses OpenAI Vision API to analyze images and PDFs
"""

import os
import base64
import tempfile
import requests
from io import BytesIO
from typing import List, Optional, Tuple, Dict
from PIL import Image
from datetime import datetime, timedelta

# In-memory cache for document context (phone -> context data)
# Stores the last analyzed document info for each user
_document_context_cache: Dict[str, dict] = {}

# Cache expiry time in minutes
CONTEXT_CACHE_EXPIRY_MINUTES = 30


def store_document_context(phone: str, analysis_result: str, document_type: str, filename: str = None):
    """
    Store the document analysis context for a user.
    
    Args:
        phone: User's phone number
        analysis_result: The analysis text from Vision API
        document_type: 'image' or 'document'
        filename: Optional filename for documents
    """
    _document_context_cache[phone] = {
        'analysis': analysis_result,
        'type': document_type,
        'filename': filename,
        'timestamp': datetime.now()
    }
    print(f"[Context] Stored context for {phone}: {document_type}")


def get_document_context(phone: str) -> Optional[dict]:
    """
    Get the stored document context for a user if it exists and hasn't expired.
    
    Args:
        phone: User's phone number
        
    Returns:
        Context dict with 'analysis', 'type', 'filename', 'timestamp' or None
    """
    context = _document_context_cache.get(phone)
    if not context:
        return None
    
    # Check if context has expired
    age = datetime.now() - context['timestamp']
    if age > timedelta(minutes=CONTEXT_CACHE_EXPIRY_MINUTES):
        del _document_context_cache[phone]
        print(f"[Context] Expired context for {phone}")
        return None
    
    return context


def clear_document_context(phone: str):
    """Clear the stored document context for a user."""
    if phone in _document_context_cache:
        del _document_context_cache[phone]
        print(f"[Context] Cleared context for {phone}")


def download_whatsapp_media(media_id: str, access_token: str) -> Optional[bytes]:
    """
    Download media from WhatsApp using the Graph API.
    
    Args:
        media_id: The WhatsApp media ID
        access_token: WhatsApp API access token
        
    Returns:
        bytes: The media file content, or None if download failed
    """
    try:
        # Step 1: Get the media URL
        url = f"https://graph.facebook.com/v17.0/{media_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # BUG FIX: Add timeout to prevent hanging
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"Failed to get media URL: {response.text}")
            return None
            
        media_url = response.json().get('url')
        if not media_url:
            print("No URL in media response")
            return None
        
        # Step 2: Download the actual media file
        media_response = requests.get(media_url, headers=headers)
        if media_response.status_code != 200:
            print(f"Failed to download media: {media_response.status_code}")
            return None
            
        return media_response.content
        
    except Exception as e:
        print(f"Error downloading media: {e}")
        return None


def convert_pdf_to_images(pdf_bytes: bytes) -> List[str]:
    """
    Convert PDF pages to base64-encoded images.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        List of base64-encoded image strings
    """
    try:
        from pdf2image import convert_from_bytes
        import platform
        
        # Set Poppler path for Windows (configurable via environment variable)
        poppler_path = None
        if platform.system() == 'Windows':
            poppler_path = os.environ.get('POPPLER_PATH', r"C:\Users\Meet\.gemini\poppler-25.12.0\Library\bin")
        
        # Convert PDF to images (limit to first 5 pages to avoid API overload)
        # Make page limit configurable via environment variable
        max_pages = int(os.environ.get('MAX_PDF_PAGES', '5'))
        
        # BUG FIX: Handle password-protected PDFs
        try:
            images = convert_from_bytes(pdf_bytes, dpi=150, poppler_path=poppler_path, first_page=1, last_page=max_pages)
        except Exception as pdf_error:
            error_msg = str(pdf_error).lower()
            if 'password' in error_msg or 'encrypted' in error_msg:
                print("[ImageService] ERROR: PDF is password-protected")
                return []
            # Re-raise other errors
            raise
        
        # Log if PDF has more pages than analyzed
        if len(images) >= max_pages:
            print(f"[ImageService] Warning: PDF has {max_pages}+ pages, analyzing first {max_pages} only")
        
        base64_images = []
        for img in images:
            # Convert PIL Image to base64
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            base64_images.append(img_base64)
            
        return base64_images
        
    except ImportError:
        with open('debug_log.txt', 'a') as f:
            f.write("[ImageService] Error: pdf2image not installed\n")
        print("pdf2image not installed. Install with: pip install pdf2image")
        print("Also ensure Poppler is installed on your system.")
        return []
    except Exception as e:
        with open('debug_log.txt', 'a') as f:
            f.write(f"[ImageService] Error converting PDF to images: {e}\n")
        print(f"Error converting PDF to images: {e}")
        return []


def encode_image_to_base64(image_bytes: bytes) -> Optional[str]:
    """
    Encode image bytes to base64 string.
    
    Args:
        image_bytes: Image file content as bytes
        
    Returns:
        Base64-encoded string of the image
    """
    try:
        # Validate and optionally resize image
        img = Image.open(BytesIO(image_bytes))
        
        # Resize if too large (OpenAI recommends max 2048x2048)
        max_size = 2048
        if img.width > max_size or img.height > max_size:
            ratio = min(max_size / img.width, max_size / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Encode to base64
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
        
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None


def analyze_images_with_vision(
    base64_images: List[str], 
    user_question: str, 
    api_key: str,
    system_prompt: str = ""
) -> str:
    """
    Send images to OpenAI Vision API for analysis.
    
    Args:
        base64_images: List of base64-encoded images
        user_question: The user's question about the images
        api_key: OpenAI API key
        system_prompt: Optional system prompt for context
        
    Returns:
        The AI's analysis response
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Build content array with all images
        content = []
        
        # Add each image
        for i, img_base64 in enumerate(base64_images):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_base64}",
                    "detail": "high"
                }
            })
        
        # Add the user's question
        if len(base64_images) > 1:
            question_text = f"I'm sharing {len(base64_images)} images/pages. {user_question}"
        else:
            question_text = user_question
            
        content.append({
            "type": "text",
            "text": question_text
        })
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({
            "role": "user",
            "content": content
        })
        
        # Call OpenAI Vision API
        # Scale max_tokens based on number of images (more pages = more tokens needed)
        tokens = min(1500 * len(base64_images), 4096)
        response = client.chat.completions.create(
            model="gpt-4o",  # GPT-4o has vision capabilities
            messages=messages,
            max_tokens=tokens
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        with open('debug_log.txt', 'a') as f:
            f.write(f"[ImageService] Error in Vision API call: {e}\n")
        print(f"Error in Vision API call: {e}")
        return f"Sorry, I couldn't analyze the image(s). Error: {str(e)}"


def analyze_media_message(
    media_id: str,
    media_type: str,
    user_question: str,
    admin,  # Admin model instance
    mime_type: str = None,
    openai_key: str = None,
    whatsapp_token: str = None,
    organization=None  # Organization model instance
) -> str:
    """
    Main function to analyze media (image or PDF) from WhatsApp.
    
    Args:
        media_id: WhatsApp media ID
        media_type: 'image' or 'document'
        user_question: The user's question/caption
        admin: Admin model instance with API keys
        mime_type: MIME type of the document (for PDFs)
        openai_key: Optional OpenAI API key (preferred over admin's key)
        whatsapp_token: Optional WhatsApp token (preferred over admin's token)
        organization: Optional Organization model instance
        
    Returns:
        Analysis response string
    """
    # Get API keys - prefer passed-in keys (from org/creds), fall back to org, then admin
    api_key = openai_key
    wa_token = whatsapp_token
    
    if not api_key and organization:
        api_key = getattr(organization, 'openai_api_key', None)
        wa_token = wa_token or getattr(organization, 'whatsapp_token', None)
    if not api_key and admin:
        api_key = getattr(admin, 'openai_api_key', None)
        wa_token = wa_token or getattr(admin, 'whatsapp_token', None)
    
    if not api_key:
        return "Sorry, I cannot analyze images right now. The AI service is not configured."
    
    if not wa_token:
        return "Sorry, I cannot download your media. WhatsApp is not configured."
    
    # Download the media
    try:
        # BUG FIX: Add size validation
        MAX_MEDIA_SIZE_MB = 16
        media_bytes = download_whatsapp_media(media_id, wa_token)
        
        if not media_bytes:
            return "Sorry, I couldn't download your file. Please try sending it again."
        
        # Check file size
        media_size_mb = len(media_bytes) / (1024 * 1024)
        if media_size_mb > MAX_MEDIA_SIZE_MB:
            return f"Sorry, the file is too large (max {MAX_MEDIA_SIZE_MB}MB). Please send a smaller file."
        
        with open('debug_log.txt', 'a') as f:
            f.write(f"[Vision] Downloaded media bytes: {len(media_bytes)} ({media_size_mb:.2f}MB)\n")
    except Exception as e:
        with open('debug_log.txt', 'a') as f:
            f.write(f"[Vision] Download check failed: {str(e)}\n")
        return f"Error downloading media: {str(e)}"
    if not media_bytes:
        return "Sorry, I couldn't download your file. Please try sending it again."
    
    base64_images = []
    
    # Process based on media type
    if media_type == 'image':
        # Single image
        img_base64 = encode_image_to_base64(media_bytes)
        if img_base64:
            base64_images = [img_base64]
        else:
            return "Sorry, I couldn't process your image. Please try a different format."
            
    elif media_type == 'document':
        # Check if it's a PDF
        is_pdf = False
        if mime_type and 'pdf' in mime_type.lower():
            is_pdf = True
        elif media_bytes[:4] == b'%PDF':
            is_pdf = True
            
        if is_pdf:
            # Convert PDF to images
            base64_images = convert_pdf_to_images(media_bytes)
            if not base64_images:
                return "Sorry, I couldn't process your PDF. Please ensure it's a valid PDF file."
        else:
            # Try to treat as an image
            img_base64 = encode_image_to_base64(media_bytes)
            if img_base64:
                base64_images = [img_base64]
            else:
                return "Sorry, I can only analyze images and PDF documents."
    
    if not base64_images:
        return "Sorry, I couldn't extract any images to analyze."
    
    # Get system prompt — filter by organization/admin for correct business context
    from .models import ChatGPTPrompt
    prompt_obj = None
    if organization:
        prompt_obj = ChatGPTPrompt.objects.filter(organization=organization).order_by('-updated_at').first()
    if not prompt_obj and admin:
        prompt_obj = ChatGPTPrompt.objects.filter(admin=admin).order_by('-updated_at').first()
    if not prompt_obj:
        prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
    system_prompt = prompt_obj.prompt_text if prompt_obj else ""
    
    # Add context for image analysis
    enhanced_prompt = system_prompt
    if not enhanced_prompt:
        enhanced_prompt = "You are a helpful assistant that analyzes images and documents."
    enhanced_prompt += "\n\nWhen analyzing images or documents, respond in the context of the conversation. If the image is a screenshot of a booking confirmation, appointment, or receipt, acknowledge it and extract relevant details. Be specific and detailed. If asked about specific information (like IDs, dates, amounts), extract and provide that exact information."
    
    # Analyze with Vision API
    response = analyze_images_with_vision(
        base64_images,
        user_question,
        api_key,
        enhanced_prompt
    )
    
    with open('debug_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"\n[Vision] OpenAI Response:\n{response}\n")
        
    return response


def transcribe_audio(media_id: str, openai_key: str, whatsapp_token: str) -> Optional[str]:
    """
    Download audio from WhatsApp and transcribe using OpenAI Whisper.
    Supports: ogg/opus (WhatsApp voice), mp3, m4a, wav, webm
    
    Args:
        media_id: WhatsApp media ID
        openai_key: OpenAI API key
        whatsapp_token: WhatsApp API access token
        
    Returns:
        Transcription text, or None if failed
    """
    if not openai_key:
        print("[Audio] No OpenAI key for transcription")
        return None
    
    if not whatsapp_token:
        print("[Audio] No WhatsApp token for media download")
        return None
    
    # Download audio from WhatsApp
    audio_bytes = download_whatsapp_media(media_id, whatsapp_token)
    if not audio_bytes:
        print("[Audio] Failed to download audio")
        return None
    
    # Save to temp file (Whisper API needs a file object)
    temp_path = None
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name
        
        # Transcribe with OpenAI Whisper
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        with open(temp_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                prompt="This is a voice message from a WhatsApp conversation."
            )
        
        with open('debug_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"[Audio] Transcribed: {transcript.text[:200] if transcript.text else 'EMPTY'}\n")
        
        transcribed_text = transcript.text.strip() if transcript.text else None
        if transcribed_text:
            print(f"[Audio] Transcribed: {transcribed_text[:100]}...")
        else:
            print("[Audio] Whisper returned empty transcription")
        
        return transcribed_text
        
    except Exception as e:
        print(f"[Audio] Transcription error: {e}")
        with open('debug_log.txt', 'a') as f:
            f.write(f"[Audio] Transcription error: {e}\n")
        return None
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except Exception as cleanup_error:
                print(f"[Audio] Warning: Could not delete temp file: {cleanup_error}")


def save_chat_media(media_id: str, access_token: str) -> Optional[str]:
    """
    Downloads media from WhatsApp and saves it to MEDIA_ROOT/chat_uploads.
    Returns the public relative URL (e.g. /media/chat_uploads/xyz.jpg).
    """
    try:
        from django.conf import settings
        import os
        
        # Download bytes
        media_bytes = download_whatsapp_media(media_id, access_token)
        if not media_bytes:
            return None
            
        # Create directory
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'chat_uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Detect extension
        ext = 'bin'
        if media_bytes[:4] == b'%PDF':
            ext = 'pdf'
        elif media_bytes[:3] == b'\xff\xd8\xff': # JPEG
            ext = 'jpg'
        elif media_bytes[:8] == b'\x89PNG\r\n\x1a\n': # PNG
            ext = 'png'
        else:
            # Fallback for others
            ext = 'jpg' 
            
        filename = f"{media_id}.{ext}"
        filepath = os.path.join(upload_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(media_bytes)
            
        # Return URL
        return f"/media/chat_uploads/{filename}"
        
    except Exception as e:
        print(f"Error saving chat media: {e}")
        return None
