import re

path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 238 (index 237) has: <div class="avatar"...>{{
# Line 239 (index 238) has:   selected_user...|upper }}</div>
# We need to merge them into one line

if 'style="width:36px;height:36px">{{\n' in lines[237] or 'style="width:36px;height:36px">{{\\n' in lines[237]:
    # Merge line 238 and 239
    merged = lines[237].rstrip('\r\n') + ' ' + lines[238].lstrip()
    # Also remove the extra spaces
    merged = merged.replace('>{{ ', '>{{ ').replace('{{  ', '{{ ')
    lines[237] = merged
    del lines[238]
    print(f"Merged line: {merged[:100]}...")
else:
    print(f"Pattern not found. Line 237: {lines[237][:80]}")

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("File saved!")
