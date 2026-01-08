
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_multiline_tags():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We want to find the tag that looks like:
    # {{
    # selected_user.name|default:selected_user.phone_no|slice:":2"|upper
    # }}
    # And turn it into {{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}
    
    # Generic flattener for this specific tag content
    # matches {{ (whitespace) selected_user... (whitespace) }}
    pattern = re.compile(r'\{\{\s*(selected_user\.name\|default:selected_user\.phone_no\|slice:":2"\|upper)\s*\}\}', re.DOTALL)
    
    def replacer(match):
        # Return the flattened version
        return "{{ " + match.group(1) + " }}"

    new_content, count = pattern.subn(replacer, content)

    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {count} multiline template tag(s).")
    else:
        print("No multiline tags found matching the pattern. Checking for close variants...")
        
        # Checking if maybe my pattern is too strict?
        # Let's search just for the content string
        if 'selected_user.name|default:selected_user.phone_no|slice:":2"|upper' in content:
            # find where it is
            idx = content.find('selected_user.name|default:selected_user.phone_no|slice:":2"|upper')
            # Look around it
            start = max(0, idx - 20)
            end = min(len(content), idx + 100)
            snippet = content[start:end]
            print(f"Found the content string in context: {snippet!r}")
            
            # If we see it inside {{\n ... \n}}, we can try a broader regex or manual fix logic here if needed.
            # But usually re.DOTALL matches strictly.
        else:
             print("Could not even find the tag content string!")

if __name__ == "__main__":
    fix_multiline_tags()
