from django.contrib import admin

from django.urls import path
from django.views.generic import RedirectView
from newapp.views import send_whatsapp_message
from newapp import views
from newapp.controllers.login import Logincontroller
from newapp.controllers.inbox import Inboxcontroller

from newapp.controllers.contact import Contactcontroller
from newapp.controllers.settings import Settingcontroller
from newapp.controllers.whatsapp import whatsappcontroller
from newapp.controllers.integration import Integrationcontroller
from newapp.views import whatsapp_templates
from newapp.controllers.integration import Integrationcontroller
integration_controller = Integrationcontroller()
from django.conf import settings
from django.conf.urls.static import static
from newapp.views import delete_pdf
from newapp import calendly_views
from newapp import calendly_integration_views

# Multi-tenant admin imports
from newapp.controllers import auth_views, superadmin_views, client_views



urlpatterns = [
    # ==================== SUPER ADMIN PORTAL ====================
    path('super-login/', RedirectView.as_view(url='/login/', permanent=False)), # CONVENIENCE REDIRECT
    path('super-admin/', superadmin_views.super_admin_dashboard, name='super_admin_dashboard'),
    path('super-admin/login/', RedirectView.as_view(url='/login/', permanent=False), name='super_admin_login'),  # Redirects to common login
    path('super-admin/logout/', auth_views.super_admin_logout, name='super_admin_logout'),
    path('super-admin/organizations/', superadmin_views.organization_list, name='organization_list'),
    path('super-admin/organizations/create/', superadmin_views.organization_create, name='organization_create'),
    path('super-admin/organizations/<int:pk>/', superadmin_views.organization_detail, name='organization_detail'),
    path('super-admin/organizations/<int:pk>/update/', superadmin_views.organization_update, name='organization_update'),
    path('super-admin/organizations/<int:pk>/toggle/', superadmin_views.organization_toggle_status, name='organization_toggle_status'),
    path('super-admin/organizations/<int:org_pk>/add-user/', superadmin_views.add_user_to_organization, name='add_user_to_organization'),
    path('super-admin/users/', superadmin_views.super_admin_user_list, name='super_admin_user_list'),
    path('super-admin/users/create/', superadmin_views.super_admin_user_create, name='super_admin_user_create'),
    path('super-admin/users/<int:pk>/toggle/', superadmin_views.super_admin_user_toggle_status, name='super_admin_user_toggle_status'),
    path('super-admin/users/<int:pk>/update/', superadmin_views.super_admin_user_update, name='super_admin_user_update'),
    
    # ==================== CLIENT PORTAL AUTH ====================
    path('login/', auth_views.client_login, name='login'),
    path('client-logout/', auth_views.client_logout, name='client_logout'),
    
    # ==================== CLIENT SETTINGS ====================
    path('client/settings/', client_views.client_settings, name='client_settings'),
    path('client/settings/update/', client_views.client_settings_update, name='client_settings_update'),
    
    # ==================== LEGACY ROUTES (backward compatibility) ====================
    # logout
    path('',Logincontroller.enter,name=''),
    path('logout/',Logincontroller.logout,name='logout'),
    
    path('login_view/',Logincontroller.login_view, name='login_view'),
    path('login_post/',Logincontroller.login_post,name='login_post'),
    
    path('dashboard/', views.dashboard_view, name='dashboard'),
    # inbox
    path('inbox/dashboard', Inboxcontroller.dashboard, name='inbox_dashboard'),
    path('api/inbox/new_messages', Inboxcontroller.get_new_messages, name='get_new_messages_api'),
    
    # contact
    path('contact/dashboard',Contactcontroller.dashboard,name='contact_dashboard'),
    path('contact/add',Contactcontroller.add_user,name='add_user'),
    path('contact/add_admin_user',Contactcontroller.add_admin_user,name='add_admin_user'),
    path('contact/tag/', views.tag_view, name='add_tag'),
    path('contact/tags/delete/<int:tag_id>/', views.delete_tag, name='delete_tag'),
    path('api/users/', views.user_search_api, name='user_search_api'),
    path('contact/edit/<int:id>/', Contactcontroller.edit_user, name='edit_user'),
    path('contact/delete/<int:id>/', Contactcontroller.delete_user, name='delete_user'),
    path('api/user/tag/add/', Contactcontroller.add_user_tag, name='add_user_tag'),
    path('api/user/tag/remove/', Contactcontroller.remove_user_tag, name='remove_user_tag'),
    
    # setting
    path('settings/',Settingcontroller.dashboard , name='settings'),
   # channels
    path('setting/channels', Settingcontroller.channels_view, name='channels_view'),
    # integration
    path('setting/integration',Settingcontroller.integration,name='integration_view'),
    path('setting/external_apis',Settingcontroller.external_apis,name='external_apis_view'),
    # External APIs CRUD
    path('api/external-api/create/', Settingcontroller.external_api_create, name='external_api_create'),
    path('api/external-api/<int:api_id>/', Settingcontroller.external_api_detail, name='external_api_detail'),
    path('api/external-api/<int:api_id>/update/', Settingcontroller.external_api_update, name='external_api_update'),
    path('api/external-api/<int:api_id>/delete/', Settingcontroller.external_api_delete, name='external_api_delete'),
    path('api/external-api/<int:api_id>/test/', Settingcontroller.external_api_test, name='external_api_test'),
    # Image Assets CRUD
    path('setting/image_assets', Settingcontroller.image_assets, name='image_assets_view'),
    path('api/image-asset/create/', Settingcontroller.image_asset_create, name='image_asset_create'),
    path('api/image-asset/<int:asset_id>/update/', Settingcontroller.image_asset_update, name='image_asset_update'),
    path('api/image-asset/<int:asset_id>/delete/', Settingcontroller.image_asset_delete, name='image_asset_delete'),
    # Follow-up Settings
    path('setting/followup', Settingcontroller.followup_settings, name='followup_settings_view'),
    path('api/followup/create/', Settingcontroller.followup_create, name='followup_create'),
    path('api/followup/<int:followup_id>/update/', Settingcontroller.followup_update, name='followup_update'),
    path('api/followup/<int:followup_id>/delete/', Settingcontroller.followup_delete, name='followup_delete'),
    path('api/followup/toggle/', Settingcontroller.followup_toggle, name='followup_toggle'),
    # Tag Management
    path('setting/tags', Settingcontroller.tags_view, name='tags_view'),
    path('api/tag/create/', Settingcontroller.tag_create, name='settings_tag_create'),
    path('api/tag/<int:tag_id>/update/', Settingcontroller.tag_update, name='settings_tag_update'),
    path('api/tag/<int:tag_id>/delete/', Settingcontroller.tag_delete, name='settings_tag_delete'),
    path('whatsapp_connect',whatsappcontroller.connect,name='whatsapp_connect'),
    #path('admin/connect_google_calendar/', Integrationcontroller.connect_google_calendar, name='connect_google_calendar'),
    #path('admin/disconnect_google_calendar/', Integrationcontroller.disconnect_google_calendar, name='disconnect_google_calendar'),

    
    
    # whatsapp
    path('get_message/', whatsappcontroller.get_message, name='get_message'),
    path('get_message', whatsappcontroller.get_message, name='get_message_no_slash'),  # For Meta webhook
    path('send_whatsapp_message/', whatsappcontroller.send_whatsapp_message,name='send_whatsapp_message'),
    path('disconnect/',whatsappcontroller.disconnect,name='disconnect'), 
    path('send_trigger/',whatsappcontroller.send_trigger,name='send_trigger'),
    path('appointment_date/',whatsappcontroller.appointment_date,name='appointment_date'),

    # Google Calendar event creation API endpoint
    path('create-event/', views.create_event_api, name='create_event_api'),
    
    
    
    # pinecone
    path('disconnect_pinecone/',Integrationcontroller.disconnect,name='disconnect'),
    path('connect_pinecone_token/',Integrationcontroller.connect,name='pinecone_connect'),
    
    
    path('flows/', views.flows_view, name='flows'),
    path('admin/', admin.site.urls),
   
    path('connect_whatsapp/', views.connect_whatsapp, name='connect_whatsapp'),
    path('voice_bot/', views.voice_bot, name='voice_bot'),
    path('send_voice_bot/', views.send_voice_bot, name='send_voice_bot'),
    
    path('show_people/',views.show_people,name='show_people'),
    path('chatbox/', views.show_chatbox, name='chatbox'),
    path('broadcast_msg/',views.broadcast_msg,name='broadcast_msg'),
    path('send_broadcast/', views.send_broadcast, name='send_broadcast'),
    path('import_contacts/', views.import_contacts, name='import_contacts'),
    path('api/whatsapp_templates/', whatsapp_templates, name='whatsapp_templates'),
    


    #chatgpt
    path('connect_openai_key/', views.connect_openai_key, name='connect_openai_key'),
    path('disconnect_openai_key/', views.disconnect_openai_key, name='disconnect_openai_key'),
    path('set_chatgpt_mode/', Integrationcontroller.set_chatgpt_mode, name='set_chatgpt_mode'),
    path('chatgpt_prompt/', views.chatgpt_prompt_page, name='chatgpt_prompt_page'),
    path('chatgpt/respond/', views.chatgpt_respond, name='chatgpt_respond'),
    path('inbox/send/', views.send_inbox_message, name='send_inbox_message'),
    path('ai_agent/upload/', integration_controller.ai_agent_upload, name='ai_agent_upload'),
    path('ai_agent/delete/<int:pk>/', delete_pdf, name='delete_pdf'),
    path('whatsapp/chatgpt_webhook/', views.get_message_chatgpt, name='chatgpt_webhook'),
 


    # path('new/',views.new,name='new')  # ✅ This line is correct
    
    # ==================== CALENDLY API ENDPOINTS ====================
    path('api/calendly/user/', calendly_views.calendly_user_info, name='calendly_user_info'),
    path('api/calendly/event-types/', calendly_views.calendly_event_types, name='calendly_event_types'),
    path('api/calendly/available-times/', calendly_views.calendly_available_times, name='calendly_available_times'),
    path('api/calendly/book/', calendly_views.calendly_create_booking, name='calendly_create_booking'),
    path('api/calendly/booking-link/', calendly_views.calendly_get_booking_link, name='calendly_get_booking_link'),
    path('api/calendly/scheduled-events/', calendly_views.calendly_scheduled_events, name='calendly_scheduled_events'),
    path('api/calendly/cancel/', calendly_views.calendly_cancel_event, name='calendly_cancel_event'),
    path('api/calendly/chatbot/', calendly_views.calendly_chatbot_handler, name='calendly_chatbot_handler'),
    path('api/calendly/webhook/', calendly_views.calendly_webhook, name='calendly_webhook'),
    path('api/calendly/webhook', calendly_views.calendly_webhook, name='calendly_webhook_no_slash'),
    
    # ==================== CALENDLY INTEGRATION UI ====================
    path('connect_calendly/', calendly_integration_views.connect_calendly, name='connect_calendly'),
    path('disconnect_calendly/', calendly_integration_views.disconnect_calendly, name='disconnect_calendly'),
    path('update_followup_settings/', calendly_integration_views.update_followup_settings, name='update_followup_settings'),
    
]

if settings.DEBUG:  # Add this block at the bottom of the file
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)