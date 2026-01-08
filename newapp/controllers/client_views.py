"""
Client views for organization settings and API configuration.
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from newapp.decorators import client_admin_required
from newapp.models import Organization


@client_admin_required
def client_settings(request):
    """Settings page for Client Admin to configure their organization's API keys."""
    org = request.org_user.organization
    
    if not org:
        messages.error(request, 'No organization associated with your account.')
        return redirect('dashboard')
    
    context = {
        'organization': org,
    }
    return render(request, 'client/settings.html', context)


@client_admin_required
@csrf_protect
@require_http_methods(["POST"])
def client_settings_update(request):
    """Update organization API settings."""
    org = request.org_user.organization
    
    if not org:
        messages.error(request, 'No organization associated with your account.')
        return redirect('dashboard')
    
    # Update WhatsApp settings
    org.display_phone_no = request.POST.get('display_phone_no', org.display_phone_no)
    org.whatsapp_phone_id = request.POST.get('whatsapp_phone_id', org.whatsapp_phone_id)
    
    whatsapp_token = request.POST.get('whatsapp_token', '').strip()
    if whatsapp_token:
        org.whatsapp_token = whatsapp_token
    
    # Update OpenAI settings
    openai_api_key = request.POST.get('openai_api_key', '').strip()
    if openai_api_key:
        org.openai_api_key = openai_api_key
    
    org.assistant_name = request.POST.get('assistant_name', org.assistant_name)
    org.chatgpt_mode = request.POST.get('chatgpt_mode', org.chatgpt_mode)
    
    # Update Pinecone settings
    pinecone_token = request.POST.get('pinecone_token', '').strip()
    if pinecone_token:
        org.pinecone_token = pinecone_token
    
    # Update Calendly settings
    calendly_token = request.POST.get('calendly_token', '').strip()
    if calendly_token:
        org.calendly_token = calendly_token
    org.calendly_scheduling_url = request.POST.get('calendly_scheduling_url', org.calendly_scheduling_url)
    
    org.save()
    
    messages.success(request, 'Settings updated successfully!')
    return redirect('client_settings')
