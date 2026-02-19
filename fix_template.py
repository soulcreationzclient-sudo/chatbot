"""Fix the avatar template expression split across lines"""
path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix: The multiline {{ }} tag on lines 576-577 needs to be on one line
# and we need to use {% firstof %} or a simpler approach
old = '''<div class="avatar" style="width:36px;height:36px">{{
        selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>'''

new = '''<div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("FIXED: Joined multiline template tag onto single line")
else:
    print("Pattern not found - checking alternative...")
    # Try to find it with different whitespace
    import re
    pattern = re.compile(r'<div class="avatar"[^>]*>\{\{\s*\n\s*selected_user\.name\|default:selected_user\.phone_no\|slice:":2"\|upper\s*\}\}', re.MULTILINE)
    m = pattern.search(content)
    if m:
        found = m.group(0)
        # Replace with single-line version
        fixed = found.replace('\n', '').replace('  ', ' ')
        # Clean up extra spaces
        fixed = re.sub(r'\{\{\s+', '{{ ', fixed)
        fixed = re.sub(r'\s+\}\}', ' }}', fixed)
        content = content.replace(found, fixed)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"FIXED (regex): Joined multiline template tag")
        print(f"  Was: {repr(found[:100])}")
        print(f"  Now: {repr(fixed[:100])}")
    else:
        print("Could not find pattern at all")

# Verify
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if 'selected_user.name' in l and 'slice' in l:
        print(f"  Line {i+1}: {l.strip()}")
