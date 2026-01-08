
import os

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\set\tags.html'

def fix_template():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The issue: {{tag:add:tag_name}} and {{tag:remove:tag_name}} are being parsed as variables.
    # We need to escape them using {% templatetag openvariable %} and {% templatetag closevariable %}
    
    # Target strings to replace
    bad_syntax_1 = '<code>{{tag:add:tag_name}}</code>'
    bad_syntax_2 = '<code>{{tag:remove:tag_name}}</code>'
    
    # Correct strings
    correct_syntax_1 = '<code>{% templatetag openvariable %}tag:add:tag_name{% templatetag closevariable %}</code>'
    correct_syntax_2 = '<code>{% templatetag openvariable %}tag:remove:tag_name{% templatetag closevariable %}</code>'
    
    new_content = content
    replaced = False

    if bad_syntax_1 in new_content:
        new_content = new_content.replace(bad_syntax_1, correct_syntax_1)
        print(f"Fixed: {{tag:add:tag_name}}")
        replaced = True
    else:
        print(f"Not found or already fixed: {{tag:add:tag_name}}")

    if bad_syntax_2 in new_content:
        new_content = new_content.replace(bad_syntax_2, correct_syntax_2)
        print(f"Fixed: {{tag:remove:tag_name}}")
        replaced = True
    else:
        print(f"Not found or already fixed: {{tag:remove:tag_name}}")

    if replaced:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Successfully overwrote tags.html with corrections.")
    else:
        print("No changes made.")

    # Verification: Read back to confirm
    with open(file_path, 'r', encoding='utf-8') as f:
        final_content = f.read()
        if '{% templatetag openvariable %}tag:add:tag_name' in final_content:
            print("Verification PASSED: Found escaped tag.")
        else:
            print("Verification FAILED: Did not find escaped tag.")

if __name__ == "__main__":
    fix_template()
