from django.http import HttpResponse
from django.shortcuts import render,redirect
from ..models import Admin

class Settingcontroller :
    def dashboard(request):
        # return HttpResponse('hi')
        return render(request,'set/dashboard.html')
    def channels_view(request):
        # return render(re)
        whatsapp_connected=None
        admin_id=request.session.get('admin_id')
        if admin_id:
            admin=Admin.objects.filter(id=admin_id).only('whatsapp_phone_id','whatsapp_token').first()
            if admin:
              if admin.whatsapp_token!='' and admin.whatsapp_phone_id!='':
                  whatsapp_connected=True
        # return HttpResponse(whatsapp_connected)
        # return HttpResponse(whatsapp_connected)
        return render(request,'set/channels.html',{'whatsapp_connected':whatsapp_connected})
    
    def integration(request):
        pinecone_connected = None
        chatgpt_connected = False
        calendly_connected = False
        admin = None 
        chatgpt_mode = "N/A"
        admin_id = request.session.get('admin_id')

        if admin_id:
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
            'chatgpt_mode': chatgpt_mode,
        })
    
    def external_apis(request):
        from ..models import ExternalAPI
        admin_id = request.session.get('admin_id')
        apis = []
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                apis = ExternalAPI.objects.filter(admin=admin)
        
        return render(request, 'set/external_apis.html', {'apis': apis})
    
    @staticmethod
    def external_api_detail(request, api_id):
        from django.http import JsonResponse
        from ..models import ExternalAPI
        
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
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
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        try:
            data = json.loads(request.body)
            api = ExternalAPI.objects.create(
                admin=admin,
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
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
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
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
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
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        api = ExternalAPI.objects.filter(id=api_id, admin=admin).first()
        if not api:
            return JsonResponse({'error': 'API not found'}, status=404)
        
        try:
            headers = api.headers if isinstance(api.headers, dict) else {}
            payload = api.payload if isinstance(api.payload, dict) else {}
            
            if api.method == 'GET':
                response = requests.get(api.url, headers=headers, params=payload, timeout=30)
            elif api.method == 'POST':
                if api.body_type == 'json':
                    response = requests.post(api.url, headers=headers, json=payload, timeout=30)
                else:
                    response = requests.post(api.url, headers=headers, data=payload, timeout=30)
            elif api.method == 'PUT':
                response = requests.put(api.url, headers=headers, json=payload, timeout=30)
            elif api.method == 'PATCH':
                response = requests.patch(api.url, headers=headers, json=payload, timeout=30)
            elif api.method == 'DELETE':
                response = requests.delete(api.url, headers=headers, timeout=30)
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
            })
        except requests.exceptions.Timeout:
            return JsonResponse({'error': 'Request timed out'}, status=408)
        except requests.exceptions.RequestException as e:
            return JsonResponse({'error': str(e)}, status=500)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # ==================== IMAGE ASSETS ====================
    
    def image_assets(request):
        from ..models import ImageAsset
        admin_id = request.session.get('admin_id')
        assets = []
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                assets = ImageAsset.objects.filter(admin=admin).order_by('-created_at')
        
        return render(request, 'set/image_assets.html', {'assets': assets})
    
    @staticmethod
    def image_asset_create(request):
        from django.http import JsonResponse
        from ..models import ImageAsset
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            image_file = request.FILES.get('image')
            
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            if not image_file:
                return JsonResponse({'error': 'Image file is required'}, status=400)
            
            # Check for duplicate name
            if ImageAsset.objects.filter(admin=admin, name=name).exists():
                return JsonResponse({'error': f'An image with name "{name}" already exists'}, status=400)
            
            asset = ImageAsset.objects.create(
                admin=admin,
                name=name,
                description=description,
                image=image_file,
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
        from ..models import ImageAsset
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        asset = ImageAsset.objects.filter(id=asset_id, admin=admin).first()
        if not asset:
            return JsonResponse({'error': 'Image asset not found'}, status=404)
        
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            image_file = request.FILES.get('image')
            
            if name and name != asset.name:
                if ImageAsset.objects.filter(admin=admin, name=name).exclude(id=asset_id).exists():
                    return JsonResponse({'error': f'An image with name "{name}" already exists'}, status=400)
                asset.name = name
            
            if description is not None:
                asset.description = description
            
            if image_file:
                if asset.image:
                    asset.image.delete(save=False)
                asset.image = image_file
            
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
        from ..models import ImageAsset
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        admin = Admin.objects.filter(id=admin_id).first()
        if not admin:
            return JsonResponse({'error': 'Admin not found'}, status=404)
        
        asset = ImageAsset.objects.filter(id=asset_id, admin=admin).first()
        if not asset:
            return JsonResponse({'error': 'Image asset not found'}, status=404)
        
        if asset.image:
            asset.image.delete(save=False)
        
        asset.delete()
        return JsonResponse({'success': True})