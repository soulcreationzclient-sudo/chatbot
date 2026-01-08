
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_syntax_final():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: {{ messages.last.id |default: 0 }}
    # We want to replace it specifically.
    
    # We'll use a very specific replace first.
    bad_pattern = "{{ messages.last.id |default: 0 }}"
    good_pattern = "{{ messages.last.id|default:0 }}"
    
    new_content = content.replace(bad_pattern, good_pattern)
    
    if new_content == content:
        print("Direct string replacement did not find the exact string. Trying regex for spacing variations...")
        # Regex to match {{ messages.last.id (spaces) | (spaces) default (spaces) : (spaces) 0 }}
        regex_pattern = r'\{\{\s*messages\.last\.id\s*\|\s*default\s*:\s*0\s*\}\}'
        new_content, count = re.subn(regex_pattern, good_pattern, content)
        if count > 0:
             print(f"Regex found and fixed {count} instances.")
        else:
             print("Regex also failed to find the pattern. Please check the file content manually.")
    else:
        print("Fixed syntax error using string replacement.")

    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("File updated successfully.")

if __name__ == "__main__":
    fix_syntax_final()
