path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the default filter - remove space after colon
old = '|default: 0'
new = '|default:0'

if old in content:
    content = content.replace(old, new)
    print(f"Fixed: '{old}' -> '{new}'")
else:
    print(f"Pattern '{old}' not found!")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("File saved!")
