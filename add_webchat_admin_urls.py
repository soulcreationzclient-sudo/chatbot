# Script to add webchat admin URLs to urls.py
import re

# Read the file
with open('mynewsite/urls.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import for webchat_admin
import_pattern = r"from newapp\.controllers\.webchat import \("
import_replacement = """from newapp.controllers.webchat import (
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
)"""

content = re.sub(import_pattern, import_replacement, content)

# Add webchat admin URLs before the closing bracket
old_pattern = r"    path\('api/webchat/language/', api_webchat_language, name='webchat_language'\),\s*\n\]"

new_lines = """    path('api/webchat/language/', api_webchat_language, name='webchat_language'),
    
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
    
]"""

content = re.sub(old_pattern, new_lines, content)

# Write back
with open('mynewsite/urls.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully added webchat admin URLs to urls.py")
