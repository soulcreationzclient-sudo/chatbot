
import re
import os

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_robust():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Target the specific complex string
    # We want valid: {{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}
    
    target_string = 'selected_user.name|default:selected_user.phone_no|slice:":2"|upper'
    
    # 1. Find any occurrences of target_string that are NOT properly enclosed
    #    Regex is hard for "not enclosed", so we'll just find ALL occurrences and standardize them.
    
    # We find the target_string, possibly surrounded by mess
    # We also look for {{ occurring before it with whitespace/newlines
    
    # Pattern:
    # (optional {{) (whitespace) target_string (whitespace) (optional }})
    
    regex = r'(\{\{\s*)?' + re.escape(target_string) + r'(\s*\}\})?'
    
    def replacer(match):
        # We always want the full clean tag
        return '{{ ' + target_string + ' }}'

    # Replace all matches
    new_content = re.sub(regex, replacer, content)
    
    # 2. Check for the "split" case: {{ on one line, content on next
    #    The above regex might handle it if we flag DOTALL, but re.sub defaults are line-based? No, re.sub works on string.
    #    But we need to ensure we consume the {{ if it's far away.
    
    # Let's try a wider regex for the split case specifically
    regex_split = r'\{\{\s+' + re.escape(target_string)
    new_content = re.sub(regex_split, '{{ ' + target_string, new_content)

    # 3. Clean up any double braces if we over-corrected?
    #    e.g. {{ {{ ... }} }}
    new_content = new_content.replace('{{ {{', '{{').replace('}} }}', '}}')
    
    if content != new_content:
        print("Fixed broken tags.")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    else:
        print("No matches found to fix.")

if __name__ == "__main__":
    fix_robust()
