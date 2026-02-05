#!/usr/bin/env python
"""Add link to webchat button in dashboard."""

import os

# Read the file
file_path = "newapp/templates/dashboard.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old and new content for webchat card (with exact indentation - 12 spaces)
old_content = """            <div>Webchat</div>
            <button>Test now</button>
        </div>
        <div class="channel-card">
            <div style="font-size: 24px;">+</div>"""

new_content = """            <div>Webchat</div>
            <button onclick="window.location.href='/webchat/dashboard/'">Open Dashboard</button>
        </div>
        <div class="channel-card">
            <div style="font-size: 24px;">+</div>"""

# Check if the old content exists
if old_content in content:
    new_file_content = content.replace(old_content, new_content)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_file_content)
    print(f"✅ Successfully added webchat link to {file_path}")
else:
    print("❌ Could not find the expected content to replace")
    # Print the relevant section for debugging
    print("\nSearching for webchat card...")
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'Webchat' in line:
            print(f"Line {i+1}: {repr(line)}")
