#!/usr/bin/env python
"""Add webchat link to sidebar navigation."""

import os

# Read the file
file_path = "newapp/templates/layouts/sidebar.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old and new content
old_content = """    Settings
  </a>

</div>"""

new_content = """    Settings
  </a>

  {% url 'webchat_dashboard' as webchat_url %}
  <a href="{{ webchat_url }}" class="nav-item {% if request.path == webchat_url %}active{% endif %}">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
    WebChat
  </a>

</div>"""

# Check if the old content exists
if old_content in content:
    new_file_content = content.replace(old_content, new_content)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_file_content)
    print(f"✅ Successfully added webchat link to {file_path}")
else:
    print("❌ Could not find the expected content to replace")
    # Print the last 200 characters for debugging
    print("\nLast 200 characters of file:")
    print(repr(content[-200:]))
