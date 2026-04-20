# Script to completely fix urls.py imports
# Read the file
with open('mynewsite/urls.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the duplicate section and fix it
# The file has a broken structure around the webchat imports

# Let's find where the urlpatterns starts
urlpatterns_match = re.search(r'urlpatterns = \[', content)
if urlpatterns_match:
    # Get everything before urlpatterns
    imports_section = content[:urlpatterns_match.start()]
    
    # Find the last closing parenthesis before urlpatterns
    # The problem is we have duplicate/broken imports
    
    # Let's identify the broken part and remove it
    # Look for the pattern where we have duplicate imports
    
    # Clean approach: keep only what's before urlpatterns and fix imports
    import re
    
    # Pattern to match the broken duplicate imports
    broken_pattern = r"from newapp\.controllers\.webchat_admin import \(\n    dashboard as webchat_dashboard,\n    session_detail as webchat_session_detail,\n    end_session_api,\n    delete_session_api,\n    analytics as webchat_analytics,\n    widgets as webchat_widgets,\n    create_widget,\n    update_widget,\n    delete_widget,\n    get_widget_embed_code,\n\)\nfrom newapp\.controllers\.webchat_admin import \(\n    dashboard as webchat_dashboard,\n    session_detail as webchat_session_detail,\n    end_session_api,\n    delete_session_api,\n    analytics as webchat_analytics,\n    widgets as webchat_widgets,\n    create_widget,\n    update_widget,\n    delete_widget,\n    get_widget_embed_code,"
    
    # Remove the duplicate
    content = re.sub(broken_pattern, 'from newapp.controllers.webchat_admin import (\n    dashboard as webchat_dashboard,\n    session_detail as webchat_session_detail,\n    end_session_api,\n    delete_session_api,\n    analytics as webchat_analytics,\n    widgets as webchat_widgets,\n    create_widget,\n    update_widget,\n    delete_widget,\n    get_widget_embed_code,\n)\n', content)

# Write back
with open('mynewsite/urls.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed duplicate imports in urls.py")
