"""
Image Tag Processor for WhatsApp Messages

This module handles the processing of {{image:name}} tags in AI responses,
allowing the chatbot to send images stored as ImageAssets via WhatsApp.

Usage in AI prompts:
    "Here's our menu! {{image:menu_card}}"
    
The processor will:
1. Parse the {{image:xxx}} tags from the response
2. Look up the corresponding ImageAsset
3. Upload and send the image via WhatsApp API
4. Send any remaining text as a separate message
"""

import re
import os
import requests
from django.conf import settings


def parse_image_tags(text):
    """
    Extract all {{image:xxx}} tags from text.
    
    Args:
        text: The response text containing potential image tags
        
    Returns:
        List of tuples: [(full_tag, image_name), ...]
        Example: [('{{image:menu_card}}', 'menu_card'), ('{{image:price_list}}', 'price_list')]
    """
    pattern = r'\{\{image:([a-zA-Z0-9_]+)\}\}'
    matches = re.findall(pattern, text)
    full_tags = re.findall(r'\{\{image:[a-zA-Z0-9_]+\}\}', text)
    return list(zip(full_tags, matches))


def get_image_asset(name, admin, organization=None):
    """
    Look up an ImageAsset by name for a specific admin or organization.
    
    Args:
        name: The image asset name (e.g., 'menu_card')
        admin: The Admin model instance
        organization: The Organization model instance (optional)
        
    Returns:
        ImageAsset instance or None if not found
    """
    from newapp.models import ImageAsset
    try:
        if organization:
            asset = ImageAsset.objects.filter(organization=organization, name=name).first()
            if asset:
                return asset
        
        # Fallback to admin if no org specific asset or org not provided
        if admin:
            return ImageAsset.objects.filter(admin=admin, name=name).first()
            
        return None
    except Exception as e:
        print(f"[ImageTag] Error looking up image asset '{name}': {e}")
        return None


def compress_image_for_whatsapp(image_path, max_size_mb=5, max_dimension=1024):
    """
    Compress an image to be within WhatsApp's size limits.
    
    Args:
        image_path: Path to the original image
        max_size_mb: Maximum file size in MB (WhatsApp limit is ~16MB, but we use 5 for safety)
        max_dimension: Maximum width/height in pixels
        
    Returns:
        Path to the compressed image (temp file), or original path if already small enough
    """
    try:
        from PIL import Image
        import tempfile
        
        # Check current file size
        current_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        
        if current_size <= max_size_mb:
            # Check dimensions too
            with Image.open(image_path) as img:
                if max(img.size) <= max_dimension:
                    print(f"[ImageTag] Image already within limits: {current_size:.2f}MB")
                    return image_path
        
        print(f"[ImageTag] Compressing image from {current_size:.2f}MB...")
        
        # Open and resize
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"[ImageTag] Resized to {new_size}")
            
            # Save to temp file with compression
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # Try different quality levels to get under size limit
            for quality in [85, 70, 50, 30]:
                img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                new_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
                if new_size_mb <= max_size_mb:
                    print(f"[ImageTag] Compressed to {new_size_mb:.2f}MB (quality={quality})")
                    return temp_path
            
            # If still too big, return anyway (better than nothing)
            print(f"[ImageTag] Warning: Could only compress to {new_size_mb:.2f}MB")
            return temp_path
            
    except ImportError:
        print("[ImageTag] Warning: Pillow not installed. Cannot compress images.")
        return image_path
    except Exception as e:
        print(f"[ImageTag] Error compressing image: {e}")
        return image_path


def upload_image_to_whatsapp(image_path, phone_number_id, token, skip_compression=False):
    """
    Upload an image to WhatsApp Media API.
    
    Args:
        image_path: Absolute path to the image file
        phone_number_id: WhatsApp Business phone number ID
        token: WhatsApp API access token
        skip_compression: If True, skip compression (use for pre-compressed images)
        
    Returns:
        media_id (str) on success, None on failure
    """
    temp_path = None
    try:
        # Only compress if not skipped (pre-compressed images from ImageAssets skip this)
        if skip_compression:
            compressed_path = image_path
            print(f"[ImageTag] Using pre-compressed image (skipping runtime compression)")
        else:
            # Compress image first to avoid "file too large" errors
            compressed_path = compress_image_for_whatsapp(image_path)
            if compressed_path != image_path:
                temp_path = compressed_path  # Track for cleanup

        
        url = f"https://graph.facebook.com/v17.0/{phone_number_id}/media"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # Determine mime type from extension
        ext = os.path.splitext(compressed_path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')
        
        with open(compressed_path, 'rb') as f:
            files = {
                'file': (os.path.basename(compressed_path), f, mime_type)
            }
            data = {
                'messaging_product': 'whatsapp',
                'type': mime_type
            }
            
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
            
        if response.status_code == 200:
            result = response.json()
            media_id = result.get('id')
            print(f"[ImageTag] Image uploaded successfully. Media ID: {media_id}")
            return media_id
        else:
            print(f"[ImageTag] Failed to upload image. Status: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"[ImageTag] Error uploading image: {e}")
        return None
    finally:
        # Clean up temp file if created
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass



def send_whatsapp_image(media_id, phone, phone_number_id, token, caption=""):
    """
    Send an image message via WhatsApp API.
    
    Args:
        media_id: The WhatsApp media ID (from upload)
        phone: Recipient's phone number
        phone_number_id: WhatsApp Business phone number ID
        token: WhatsApp API access token
        caption: Optional caption for the image
        
    Returns:
        True on success, False on failure
    """
    try:
        url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "image",
            "image": {
                "id": media_id
            }
        }
        
        # Add caption if provided
        if caption and caption.strip():
            payload["image"]["caption"] = caption.strip()
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            print(f"[ImageTag] Image sent successfully to {phone}")
            return True
        else:
            print(f"[ImageTag] Failed to send image. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ImageTag] Error sending image: {e}")
        return False


def send_whatsapp_text(text, phone, phone_number_id, token):
    """
    Send a text message via WhatsApp API.
    
    Args:
        text: Message text to send
        phone: Recipient's phone number
        phone_number_id: WhatsApp Business phone number ID
        token: WhatsApp API access token
        
    Returns:
        True on success, False on failure
    """
    try:
        url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text}
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            print(f"[ImageTag] Text sent successfully to {phone}")
            return True
        else:
            print(f"[ImageTag] Failed to send text. Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ImageTag] Error sending text: {e}")
        return False


def process_response_with_images(response_text, admin, phone, phone_number_id, token, organization=None):
    """
    Process an AI response, extracting and sending any {{image:xxx}} tags as images.
    
    This is the main function to call from the WhatsApp controller.
    Images are sent WITH caption (text as caption on the image) for faster delivery.
    
    Args:
        response_text: The full AI response text
        admin: The Admin model instance
        phone: Recipient's phone number
        phone_number_id: WhatsApp Business phone number ID
        token: WhatsApp API access token
        organization: Organization model instance (optional)
        
    Returns:
        dict with:
            - 'success': bool - Whether processing completed without errors
            - 'images_sent': int - Number of images successfully sent
            - 'text_sent': bool - Whether text message was sent
            - 'final_text': str - The text with image tags removed (for saving to DB)
    """
    result = {
        'success': True,
        'images_sent': 0,
        'text_sent': False,
        'final_text': response_text
    }
    
    # Parse image tags
    image_tags = parse_image_tags(response_text)
    
    if not image_tags:
        # No image tags found, just send as regular text
        success = send_whatsapp_text(response_text, phone, phone_number_id, token)
        result['text_sent'] = success
        result['success'] = success
        return result
    
    print(f"[ImageTag] Found {len(image_tags)} image tag(s) in response")
    
    # Process each image tag - collect images and compute remaining text
    remaining_text = response_text
    images_to_send = []
    
    for full_tag, image_name in image_tags:
        # Look up the image asset
        asset = get_image_asset(image_name, admin, organization)
        
        if asset and asset.image:
            # Get the full path to the image
            image_path = asset.image.path
            
            if os.path.exists(image_path):
                images_to_send.append({
                    'path': image_path,
                    'name': image_name,
                    'tag': full_tag
                })
                print(f"[ImageTag] Found image asset: {image_name} -> {image_path}")
            else:
                print(f"[ImageTag] Warning: Image file not found at {image_path}")
        else:
            print(f"[ImageTag] Warning: Image asset '{image_name}' not found for admin")
        
        # Remove the tag from the text
        remaining_text = remaining_text.replace(full_tag, '').strip()
    
    # Clean up extra whitespace/newlines from removed tags
    remaining_text = re.sub(r'\n\s*\n', '\n\n', remaining_text).strip()
    result['final_text'] = remaining_text if remaining_text else "(Image sent)"
    
    # Send images WITH caption (text included as caption on image)
    # This combines text + image into one message for faster delivery
    for i, img_info in enumerate(images_to_send):
        # Upload image (no compression needed - already pre-compressed on upload)
        media_id = upload_image_to_whatsapp(img_info['path'], phone_number_id, token, skip_compression=True)
        
        if media_id:
            # For first image, include the text as caption
            # For additional images, send without caption
            caption = remaining_text if i == 0 and remaining_text else ""
            
            img_success = send_whatsapp_image(media_id, phone, phone_number_id, token, caption=caption)
            if img_success:
                result['images_sent'] += 1
                if i == 0 and remaining_text:
                    result['text_sent'] = True  # Text was sent as caption
            else:
                result['success'] = False
        else:
            result['success'] = False
            print(f"[ImageTag] Failed to upload image: {img_info['name']}")
    
    # If no images were sent but we have text, send text separately
    if result['images_sent'] == 0 and remaining_text:
        text_success = send_whatsapp_text(remaining_text, phone, phone_number_id, token)
        result['text_sent'] = text_success
    
    print(f"[ImageTag] Processing complete. Sent {result['images_sent']} image(s), text: {result['text_sent']}")
    return result

