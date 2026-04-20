# Script to add webchat URLs to urls.py
import re

# Read the file
with open('mynewsite/urls.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The pattern to find (ending of urlpatterns)
old_pattern = r"    path\('api/inbox/user_tags/', Inboxcontroller\.get_user_tags, name='inbox_get_user_tags'\),\s*\n\]"

# The new lines to add
new_lines = """    path('api/inbox/user_tags/', Inboxcontroller.get_user_tags, name='inbox_get_user_tags'),
    
    # ==================== WEBCHAT API ====================
    path('api/webchat/start/', api_webchat_start, name='webchat_start'),
    path('api/webchat/message/', api_webchat_message, name='webchat_message'),
    path('api/webchat/messages/<str:session_id>/', api_webchat_messages, name='webchat_messages'),
    path('api/webchat/end/', api_webchat_end, name='webchat_end'),
    path('api/webchat/feedback/', api_webchat_feedback, name='webchat_feedback'),
    path('api/webchat/language/', api_webchat_language, name='webchat_language'),
    
]"""

# Replace
new_content = re.sub(old_pattern, new_lines, content)

# Write back
with open('mynewsite/urls.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully added webchat URLs to urls.py")
