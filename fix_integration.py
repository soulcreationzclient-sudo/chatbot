import os

path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\set\integration.html'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix lines 391-392
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Check if this is the broken line
    if 'id="followupEnabled" {% if admin.followup_enabled' in line and i + 1 < len(lines):
        next_line = lines[i + 1]
        if '%}checked{% endif %}>' in next_line:
            # Combine into one line
            fixed_line = '            <input class="form-check-input" type="checkbox" id="followupEnabled" {% if admin.followup_enabled %}checked{% endif %}>\r\n'
            fixed_lines.append(fixed_line)
            i += 2  # Skip both lines
            continue
    fixed_lines.append(line)
    i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print('Fixed! Lines changed.')
