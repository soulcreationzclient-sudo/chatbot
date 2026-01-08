
import re
import os

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_avatar_tag():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find the broken tag. 
    # It attempts to match: <div class="avatar" ...> {{ ... }} </div>
    # allowing for newlines inside {{ ... }}
    
    pattern = r'(<div class="avatar"[^>]*>)\s*\{\{\s*selected_user\.name\|default:selected_user\.phone_no\|slice:":2"\|upper\s*\}\}\s*(</div>)'
    
    # Replacement: single line
    replacement = r'\1{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}\2'
    
    # Also try a broader regex in case the specific one fails due to extra pipe spaces etc
    # Matches {{ ... selected_user.name ... }} across lines
    pattern_broad = r'(\{\{\s*selected_user\.name\|default:selected_user\.phone_no\|slice:":2")\s+(\|upper\s*\}\})'
    
    new_content = re.sub(pattern_broad, r'\1\2', content)
    
    # Let's clean up any remaining newlines within the curly braces for this specific tag
    # searching for the specific sequence
    
    # Force replacement of the known problematic chunk if regex is too tricky
    # We look for the start of the tag and the end
    search_start = 'selected_user.name|default:selected_user.phone_no|slice:":2"'
    search_end = '|upper }}'
    
    if search_start in new_content and search_end in new_content:
        # Check if they are separated by header? No, just whitespace.
        # Let's just do a manual string cleanup if regex misses
        pass

    # A more aggressive regex for the whole div
    pattern_full_div = r'(<div class="avatar"[^>]*>)\s*\{\{.*?\}\}\s*(</div>)'
    
    # We only want to replace the ONE in the thread head. 
    # It follows {% if selected_user %}
    
    marker = '{% if selected_user %}'
    start_idx = new_content.find(marker)
    if start_idx != -1:
        # Look specifically in this area
        sub_content = new_content[start_idx:]
        div_start = sub_content.find('<div class="avatar"')
        if div_start != -1:
            div_end = sub_content.find('</div>', div_start)
            if div_end != -1:
                # Found the div block
                full_block_idx_start = start_idx + div_start
                full_block_idx_end = start_idx + div_end + 6
                
                old_block = new_content[full_block_idx_start:full_block_idx_end]
                print(f"DEBUG: Found block: {old_block}")
                
                new_block = '<div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>'
                
                new_content = new_content[:full_block_idx_start] + new_block + new_content[full_block_idx_end:]
                print("Replaced block with clean single-line version.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

if __name__ == "__main__":
    fix_avatar_tag()
