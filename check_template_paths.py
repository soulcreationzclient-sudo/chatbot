#!/usr/bin/env python
import os

# Check all webchat templates for incorrect paths
templates_dir = 'C:/Users/Meet/.gemini/chatbot/19 08/chatbot/templates/webchat'

for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'newapp/templates/layouts' in content:
            print(f'❌ WRONG PATH in {filename}:')
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'newapp/templates/layouts' in line:
                    print(f'   Line {i+1}: {line.strip()}')
        else:
            print(f'✅ OK: {filename}')