
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_syntax():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to find: {{ messages.last.id (spaces) | (spaces) default (spaces) : (spaces) 0 }}
    # We want to normalize it to {{ messages.last.id|default:0 }}
    
    # Regex explanation:
    # \{\{\s*messages\.last\.id\s*  -> matches {{ messages.last.id (with optional trailing space)
    # \|\s*default\s*:\s*0\s*       -> matches | default : 0 (with optional spaces key chars)
    # \}\}                          -> matches }}
    
    pattern = r'\{\{\s*messages\.last\.id\s*\|\s*default\s*:\s*0\s*\}\}'
    replacement = '{{ messages.last.id|default:0 }}'
    
    new_content, count = re.subn(pattern, replacement, content)
    
    if count > 0:
        print(f"Found and fixed {count} occurrence(s) of the syntax error.")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    else:
        print("No matching syntax error found. Printing context around likely line 418:")
        lines = content.splitlines()
        if len(lines) > 415:
            for i in range(415, min(425, len(lines))):
                print(f"{i+1}: {lines[i]}")

if __name__ == "__main__":
    fix_syntax()
