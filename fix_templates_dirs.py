#!/usr/bin/env python
import re

# Read settings.py
with open('mynewsite/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the DIRS line
old_text = """TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'newapp' / 'templates'],
        'APP_DIRS': True,"""

new_text = """TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'newapp' / 'templates',
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,"""

if old_text in content:
    content = content.replace(old_text, new_text)
    with open('mynewsite/settings.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ Successfully updated TEMPLATES DIRS in settings.py')
else:
    print('❌ Could not find the exact text to replace')
    print('Searching for TEMPLATES configuration...')
    if 'TEMPLATES' in content:
        print('TEMPLATES found in file')
        # Show the relevant section
        match = re.search(r"TEMPLATES\s*=\s*\[.*?\]", content, re.DOTALL)
        if match:
            print('Found TEMPLATES config (truncated):')
            print(match.group()[:500])