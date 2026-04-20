#!/usr/bin/env python
"""Search for sidebar.html references in webchat templates."""

import os
import glob

webchat_dir = "templates/webchat"
html_files = glob.glob(os.path.join(webchat_dir, "*.html"))

print("=" * 60)
print("Searching for 'layouts/sidebar' references in webchat templates")
print("=" * 60)
print()

for file_path in html_files:
    file_name = os.path.basename(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'layouts/sidebar' in content:
        print(f"Found in: {file_name}")
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'sidebar' in line.lower():
                print(f"  Line {i+1}: {line.strip()}")
        print()
