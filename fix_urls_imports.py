# Script to fix the malformed imports in urls.py
import re

# Read the file
with open('mynewsite/urls.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the malformed imports - the webchat API imports lost their indentation
old_pattern = r"""from newapp\.controllers\.webchat_admin import \(
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
\)
api_webchat_start,
api_webchat_message,
api_webchat_messages,
api_webchat_end,
api_webchat_feedback,
api_webchat_language
\)"""

new_content = """from newapp.controllers.webchat_admin import (
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
from newapp.controllers.webchat import (
    api_webchat_start,
    api_webchat_message,
    api_webchat_messages,
    api_webchat_end,
    api_webchat_feedback,
    api_webchat_language
)"""

content = content.replace(')\n    api_webchat_start,', new_content + '\n')

# Write back
with open('mynewsite/urls.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed malformed imports in urls.py")
