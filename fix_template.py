"""Fix all Django template syntax issues in dashboard.html"""
import re

path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

fixes = 0

# Fix 1: |default: 0  ->  |default:0  (space after colon breaks Django 5)
if '|default: 0' in content:
    content = content.replace('|default: 0', '|default:0')
    fixes += 1
    print("[FIXED] |default: 0 -> |default:0")

# Fix 2: ==tid without spaces (already done but double check)
if 'tag_id==tid' in content:
    content = content.replace('tag_id==tid', 'tag_id == tid')
    fixes += 1
    print("[FIXED] ==tid spacing")

# Fix 3: Search for any other |default with space after colon
import re
matches = re.findall(r'\|default:\s+\S+', content)
for m in matches:
    fixed = m.replace(': ', ':')
    if m != fixed:
        content = content.replace(m, fixed)
        fixes += 1
        print(f"[FIXED] '{m}' -> '{fixed}'")

if fixes > 0:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nDone! {fixes} fix(es) applied and saved.")
else:
    print("\nNo issues found.")
