from django.http import HttpResponse, JsonResponse
from django.shortcuts import render,redirect
from django.views.decorators.csrf import csrf_exempt
from ..models import Admin
import json
import requests

class Settingcontroller :
    def dashboard(request):
        # return HttpResponse('hi')
        return render(request,'set/dashboard.html')
    def channels_view(request):
        whatsapp_connected = None
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if org_id:
            # Organization-based auth
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_token and org.whatsapp_phone_id:
                whatsapp_connected = True
        elif admin_id:
            # Legacy admin-based auth
            admin = Admin.objects.filter(id=admin_id).only('whatsapp_phone_id', 'whatsapp_token').first()
            if admin and admin.whatsapp_token and admin.whatsapp_phone_id:
                whatsapp_connected = True
        
        return render(request, 'set/channels.html', {'whatsapp_connected': whatsapp_connected})
    
    def integration(request):
        pinecone_connected = None
        chatgpt_connected = False
        calendly_connected = False
        admin = None 
        chatgpt_mode = "N/A"
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if org_id:
            # New Organization Logic
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org:
                if org.pinecone_token: pinecone_connected = True
                if org.openai_api_key: chatgpt_connected = True
                if org.calendly_token: calendly_connected = True
                chatgpt_mode = org.chatgpt_mode
                
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            
            if admin:
                pinecone_token = admin.pinecone_token
                if pinecone_token != '':
                    pinecone_connected = True
                
                openai_key = admin.openai_api_key
                if openai_key and openai_key != '':
                    chatgpt_connected = True
                chatgpt_mode = admin.chatgpt_mode
                
                # Check Calendly connection
                if admin.calendly_token and admin.calendly_token.strip():
                    calendly_connected = True

        return render(request, 'set/integration.html', {
            'pinecone_connected': pinecone_connected,
            'chatgpt_connected': chatgpt_connected,
            'calendly_connected': calendly_connected,
            'admin': admin,
            'org': org if org_id else None,
            'chatgpt_mode': chatgpt_mode,
            'current_gpt_model': getattr(org, 'gpt_model', 'gpt-4o-mini') if org_id and org else 'gpt-4o-mini',
        })
    
    def external_apis(request):
        from ..models import ExternalAPI, CustomField, Organization
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        apis = []
        custom_fields = []
        
        if org_id:
            # Organization user - filter by organization
            apis = ExternalAPI.objects.filter(organization_id=org_id)
            custom_fields = CustomField.objects.filter(organization_id=org_id).order_by('name')
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                apis = ExternalAPI.objects.filter(admin=admin)
                custom_fields = CustomField.objects.filter(admin=admin).order_by('name')
        
        return render(request, 'set/external_apis.html', {
            'apis': apis,
            'custom_fields': custom_fields,
        })
    
    @staticmethod
    def external_api_detail(request, api_id):
        from django.http import JsonResponse
        from ..models import ExternalAPI
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        org = None
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        if org:
            api = ExternalAPI.objects.filter(id=api_id, organization_id=org_id).first()
        elif admin:
            api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
        else:
            api = None
        if not api:
            return JsonResponse({'error': 'API not found'}, status=404)
        
        return JsonResponse({
            'id': api.id,
            'name': api.name,
            'description': api.description,
            'url': api.url,
            'method': api.method,
            'headers': api.headers,
            'body_type': api.body_type,
            'payload': api.payload,
            'response_mapping': api.response_mapping,
        })
    
    @staticmethod
    def external_api_create(request):
        from django.http import JsonResponse
        from ..models import ExternalAPI
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        org = None
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            data = json.loads(request.body)
            api = ExternalAPI.objects.create(
                admin=admin,
                organization_id=org_id if org_id else None,
                name=data.get('name', ''),
                description=data.get('description', ''),
                url=data.get('url', ''),
                method=data.get('method', 'POST'),
                headers=data.get('headers', {}),
                body_type=data.get('body_type', 'json'),
                payload=data.get('payload', {}),
                response_mapping=data.get('response_mapping', []),
            )
            return JsonResponse({'success': True, 'id': api.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def external_api_update(request, api_id):
        from django.http import JsonResponse
        from ..models import ExternalAPI
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        org = None
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        if org:
            api = ExternalAPI.objects.filter(id=api_id, organization_id=org_id).first()
        elif admin:
            api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
        else:
            api = None
        if not api:
            return JsonResponse({'error': 'API not found'}, status=404)
        
        try:
            data = json.loads(request.body)
            api.name = data.get('name', api.name)
            api.description = data.get('description', api.description)
            api.url = data.get('url', api.url)
            api.method = data.get('method', api.method)
            api.headers = data.get('headers', api.headers)
            api.body_type = data.get('body_type', api.body_type)
            api.payload = data.get('payload', api.payload)
            api.response_mapping = data.get('response_mapping', api.response_mapping)
            api.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def external_api_delete(request, api_id):
        from django.http import JsonResponse
        from ..models import ExternalAPI
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        org = None
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        if org:
            api = ExternalAPI.objects.filter(id=api_id, organization_id=org_id).first()
        elif admin:
            api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
        else:
            api = None
        if not api:
            return JsonResponse({'error': 'API not found'}, status=404)
        
        api.delete()
        return JsonResponse({'success': True})
    
    @staticmethod
    def external_api_test(request, api_id):
        from django.http import JsonResponse
        from ..models import ExternalAPI
        import requests
        import json
        import re
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        org = None
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        if org:
            api = ExternalAPI.objects.filter(id=api_id, organization_id=org_id).first()
        elif admin:
            api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
        else:
            api = None
        if not api:
            return JsonResponse({'error': 'API not found'}, status=404)
        
        try:
            # Get test parameters from request body
            test_params = {}
            try:
                body = json.loads(request.body)
                test_params = body.get('test_params', {})
            except:
                pass
            
            # If no test params provided, extract {param} placeholders from URL and use sample values
            if not test_params:
                placeholders = re.findall(r'\{(\w+)\}', api.url)
                for p in placeholders:
                    test_params[p] = f'1'  # Default test value
            
            headers = api.headers if isinstance(api.headers, dict) else {}
            payload = api.payload if isinstance(api.payload, dict) else {}
            
            # Substitute {param} placeholders in URL with test values
            url = api.url
            for key, value in test_params.items():
                url = url.replace('{' + key + '}', str(value))
            
            # Also substitute in payload values
            if payload:
                payload_str = json.dumps(payload)
                for key, value in test_params.items():
                    payload_str = payload_str.replace('{' + key + '}', str(value))
                    payload_str = payload_str.replace('{{custom_field:' + key + ':value}}', str(value))
                payload = json.loads(payload_str)
            
            if api.method == 'GET':
                response = requests.get(url, headers=headers, params=payload, timeout=30)
            elif api.method == 'POST':
                if api.body_type == 'json':
                    response = requests.post(url, headers=headers, json=payload, timeout=30)
                else:
                    response = requests.post(url, headers=headers, data=payload, timeout=30)
            elif api.method == 'PUT':
                response = requests.put(url, headers=headers, json=payload, timeout=30)
            elif api.method == 'PATCH':
                response = requests.patch(url, headers=headers, json=payload, timeout=30)
            elif api.method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return JsonResponse({'error': f'Unsupported method: {api.method}'}, status=400)
            
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            return JsonResponse({
                'success': True,
                'status_code': response.status_code,
                'response': response_data,
                'url_called': url,
            })
        except requests.exceptions.Timeout:
            return JsonResponse({'error': 'Request timed out'}, status=408)
        except requests.exceptions.RequestException as e:
            return JsonResponse({'error': str(e)}, status=500)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # ==================== IMAGE ASSETS ====================
    
    @staticmethod
    def compress_uploaded_image(image_file, max_dimension=1024, quality=85):
        """
        Compress an uploaded image file before saving.
        Resizes to max_dimension and compresses to JPEG.
        
        Args:
            image_file: Django UploadedFile object
            max_dimension: Maximum width/height in pixels
            quality: JPEG quality (1-100)
            
        Returns:
            Compressed image file (InMemoryUploadedFile or original)
        """
        try:
            from PIL import Image
            from io import BytesIO
            from django.core.files.uploadedfile import InMemoryUploadedFile
            import os
            
            # Open image
            img = Image.open(image_file)
            original_format = img.format
            
            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"[ImageAsset] Resized from {img.size} to {new_size}")
            
            # Save to buffer
            buffer = BytesIO()
            img.save(buffer, 'JPEG', quality=quality, optimize=True)
            buffer.seek(0)
            
            # Get new filename with .jpg extension
            original_name = image_file.name
            base_name = os.path.splitext(original_name)[0]
            new_name = f"{base_name}.jpg"
            
            # Create new InMemoryUploadedFile
            compressed_file = InMemoryUploadedFile(
                file=buffer,
                field_name='image',
                name=new_name,
                content_type='image/jpeg',
                size=buffer.getbuffer().nbytes,
                charset=None
            )
            
            print(f"[ImageAsset] Compressed image: {buffer.getbuffer().nbytes / 1024:.1f}KB")
            return compressed_file
            
        except ImportError:
            print("[ImageAsset] Warning: Pillow not installed. Cannot compress images.")
            return image_file
        except Exception as e:
            print(f"[ImageAsset] Error compressing image: {e}")
            return image_file
    
    def image_assets(request):
        from ..models import ImageAsset, Organization
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        assets = []
        
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
            if org:
                assets = ImageAsset.objects.filter(organization=org).order_by('-created_at')
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                assets = ImageAsset.objects.filter(admin=admin).order_by('-created_at')
        
        return render(request, 'set/image_assets.html', {'assets': assets})
    
    @staticmethod
    @csrf_exempt
    def image_asset_create(request):
        from django.http import JsonResponse
        from ..models import ImageAsset, Organization
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        # Support both organization and admin auth
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        admin = None
        org = None
        
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            image_file = request.FILES.get('image')
            
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            if not image_file:
                return JsonResponse({'error': 'Image file is required'}, status=400)
            
            # Check for duplicate name
            if org:
                if ImageAsset.objects.filter(organization=org, name=name).exists():
                    return JsonResponse({'error': f'An image with name "{name}" already exists'}, status=400)
            elif admin:
                if ImageAsset.objects.filter(admin=admin, name=name).exists():
                    return JsonResponse({'error': f'An image with name "{name}" already exists'}, status=400)
            
            # Compress image before saving
            compressed_image = Settingcontroller.compress_uploaded_image(image_file)
            
            asset = ImageAsset.objects.create(
                admin=admin,
                organization=org,
                name=name,
                description=description,
                image=compressed_image,
            )
            return JsonResponse({
                'success': True,
                'id': asset.id,
                'image_url': asset.image.url if asset.image else None
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def image_asset_update(request, asset_id):
        from django.http import JsonResponse
        from ..models import ImageAsset, Organization
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        admin = None
        org = None
        
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        if org:
            asset = ImageAsset.objects.filter(id=asset_id, organization=org).first()
        else:
            asset = ImageAsset.objects.filter(id=asset_id, admin=admin).first()
            
        if not asset:
            return JsonResponse({'error': 'Image asset not found'}, status=404)
        
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            image_file = request.FILES.get('image')
            
            if name and name != asset.name:
                exists = False
                if org:
                    exists = ImageAsset.objects.filter(organization=org, name=name).exclude(id=asset_id).exists()
                else:
                    exists = ImageAsset.objects.filter(admin=admin, name=name).exclude(id=asset_id).exists()
                
                if exists:
                    return JsonResponse({'error': f'An image with name "{name}" already exists'}, status=400)
                asset.name = name
            
            if description is not None:
                asset.description = description
            
            if image_file:
                if asset.image:
                    asset.image.delete(save=False)
                # Compress image before saving
                compressed_image = Settingcontroller.compress_uploaded_image(image_file)
                asset.image = compressed_image
            
            asset.save()
            return JsonResponse({
                'success': True,
                'image_url': asset.image.url if asset.image else None
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def image_asset_delete(request, asset_id):
        from django.http import JsonResponse
        from ..models import ImageAsset, Organization
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        admin = None
        org = None
        
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        
        if not admin and not org:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            if org:
                result = ImageAsset.objects.filter(id=asset_id, organization=org).delete()
            else:
                result = ImageAsset.objects.filter(id=asset_id, admin=admin).delete()
            
            if result[0] > 0:
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'error': 'Image asset not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    # ===================== FOLLOW-UP SETTINGS =====================
    
    @staticmethod
    def followup_settings(request):
        from ..models import FollowUpMessage, Admin, Tag, WhatsAppTemplate
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        # Get admin - either from session or via org's WhatsApp phone ID
        admin = None
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
            
        if not admin:
            # Follow-ups require an Admin record to be linked
            return render(request, 'set/followup_settings.html', {
                'admin': None,
                'followups': [],
                'tags': Tag.objects.none(),
                'templates': WhatsAppTemplate.objects.none(),
                'error_message': 'Follow-up settings require a WhatsApp connection. Please connect WhatsApp first in Settings > Channels.'
            })
        
        followups = FollowUpMessage.objects.filter(admin=admin).order_by('step')
        
        # Get tags for the dropdown - filter by org or admin
        if org_id:
            tags = Tag.objects.filter(organization_id=org_id)
        elif admin_id:
            tags = Tag.objects.filter(admin_id=admin_id)
        else:
            tags = Tag.objects.none()
        
        # Get approved WhatsApp templates for the template picker
        # Query by BOTH org and admin to ensure we find templates regardless of how they were synced
        from django.db.models import Q
        q_filter = Q()
        if org_id:
            q_filter |= Q(organization_id=org_id)
        if admin_id:
            q_filter |= Q(admin_id=admin_id)
        if admin:
            q_filter |= Q(admin_id=admin.id)
        if q_filter:
            templates = WhatsAppTemplate.objects.filter(q_filter, status='APPROVED').distinct()
        else:
            templates = WhatsAppTemplate.objects.none()
        
        return render(request, 'set/followup_settings.html', {
            'admin': admin,
            'followups': followups,
            'tags': tags,
            'templates': templates
        })
    
    @staticmethod
    def followup_create(request):
        from django.http import JsonResponse
        from ..models import FollowUpMessage
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        # Get admin - either from session or via org's WhatsApp phone ID
        admin = None
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin:
            return JsonResponse({'error': 'Follow-up settings require a WhatsApp connection. Please connect WhatsApp first.'}, status=404)
        
        # Check limit (max 4)
        existing_count = FollowUpMessage.objects.filter(admin=admin).count()
        if existing_count >= 4:
            return JsonResponse({'error': 'Maximum 4 follow-ups allowed'}, status=400)
        
        try:
            data = json.loads(request.body)
            next_step = existing_count + 1
            
            use_template = data.get('use_template', False)
            if isinstance(use_template, str):
                use_template = use_template.lower() in ('true', '1', 'on')
            
            followup = FollowUpMessage.objects.create(
                admin=admin,
                step=next_step,
                delay_minutes=data.get('delay_minutes', 10),
                message=data.get('message', ''),
                tag_id=data.get('tag_id') or None,
                use_template=use_template,
                template_id=data.get('template_id') or None
            )
            
            return JsonResponse({'success': True, 'id': followup.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def followup_update(request, followup_id):
        from django.http import JsonResponse
        from ..models import FollowUpMessage
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        admin = None
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        followup = FollowUpMessage.objects.filter(id=followup_id, admin=admin).first()
        if not followup:
            return JsonResponse({'error': 'Follow-up not found'}, status=404)
        
        try:
            data = json.loads(request.body)
            followup.delay_minutes = data.get('delay_minutes', followup.delay_minutes)
            followup.message = data.get('message', followup.message)
            if 'tag_id' in data:
                followup.tag_id = data.get('tag_id') or None
            if 'use_template' in data:
                use_template = data['use_template']
                if isinstance(use_template, str):
                    use_template = use_template.lower() in ('true', '1', 'on')
                followup.use_template = use_template
            if 'template_id' in data:
                followup.template_id = data.get('template_id') or None
            followup.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def followup_delete(request, followup_id):
        from django.http import JsonResponse
        from ..models import FollowUpMessage
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        admin = None
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        followup = FollowUpMessage.objects.filter(id=followup_id, admin=admin).first()
        if not followup:
            return JsonResponse({'error': 'Follow-up not found'}, status=404)
        
        deleted_step = followup.step
        followup.delete()
        
        # Renumber remaining steps
        remaining = FollowUpMessage.objects.filter(admin=admin, step__gt=deleted_step).order_by('step')
        for i, f in enumerate(remaining, start=deleted_step):
            f.step = i
            f.save()
        
        return JsonResponse({'success': True})
    
    @staticmethod
    def followup_toggle(request):
        from django.http import JsonResponse
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        admin = None
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        try:
            data = json.loads(request.body)
            admin.followup_enabled = data.get('enabled', True)
            admin.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    # ===================== TAG MANAGEMENT =====================
    
    @staticmethod
    def tags_view(request):
        from ..models import Tag, Organization
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        tags = []
        admin = None
        org = None
        
        if org_id:
            # Organization user - filter tags by organization
            org = Organization.objects.filter(id=org_id).first()
            if org:
                tags = Tag.objects.filter(organization=org).order_by('-created_at')
        elif admin_id:
            # Admin user - filter tags by admin
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                tags = Tag.objects.filter(admin=admin).order_by('-created_at')
        else:
            return redirect('/login/')
        
        return render(request, 'set/tags.html', {
            'admin': admin,
            'tags': tags
        })
    
    @staticmethod
    def tag_create(request):
        from django.http import JsonResponse
        from ..models import Tag, Organization
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if not admin_id and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()
            
            if not name:
                return JsonResponse({'error': 'Tag name is required'}, status=400)
            
            if org_id:
                # Organization user - create tag for organization
                org = Organization.objects.filter(id=org_id).first()
                if not org:
                    return JsonResponse({'error': 'Organization not found'}, status=404)
                
                # Check for duplicate within organization
                if Tag.objects.filter(organization=org, name__iexact=name).exists():
                    return JsonResponse({'error': 'Tag already exists'}, status=400)
                
                tag = Tag.objects.create(
                    organization=org,
                    name=name,
                    description=description,
                    keyword=data.get('keyword', '').strip() or None,
                    auto_apply=data.get('auto_apply', False)
                )
            else:
                # Admin user - create tag for admin
                admin = Admin.objects.filter(id=admin_id).first()
                if not admin:
                    return JsonResponse({'error': 'Admin not found'}, status=404)
                
                # Check for duplicate within admin
                if Tag.objects.filter(admin=admin, name__iexact=name).exists():
                    return JsonResponse({'error': 'Tag already exists'}, status=400)
                
                tag = Tag.objects.create(
                    admin=admin,
                    name=name,
                    description=description,
                    keyword=data.get('keyword', '').strip() or None,
                    auto_apply=data.get('auto_apply', False)
                )
            
            return JsonResponse({'success': True, 'id': tag.id, 'name': tag.name})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def tag_update(request, tag_id):
        from django.http import JsonResponse
        from ..models import Tag, Organization
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if not admin_id and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Find tag based on user type
        tag = None
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
            if org:
                tag = Tag.objects.filter(id=tag_id, organization=org).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                tag = Tag.objects.filter(id=tag_id, admin=admin).first()
        
        if not tag:
            return JsonResponse({'error': 'Tag not found'}, status=404)
        
        try:
            data = json.loads(request.body)
            tag.name = data.get('name', tag.name).strip()
            tag.description = data.get('description', tag.description).strip()
            tag.keyword = data.get('keyword', tag.keyword or '').strip() or None
            tag.auto_apply = data.get('auto_apply', tag.auto_apply)
            tag.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def tag_delete(request, tag_id):
        from django.http import JsonResponse
        from ..models import Tag, Organization
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if not admin_id and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Find tag based on user type
        tag = None
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
            if org:
                tag = Tag.objects.filter(id=tag_id, organization=org).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                tag = Tag.objects.filter(id=tag_id, admin=admin).first()
        
        if not tag:
            return JsonResponse({'error': 'Tag not found'}, status=404)
        
        tag.delete()
        return JsonResponse({'success': True})
    
    # ===================== CUSTOM FIELD MANAGEMENT =====================
    
    @staticmethod
    def custom_fields_view(request):
        from ..models import CustomField, Organization
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        custom_fields = []
        admin = None
        org = None
        
        if org_id:
            # Organization user - filter custom fields by organization
            org = Organization.objects.filter(id=org_id).first()
            if org:
                custom_fields = CustomField.objects.filter(organization=org).order_by('-created_at')
        elif admin_id:
            # Admin user - filter custom fields by admin
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                custom_fields = CustomField.objects.filter(admin=admin).order_by('-created_at')
        else:
            return redirect('/login/')
        
        return render(request, 'set/custom_fields.html', {
            'admin': admin,
            'custom_fields': custom_fields
        })
    
    @staticmethod
    def custom_field_create(request):
        from django.http import JsonResponse
        from ..models import CustomField, Organization
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if not admin_id and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            field_type = data.get('field_type', 'text').strip()
            description = data.get('description', '').strip()
            is_required = data.get('is_required', False)
            
            if not name:
                return JsonResponse({'error': 'Field name is required'}, status=400)
            
            # Validate field_type
            valid_types = [choice[0] for choice in CustomField.FIELD_TYPE_CHOICES]
            if field_type not in valid_types:
                return JsonResponse({'error': f'Invalid field type. Must be one of: {", ".join(valid_types)}'}, status=400)
            
            if org_id:
                # Organization user - create custom field for organization
                org = Organization.objects.filter(id=org_id).first()
                if not org:
                    return JsonResponse({'error': 'Organization not found'}, status=404)
                
                # Check for duplicate within organization
                if CustomField.objects.filter(organization=org, name__iexact=name).exists():
                    return JsonResponse({'error': 'Custom field already exists'}, status=400)
                
                custom_field = CustomField.objects.create(
                    organization=org,
                    name=name,
                    field_type=field_type,
                    description=description,
                    is_required=is_required
                )
            else:
                # Admin user - create custom field for admin
                admin = Admin.objects.filter(id=admin_id).first()
                if not admin:
                    return JsonResponse({'error': 'Admin not found'}, status=404)
                
                # Check for duplicate within admin
                if CustomField.objects.filter(admin=admin, name__iexact=name).exists():
                    return JsonResponse({'error': 'Custom field already exists'}, status=400)
                
                custom_field = CustomField.objects.create(
                    admin=admin,
                    name=name,
                    field_type=field_type,
                    description=description,
                    is_required=is_required
                )
            
            return JsonResponse({'success': True, 'id': custom_field.id, 'name': custom_field.name})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def custom_field_update(request, field_id):
        from django.http import JsonResponse
        from ..models import CustomField, Organization
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if not admin_id and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Find custom field based on user type
        custom_field = None
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
            if org:
                custom_field = CustomField.objects.filter(id=field_id, organization=org).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                custom_field = CustomField.objects.filter(id=field_id, admin=admin).first()
        
        if not custom_field:
            return JsonResponse({'error': 'Custom field not found'}, status=404)
        
        try:
            data= json.loads(request.body)
            name = data.get('name', '').strip()
            field_type = data.get('field_type', '').strip()
            description = data.get('description', '').strip()
            is_required = data.get('is_required', custom_field.is_required)
            is_active = data.get('is_active', custom_field.is_active)
            
            # Validate field_type if provided
            if field_type:
                valid_types = [choice[0] for choice in CustomField.FIELD_TYPE_CHOICES]
                if field_type not in valid_types:
                    return JsonResponse({'error': f'Invalid field type. Must be one of: {", ".join(valid_types)}'}, status=400)
                custom_field.field_type = field_type
            
            if name:
                # Check for duplicate name if changing
                if name.lower() != custom_field.name.lower():
                    if org_id:
                        org = Organization.objects.filter(id=org_id).first()
                        if org and CustomField.objects.filter(organization=org, name__iexact=name).exclude(id=field_id).exists():
                            return JsonResponse({'error': 'Custom field with this name already exists'}, status=400)
                    elif admin_id:
                        admin = Admin.objects.filter(id=admin_id).first()
                        if admin and CustomField.objects.filter(admin=admin, name__iexact=name).exclude(id=field_id).exists():
                            return JsonResponse({'error': 'Custom field with this name already exists'}, status=400)
                custom_field.name = name
            
            custom_field.description = description
            custom_field.is_required = is_required
            custom_field.is_active = is_active
            custom_field.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def custom_field_delete(request, field_id):
        from django.http import JsonResponse
        from ..models import CustomField, Organization
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if not admin_id and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Find custom field based on user type
        custom_field = None
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
            if org:
                custom_field = CustomField.objects.filter(id=field_id, organization=org).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                custom_field = CustomField.objects.filter(id=field_id, admin=admin).first()
        
        if not custom_field:
            return JsonResponse({'error': 'Custom field not found'}, status=404)
        
        custom_field.delete()
        return JsonResponse({'success': True})
    
    @staticmethod
    def custom_field_list(request):
        from django.http import JsonResponse
        from ..models import CustomField, Organization
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        if not admin_id and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            custom_fields = []
            if org_id:
                org = Organization.objects.filter(id=org_id).first()
                if org:
                    custom_fields = CustomField.objects.filter(organization=org, is_active=True)
            elif admin_id:
                admin = Admin.objects.filter(id=admin_id).first()
                if admin:
                    custom_fields = CustomField.objects.filter(admin=admin, is_active=True)
            
            fields_data = [{
                'id': cf.id,
                'name': cf.name,
                'field_type': cf.field_type,
                'description': cf.description,
                'is_required': cf.is_required
            } for cf in custom_fields]
            
            return JsonResponse({'success': True, 'custom_fields': fields_data})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    # ==================== CALENDLY LINKS ====================

    @staticmethod
    def calendly_links(request):
        from ..models import CalendlyLink, CustomField, Organization
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        links = []
        calendly_connected = False
        calendly_url = ''
        custom_fields = []
        
        if org_id:
            links = CalendlyLink.objects.filter(organization_id=org_id).order_by('-created_at')
            org = Organization.objects.filter(id=org_id).first()
            if org:
                calendly_connected = bool(getattr(org, 'calendly_token', ''))
                calendly_url = getattr(org, 'calendly_scheduling_url', '') or ''
            custom_fields = CustomField.objects.filter(organization_id=org_id, is_active=True).order_by('name')
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                links = CalendlyLink.objects.filter(admin=admin).order_by('-created_at')
                calendly_connected = bool(getattr(admin, 'calendly_token', ''))
                calendly_url = getattr(admin, 'calendly_scheduling_url', '') or ''
            custom_fields = CustomField.objects.filter(admin_id=admin_id, is_active=True).order_by('name')
        
        return render(request, 'set/calendly_links.html', {
            'links': links,
            'calendly_connected': calendly_connected,
            'calendly_url': calendly_url,
            'custom_fields': custom_fields,
        })

    @staticmethod
    @csrf_exempt
    def calendly_link_create(request):
        from ..models import CalendlyLink, Organization
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()
            url = data.get('url', '').strip()
            custom_field_name = data.get('custom_field_name', '').strip()
            booking_message = data.get('booking_message', '').strip()
            
            if not name or not url:
                return JsonResponse({'error': 'Name and URL are required'}, status=400)
            
            link = CalendlyLink.objects.create(
                admin=admin,
                organization_id=org_id if org_id else None,
                name=name,
                description=description,
                url=url,
                custom_field_name=custom_field_name,
                booking_message=booking_message,
            )
            
            return JsonResponse({
                'success': True,
                'id': link.id,
                'msg': f'Calendly link "{name}" created!'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    @staticmethod
    @csrf_exempt
    def calendly_link_update(request, link_id):
        from ..models import CalendlyLink, Organization
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        link = None
        if org_id:
            link = CalendlyLink.objects.filter(id=link_id, organization_id=org_id).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                link = CalendlyLink.objects.filter(id=link_id, admin=admin).first()
        
        if not link:
            return JsonResponse({'error': 'Link not found'}, status=404)
        
        try:
            data = json.loads(request.body)
            link.name = data.get('name', link.name).strip()
            link.description = data.get('description', link.description).strip()
            link.url = data.get('url', link.url).strip()
            link.custom_field_name = data.get('custom_field_name', link.custom_field_name).strip()
            link.booking_message = data.get('booking_message', link.booking_message).strip()
            link.save()
            
            return JsonResponse({'success': True, 'msg': 'Link updated!'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    @staticmethod
    @csrf_exempt
    def calendly_link_delete(request, link_id):
        from ..models import CalendlyLink, Organization
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        link = None
        if org_id:
            link = CalendlyLink.objects.filter(id=link_id, organization_id=org_id).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                link = CalendlyLink.objects.filter(id=link_id, admin=admin).first()
        
        if not link:
            return JsonResponse({'error': 'Link not found'}, status=404)
        
        link.delete()
        return JsonResponse({'success': True, 'msg': 'Link deleted!'})

    # ==================== PROMPT MANAGEMENT (Multi-Agent) ====================
    @staticmethod
    def prompt_list(request):
        """AI Agent page — list all prompts for prompt management."""
        from ..models import ChatGPTPrompt, Organization, Admin
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        if not admin_id and not org_id:
            return redirect('/login')
        
        prompts = ChatGPTPrompt.objects.none()
        org = None
        admin = None
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
            prompts = ChatGPTPrompt.objects.filter(organization_id=org_id).order_by('-is_default', '-updated_at')
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            prompts = ChatGPTPrompt.objects.filter(admin=admin).order_by('-is_default', '-updated_at')
        
        return render(request, 'set/ai_agent.html', {
            'prompts': prompts,
            'organization': org,
            'admin': admin,
        })

    @staticmethod
    def prompt_create(request):
        """Create a new prompt."""
        from ..models import ChatGPTPrompt, Organization, Admin
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        name = data.get('name', 'New Prompt').strip()
        prompt_text = data.get('prompt_text', '').strip()
        gpt_model = data.get('gpt_model', '').strip()
        is_default = data.get('is_default', False)
        if isinstance(is_default, str):
            is_default = is_default.lower() in ('true', '1', 'on')
        
        prompt = ChatGPTPrompt(name=name, prompt_text=prompt_text, gpt_model=gpt_model, is_default=is_default)
        
        if org_id:
            prompt.organization_id = org_id
            if is_default:
                ChatGPTPrompt.objects.filter(organization_id=org_id, is_default=True).update(is_default=False)
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            prompt.admin = admin
            if is_default:
                ChatGPTPrompt.objects.filter(admin=admin, is_default=True).update(is_default=False)
        
        prompt.save()
        return JsonResponse({'success': True, 'id': prompt.id, 'msg': 'Prompt created!'})

    @staticmethod
    def prompt_update(request, prompt_id):
        """Update a prompt."""
        from ..models import ChatGPTPrompt, Organization, Admin
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        prompt = None
        if org_id:
            prompt = ChatGPTPrompt.objects.filter(id=prompt_id, organization_id=org_id).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                prompt = ChatGPTPrompt.objects.filter(id=prompt_id, admin=admin).first()
        
        if not prompt:
            return JsonResponse({'error': 'Prompt not found'}, status=404)
        
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        if 'name' in data:
            prompt.name = data['name'].strip()
        if 'prompt_text' in data:
            prompt.prompt_text = data['prompt_text'].strip()
        if 'gpt_model' in data:
            prompt.gpt_model = data['gpt_model'].strip()
        if 'is_default' in data:
            is_default = data['is_default']
            if isinstance(is_default, str):
                is_default = is_default.lower() in ('true', '1', 'on')
            if is_default:
                if org_id:
                    ChatGPTPrompt.objects.filter(organization_id=org_id, is_default=True).update(is_default=False)
                elif admin_id:
                    admin = Admin.objects.filter(id=admin_id).first()
                    if admin:
                        ChatGPTPrompt.objects.filter(admin=admin, is_default=True).update(is_default=False)
            prompt.is_default = is_default
        
        prompt.save()
        return JsonResponse({'success': True, 'msg': 'Prompt updated!'})

    @staticmethod
    def prompt_delete(request, prompt_id):
        """Delete a prompt."""
        from ..models import ChatGPTPrompt, Organization, Admin
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        prompt = None
        if org_id:
            prompt = ChatGPTPrompt.objects.filter(id=prompt_id, organization_id=org_id).first()
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                prompt = ChatGPTPrompt.objects.filter(id=prompt_id, admin=admin).first()
        
        if not prompt:
            return JsonResponse({'error': 'Prompt not found'}, status=404)
        
        prompt.delete()
        return JsonResponse({'success': True, 'msg': 'Prompt deleted!'})


    # ==================== GOOGLE CALENDAR LINKS ====================

    def gcalendar_links(request):
        """Google Calendar links management page."""
        from ..models import GoogleCalendarLink, Organization
        from django.db.models import Q

        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')

        links = GoogleCalendarLink.objects.none()
        if org_id:
            links = GoogleCalendarLink.objects.filter(organization_id=org_id).order_by('-created_at')
        elif admin_id:
            links = GoogleCalendarLink.objects.filter(
                Q(admin_id=admin_id) | Q(organization__isnull=True, admin_id=admin_id)
            ).order_by('-created_at')

        return render(request, 'set/gcalendar_links.html', {'links': links})

    @csrf_exempt
    def gcalendar_link_save(request):
        """Create or update a Google Calendar link."""
        from ..models import GoogleCalendarLink, Organization
        if request.method != 'POST':
            return JsonResponse({'error': 'POST only'}, status=405)

        data = json.loads(request.body)
        link_id = data.get('id')
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')

        fields = {
            'name': data.get('name', '').strip(),
            'description': data.get('description', '').strip(),
            'calendar_id': data.get('calendar_id', '').strip(),
            'duration_minutes': int(data.get('duration_minutes', 30)),
            'service_account_json': data.get('service_account_json', '').strip(),
            'custom_field_name': data.get('custom_field_name', '').strip(),
            'booking_message': data.get('booking_message', '').strip(),
            'start_hour': int(data.get('start_hour', 9)),
            'end_hour': int(data.get('end_hour', 17)),
            'timezone': data.get('timezone', 'Asia/Kuala_Lumpur').strip(),
            'is_active': data.get('is_active', True),
        }

        available_days = data.get('available_days', [])
        if isinstance(available_days, list):
            fields['available_days'] = available_days

        if not fields['name'] or not fields['calendar_id']:
            return JsonResponse({'error': 'Name and Calendar ID are required'}, status=400)

        if link_id:
            # Update
            link = GoogleCalendarLink.objects.filter(id=link_id).first()
            if not link:
                return JsonResponse({'error': 'Link not found'}, status=404)
            for k, v in fields.items():
                setattr(link, k, v)
            link.save()
        else:
            # Create
            link = GoogleCalendarLink(**fields)
            if org_id:
                link.organization_id = org_id
            elif admin_id:
                link.admin_id = admin_id
            link.save()

        return JsonResponse({'success': True, 'id': link.id})

    @csrf_exempt
    def gcalendar_link_delete(request, link_id):
        """Delete a Google Calendar link."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST only'}, status=405)
        from ..models import GoogleCalendarLink
        link = GoogleCalendarLink.objects.filter(id=link_id).first()
        if not link:
            return JsonResponse({'error': 'Not found'}, status=404)
        link.delete()
        return JsonResponse({'success': True})
