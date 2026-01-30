path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the tag_id comparison - add spaces around ==
old = 'request.GET.tag_id==t.id'
new = 'request.GET.tag_id == t.id'

if old in content:
    content = content.replace(old, new)
    print(f"Fixed: '{old}' -> '{new}'")
else:
    print(f"Pattern '{old}' not found!")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("File saved!")
