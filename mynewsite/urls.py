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
from django.conf import settings
from django.conf.urls.static import static
from newapp.views import delete_pdf
from newapp import calendly_views
from newapp import calendly_integration_views

# Multi-tenant admin imports
from newapp.controllers import auth_views, superadmin_views, client_views
from newapp.controllers import broadcast as broadcast_views
from newapp.controllers import pipeline as pipeline_views

# Controller instances
integration_controller = Integrationcontroller()

# Webchat imports
from newapp.controllers.webchat import (
    api_webchat_start,
    api_webchat_message,
    api_webchat_messages,
    api_webchat_end,
    api_webchat_feedback,
    api_webchat_language
)
from newapp.controllers.webchat_admin import (
    dashboard as webchat_dashboard,
    session_detail as webchat_session_detail,
    end_session_api,
    delete_session_api,
    analytics as webchat_analytics,
    widgets as webchat_widgets,
    create_widget,
    update_widget,
    delete_widget,
    get_widget_embed_code,
)

# Test Chat imports
from newapp.controllers.test_chat import (
    test_chat,
    test_chat_send,
    test_chat_quick,
)

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
    path('api/inbox/delete_user/<int:user_id>/', Inboxcontroller.delete_user, name='inbox_delete_user'),
    path('api/inbox/toggle_bot/<int:user_id>/', Inboxcontroller.toggle_bot, name='inbox_toggle_bot'),
    path('api/inbox/upload_media/', Inboxcontroller.upload_media, name='inbox_upload_media'),
    path('api/inbox/list_assets/', Inboxcontroller.list_assets, name='inbox_list_assets'),
    
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
    path('api/contact/search/', Contactcontroller.contact_search_api, name='contact_search_api'),
    
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

    # Custom Field Management
    path('setting/custom_fields', Settingcontroller.custom_fields_view, name='custom_fields_view'),
    path('api/custom-field/create/', Settingcontroller.custom_field_create, name='custom_field_create'),
    path('api/custom-field/<int:field_id>/update/', Settingcontroller.custom_field_update, name='custom_field_update'),
    path('api/custom-field/<int:field_id>/delete/', Settingcontroller.custom_field_delete, name='custom_field_delete'),
    path('api/custom-field/list/', Settingcontroller.custom_field_list, name='custom_field_list'),
    path('whatsapp_connect',whatsappcontroller.connect,name='whatsapp_connect'),
    #path('admin/connect_google_calendar/', Integrationcontroller.connect_google_calendar, name='connect_google_calendar'),
    #path('admin/disconnect_google_calendar/', Integrationcontroller.disconnect_google_calendar, name='disconnect_google_calendar'),

    
    
    # whatsapp
    path('webhook/', whatsappcontroller.get_message, name='webhook'),
    path('webhook', whatsappcontroller.get_message, name='webhook_no_slash'),
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
    path('set_gpt_model/', views.set_gpt_model, name='set_gpt_model'),
    path('set_chatgpt_mode/', Integrationcontroller.set_chatgpt_mode, name='set_chatgpt_mode'),
    path('chatgpt_prompt/', views.chatgpt_prompt_page, name='chatgpt_prompt_page'),
    path('chatgpt/respond/', views.chatgpt_respond, name='chatgpt_respond'),
    path('inbox/send/', views.send_inbox_message, name='send_inbox_message'),
    path('ai_agent/upload/', integration_controller.ai_agent_upload, name='ai_agent_upload'),
    path('api/ai_agent/set_default/', Integrationcontroller.set_default_agent, name='ai_agent_set_default'),
    path('api/ai_agent/delete/<int:agent_id>/', Integrationcontroller.delete_agent, name='ai_agent_delete'),
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
    
    # Calendly Booking Links (Tag-based)
    path('setting/calendly_links', Settingcontroller.calendly_links, name='calendly_links_view'),
    path('api/calendly-link/create/', Settingcontroller.calendly_link_create, name='calendly_link_create'),
    path('api/calendly-link/<int:link_id>/update/', Settingcontroller.calendly_link_update, name='calendly_link_update'),
    path('api/calendly-link/<int:link_id>/delete/', Settingcontroller.calendly_link_delete, name='calendly_link_delete'),
    
    # ==================== BROADCAST SYSTEM ====================
    path('api/broadcast/templates/sync/', broadcast_views.BroadcastController.sync_templates, name='broadcast_sync_templates'),
    path('api/broadcast/templates/', broadcast_views.BroadcastController.list_templates, name='broadcast_list_templates'),
    path('api/broadcast/create/', broadcast_views.BroadcastController.create_broadcast, name='broadcast_create'),
    path('api/broadcast/<int:job_id>/status/', broadcast_views.BroadcastController.get_broadcast_status, name='broadcast_status'),
    path('api/broadcast/', broadcast_views.BroadcastController.list_broadcasts, name='broadcast_list'),
    path('broadcast/', broadcast_views.BroadcastController.broadcast_dashboard, name='broadcast_dashboard'),
    
    # ==================== INBOX RESTORE (Soft-delete support) ====================
    path('api/inbox/restore_user/<int:user_id>/', Inboxcontroller.restore_user, name='inbox_restore_user'),
    # Inbox Custom Fields API
    path('api/inbox/custom_fields/', Inboxcontroller.get_user_custom_fields, name='inbox_get_custom_fields'),
    path('api/inbox/custom_field/update/', Inboxcontroller.update_user_custom_field, name='inbox_update_custom_field'),
    path('api/inbox/custom_field/delete/', Inboxcontroller.delete_user_custom_field, name='inbox_delete_custom_field'),
    # Inbox User Logs API
    path('api/inbox/user_logs/', Inboxcontroller.get_user_logs, name='inbox_get_user_logs'),
    path('api/inbox/user_log/create/', Inboxcontroller.create_user_log, name='inbox_create_user_log'),
    # Inbox User Tags API
    path('api/inbox/user_tags/', Inboxcontroller.get_user_tags, name='inbox_get_user_tags'),
    path('api/inbox/export/<int:user_id>/csv/', Inboxcontroller.export_chat_csv, name='inbox_export_csv'),
    
    # ==================== WEBCHAT API ====================
    path('api/webchat/start/', api_webchat_start, name='webchat_start'),
    path('api/webchat/message/', api_webchat_message, name='webchat_message'),
    path('api/webchat/messages/<str:session_id>/', api_webchat_messages, name='webchat_messages'),
    path('api/webchat/end/', api_webchat_end, name='webchat_end'),
    path('api/webchat/feedback/', api_webchat_feedback, name='webchat_feedback'),
    path('api/webchat/language/', api_webchat_language, name='webchat_language'),
    
    # ==================== WEBCHAT ADMIN ====================
    path('webchat/dashboard/', webchat_dashboard, name='webchat_dashboard'),
    path('webchat/session/<str:session_id>/', webchat_session_detail, name='webchat_session_detail'),
    path('api/webchat/session/end/', end_session_api, name='webchat_end_session'),
    path('api/webchat/session/delete/', delete_session_api, name='webchat_delete_session'),
    path('webchat/analytics/', webchat_analytics, name='webchat_analytics'),
    path('webchat/widgets/', webchat_widgets, name='webchat_widgets'),
    path('api/webchat/widget/create/', create_widget, name='webchat_create_widget'),
    path('api/webchat/widget/<int:widget_id>/update/', update_widget, name='webchat_update_widget'),
    path('api/webchat/widget/<int:widget_id>/delete/', delete_widget, name='webchat_delete_widget'),
    path('api/webchat/widget/<int:widget_id>/embed/', get_widget_embed_code, name='webchat_embed_code'),
    
    # ==================== TEST CHAT (Prompt Testing) ====================
    path('test/chat/', test_chat, name='test_chat'),
    path('api/test/chat/send/', test_chat_send, name='test_chat_send'),
    path('api/test/chat/quick/', test_chat_quick, name='test_chat_quick'),
    
    # ==================== PIPELINE CRM ====================
    path('pipeline/', pipeline_views.pipeline_list, name='pipeline_list'),
    path('pipeline/<int:pipeline_id>/board/', pipeline_views.pipeline_board, name='pipeline_board'),
    path('api/pipeline/create/', pipeline_views.pipeline_create, name='pipeline_create'),
    path('api/pipeline/delete/<int:pipeline_id>/', pipeline_views.pipeline_delete, name='pipeline_delete'),
    path('api/pipeline/<int:pipeline_id>/stage/create/', pipeline_views.stage_create, name='pipeline_stage_create'),
    path('api/pipeline/stage/delete/<int:stage_id>/', pipeline_views.stage_delete, name='pipeline_stage_delete'),
    path('api/pipeline/opportunity/create/', pipeline_views.opportunity_create, name='pipeline_opp_create'),
    path('api/pipeline/opportunity/<int:opp_id>/move/', pipeline_views.opportunity_move, name='pipeline_opp_move'),
    path('api/pipeline/opportunity/<int:opp_id>/update/', pipeline_views.opportunity_update, name='pipeline_opp_update'),
    path('api/pipeline/opportunity/<int:opp_id>/delete/', pipeline_views.opportunity_delete, name='pipeline_opp_delete'),
    path('api/pipeline/opportunity/<int:opp_id>/comment/', pipeline_views.opportunity_comment, name='pipeline_opp_comment'),
    path('api/pipeline/stage/<int:stage_id>/rename/', pipeline_views.stage_rename, name='pipeline_stage_rename'),
    path('api/pipeline/automation/create/', pipeline_views.automation_create, name='pipeline_auto_create'),
    path('api/pipeline/automation/delete/<int:auto_id>/', pipeline_views.automation_delete, name='pipeline_auto_delete'),
    
]

if settings.DEBUG:  # Add this block at the bottom of the file
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
