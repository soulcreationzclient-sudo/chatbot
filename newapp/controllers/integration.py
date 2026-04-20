from django.http import JsonResponse
from django.http import HttpResponse
from newapp.models import Admin
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from newapp.models import AIAgentConfig
from newapp.forms import AIAgentConfigForm
import pdfplumber
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from newapp.models import Admin


class Integrationcontroller:

    @csrf_exempt
    def connect(request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            api_key = data.get("api_key")
            assistant_name = data.get("assistant_name")

            if not api_key or not assistant_name:
                return JsonResponse({"msg": "API key and Assistant Name are required"}, status=400)

            # Disconnect ChatGPT api key
            Admin.objects.update(openai_api_key='')

            # Connect Pinecone and store Assistant Name
            Admin.objects.update(pinecone_token=api_key, assistant_name=assistant_name)

            return JsonResponse({"msg": "Pinecone connected; Assistant Name saved."})
        except Exception as e:
            return JsonResponse({"msg": str(e)}, status=500)
    def disconnect(request):
        try:
            Admin.objects.update(pinecone_token='')
            return JsonResponse({'msg': 'Pinecone disconnected successfully.'})
        except Exception as e:
            return JsonResponse({'msg': str(e)}, status=500)    
        
    # @csrf_exempt
    # def ai_agent_upload(self, request):
    #     if request.method == 'POST':
    #         pdf_file = request.FILES.get('pdf_file')
    #         instruction = request.POST.get('instruction', '')
    #         # save/process file and instruction here
    #         return JsonResponse({'msg': 'Upload successful'})
        
    #     return render(request, 'set/ai_agent.html')
    
    # @csrf_exempt
    # def ai_agent_upload(self, request):
    #     if request.method == 'POST':
    #         form = AIAgentConfigForm(request.POST, request.FILES)
    #         if form.is_valid():
    #             ai_agent = form.save()
    #             pdf_path = ai_agent.pdf_file.path
    #             pdf_text = self.extract_pdf_text(pdf_path)
    #             ai_agent.pdf_text = pdf_text
    #             ai_agent.save()
    #             return redirect('ai_agent_upload')
    #     else:
    #         form = AIAgentConfigForm()

    #     uploaded_pdfs = AIAgentConfig.objects.all().order_by('-uploaded_at')
    #     return render(request, 'set/ai_agent.html', {
    #         'form': form,
    #         'uploaded_pdfs': uploaded_pdfs,
    #     })
    @csrf_exempt
    def ai_agent_upload(self, request):
        from newapp.models import Organization
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if request.method == 'POST':
            agent_id = request.POST.get('agent_id')
            name = request.POST.get('name', 'Default Agent')
            instruction = request.POST.get('instruction', '')
            is_default = request.POST.get('is_default') == 'on'
            pdf_file = request.FILES.get('pdf_file')
            
            if agent_id:
                # Update existing agent
                agent = AIAgentConfig.objects.filter(id=agent_id).first()
                if agent:
                    agent.name = name
                    agent.instruction = instruction
                    if pdf_file:
                        agent.pdf_file = pdf_file
                        agent.save()
                        agent.pdf_text = self.extract_pdf_text(agent.pdf_file.path)
                    agent.save()
            else:
                # Create new agent
                agent = AIAgentConfig(
                    name=name,
                    instruction=instruction,
                    is_default=is_default,
                )
                if org_id:
                    agent.organization_id = org_id
                if admin_id:
                    agent.admin_id = admin_id
                if pdf_file:
                    agent.pdf_file = pdf_file
                    agent.save()
                    agent.pdf_text = self.extract_pdf_text(agent.pdf_file.path)
                    agent.save()
                else:
                    agent.pdf_file = ''
                    agent.save()
            
            # Handle is_default
            if is_default:
                # Unset other defaults for this org/admin
                q = AIAgentConfig.objects.exclude(id=agent.id)
                if org_id:
                    q = q.filter(organization_id=org_id)
                elif admin_id:
                    q = q.filter(admin_id=admin_id)
                q.update(is_default=False)
                agent.is_default = True
                agent.save()
            
            return redirect('ai_agent_upload')
        
        # GET: List all agents
        if org_id:
            agents = AIAgentConfig.objects.filter(organization_id=org_id).order_by('-is_default', '-uploaded_at')
        elif admin_id:
            agents = AIAgentConfig.objects.filter(admin_id=admin_id).order_by('-is_default', '-uploaded_at')
        else:
            agents = AIAgentConfig.objects.none()
        
        # Add computed properties for template
        agent_list = []
        for a in agents:
            a.pdf_count = 1 if a.pdf_file else 0
            a.pdf_list = [a.pdf_file.name.split('/')[-1]] if a.pdf_file else []
            agent_list.append(a)
        
        return render(request, 'set/ai_agent.html', {
            'agents': agent_list,
        })

    @staticmethod
    @csrf_exempt 
    def set_default_agent(request):
        """Set an agent as the default for the org/admin."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        import json
        data = json.loads(request.body)
        agent_id = data.get('agent_id')
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        agent = AIAgentConfig.objects.filter(id=agent_id).first()
        if not agent:
            return JsonResponse({'error': 'Agent not found'}, status=404)
        
        # Unset all defaults, then set this one
        q = AIAgentConfig.objects.all()
        if org_id:
            q = q.filter(organization_id=org_id)
        elif admin_id:
            q = q.filter(admin_id=admin_id)
        q.update(is_default=False)
        
        agent.is_default = True
        agent.save()
        
        return JsonResponse({'success': True})

    @staticmethod
    @csrf_exempt
    def delete_agent(request, agent_id):
        """Delete an AI agent."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        agent = AIAgentConfig.objects.filter(id=agent_id).first()
        if not agent:
            return JsonResponse({'error': 'Agent not found'}, status=404)
        
        if agent.is_default:
            return JsonResponse({'error': 'Cannot delete the default agent'}, status=400)
        
        agent.delete()
        return JsonResponse({'success': True})
    
    @staticmethod    
    def extract_pdf_text(pdf_path):
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    
    @csrf_exempt
    def set_chatgpt_mode(request):
        if request.method == "POST":
            mode = request.POST.get('mode')  # 'prompt' or 'ai_agent'
            if mode not in ['prompt', 'ai_agent']:
                return JsonResponse({"error": "Invalid mode"}, status=400)
            
            # Get admin or org from session
            admin_id = request.session.get('admin_id')
            org_id = request.session.get('organization_id')
            
            if org_id:
                # Organization-based: update org's chatgpt_mode
                from ..models import Organization
                org = Organization.objects.filter(id=org_id).first()
                if org:
                    org.chatgpt_mode = mode
                    org.save()
                    return JsonResponse({"success": True, "mode": mode})
            elif admin_id:
                # Admin-based: update admin's chatgpt_mode
                Admin.objects.filter(id=admin_id).update(chatgpt_mode=mode)
                return JsonResponse({"success": True, "mode": mode})
            
            # Fallback: if admin_id in POST (legacy support)
            admin_id_post = request.POST.get('admin_id')
            if admin_id_post:
                Admin.objects.filter(id=admin_id_post).update(chatgpt_mode=mode)
                return JsonResponse({"success": True, "mode": mode})
            
            return JsonResponse({"error": "Not authenticated"}, status=401)

    # @csrf_exempt
    # def ai_agent_upload(request):
    #     if request.method == 'POST':
    #         form = AIAgentConfigForm(request.POST, request.FILES)
    #         if form.is_valid():
    #             form.save()
    #             return redirect('ai_agent_upload')
    #     else:
    #         form = AIAgentConfigForm()

    #     uploaded_pdfs = AIAgentConfig.objects.all().order_by('-uploaded_at')
    #     return render(request, 'set/ai_agent.html', {
    #         'form': form,
    #         'uploaded_pdfs': uploaded_pdfs,
    #     })    

# old one 
# class Integrationcontroller:
#     def dissconnect(request):
#        Admin.objects.update(pinecone_token='')
#        return JsonResponse({
#            'msg':'disconnected pinecone'
#        })
#     # @require_POST
#     @csrf_exempt
#     def connect(request):
#             try:
#                 data = json.loads(request.body.decode("utf-8"))
#                 token = data.get("api_key") or ""
#                 if not token:
#                     return JsonResponse({"msg": "API key required"}, status=400)
#                 Admin.objects.update(pinecone_token=token)
#                 return JsonResponse({
#                     "msg": "connected",
#                     "token": token
#                 })
#             except Exception as e:
#                 return JsonResponse({"msg": str(e)}, status=500)



# new one

# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# import json
# from newapp.models import Admin

# class Integrationcontroller:

#     @csrf_exempt
#     def disconnect_pinecone(request):
#         Admin.objects.update(pinecone_token='')
#         return JsonResponse({'msg': 'Pinecone disconnected'})

#     @csrf_exempt
#     def disconnect_chatgpt(request):
#         Admin.objects.update(openai_api_key='')
#         return JsonResponse({'msg': 'ChatGPT disconnected'})

#     @csrf_exempt
#     def connect_pinecone(request):
#         try:
#             data = json.loads(request.body.decode("utf-8"))
#             token = data.get("api_key") or ""
#             if not token:
#                 return JsonResponse({"msg": "Pinecone API key required"}, status=400)

#             # Disconnect ChatGPT first
#             Admin.objects.update(openai_api_key='')

#             # Connect Pinecone token
#             Admin.objects.update(pinecone_token=token)
#             return JsonResponse({"msg": "Pinecone connected", "token": token})
#         except Exception as e:
#             return JsonResponse({"msg": str(e)}, status=500)

#     @csrf_exempt
#     def connect_chatgpt(request):
#         try:
#             data = json.loads(request.body.decode("utf-8"))
#             api_key = data.get("api_key") or ""
#             if not api_key:
#                 return JsonResponse({"msg": "ChatGPT API key required"}, status=400)

#             # Disconnect Pinecone first
#             Admin.objects.update(pinecone_token='')

#             # Connect ChatGPT API key
#             Admin.objects.update(openai_api_key=api_key)
#             return JsonResponse({"msg": "ChatGPT connected", "api_key": api_key})
#         except Exception as e:
#             return JsonResponse({"msg": str(e)}, status=500)

            