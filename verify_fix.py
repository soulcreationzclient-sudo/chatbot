#!/usr/bin/env python

# Verify TEMPLATES configuration
with open('mynewsite/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'BASE_DIR / \'templates\'' in content:
    print('✅ TEMPLATES DIRS configuration updated correctly!')
    print('')
    print('Current DIRS configuration:')
    # Find and display the DIRS section
    import re
    match = re.search(r"'DIRS':\s*\[(.*?)\]", content, re.DOTALL)
    if match:
        dirs_content = match.group(1)
        print(dirs_content.strip())
else:
    print('❌ TEMPLATES DIRS not updated')

# Verify sidebar exists
import os
sidebar_path = 'newapp/templates/layouts/sidebar.html'
if os.path.exists(sidebar_path):
    print(f'✅ Sidebar template found: {sidebar_path}')
else:
    print(f'❌ Sidebar template NOT found: {sidebar_path}')