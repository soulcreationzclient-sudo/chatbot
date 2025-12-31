path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix lines 268-269
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Check if this is the broken line
    if '<div class="avatar" style="width:36px;height:36px">{{' in line and i+1 < len(lines):
        next_line = lines[i+1]
        if 'selected_user.name|default:selected_user.phone_no|slice:":2"|upper' in next_line:
            # Merge and fix
            new_lines.append('          <div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>\r\n')
            i += 2  # Skip both lines
            continue
    new_lines.append(line)
    i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("File fixed!")

# Verify
with open(path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if i >= 266 and i <= 270:
            print(f"Line {i}: {line.rstrip()}")
