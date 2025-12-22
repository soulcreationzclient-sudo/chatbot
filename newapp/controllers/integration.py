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
        if request.method == 'POST':
            form = AIAgentConfigForm(request.POST, request.FILES)
            if form.is_valid():
                ai_agent = form.save()
                pdf_path = ai_agent.pdf_file.path
                pdf_text = self.extract_pdf_text(pdf_path)
                ai_agent.pdf_text = pdf_text
                ai_agent.save()
                # Prepare pre-filled form with last instruction
                form = AIAgentConfigForm(initial={'instruction': ai_agent.instruction})
            else:
                form = AIAgentConfigForm()
        else:
            # On GET, fetch the last uploaded instruction if it exists
            last_pdf = AIAgentConfig.objects.order_by('-uploaded_at').first()
            last_instruction = last_pdf.instruction if last_pdf else ""
            form = AIAgentConfigForm(initial={'instruction': last_instruction})

        uploaded_pdfs = AIAgentConfig.objects.all().order_by('-uploaded_at')
        return render(request, 'set/ai_agent.html', {
            'form': form,
            'uploaded_pdfs': uploaded_pdfs,
        })
    
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
            admin_id = request.POST.get('admin_id')
            mode = request.POST.get('mode')  # 'prompt' or 'ai_agent'
            if mode not in ['prompt', 'ai_agent']:
                return JsonResponse({"error": "Invalid mode"}, status=400)
            Admin.objects.filter(id=admin_id).update(chatgpt_mode=mode)
            return JsonResponse({"success": True, "mode": mode})
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

            