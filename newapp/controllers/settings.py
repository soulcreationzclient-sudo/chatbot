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
    
    # def integration(request):
    #     pinecone_connected=None
    #     admin_id=request.session.get('admin_id')
    #     if admin_id:
    #         admin=Admin.objects.filter(id=admin_id).only('pinecone_token').first()
    #         pinecone_token=(admin.pinecone_token)
    #         # return HttpResponse(pinecone_token)
    #         if(pinecone_token!=''):
    #             pinecone_connected=True
    #     # return HttpResponse(pinecone_connected)
    #     return render(request,'set/integration.html',{'pinecone_connected':pinecone_connected})
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
        