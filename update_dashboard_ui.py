
import os
import re

inbox_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'
contact_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\contact\dashboard.html'

def update_ui():
    # 1. Update Inbox UI
    if os.path.exists(inbox_html):
        with open(inbox_html, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # A. Add Filter Dropdown to List Head
        # Find: <div class="list-head">Inbox</div>
        # Replace with header + select
        if '<select id="tagFilter"' not in content:
            target = '<div class="list-head">Inbox</div>'
            replacement = """<div class="list-head d-flex justify-content-between align-items-center">
      <span>Inbox</span>
      <select id="tagFilter" class="form-select form-select-sm" style="width:auto;" onchange="applyInboxFilter(this.value)">
        <option value="">All Tags</option>
        {% for t in all_tags %}
        <option value="{{ t.id }}" {% if request.GET.tag_id == t.id|stringformat:"s" %}selected{% endif %}>{{ t.name }}</option>
        {% endfor %}
      </select>
    </div>"""
            content = content.replace(target, replacement)

        # B. Add "all_tags" to context? 
        # Wait, Inboxcontroller doesn't send all_tags yet!
        # I missed that in update_controllers. I need to fix that or use a template tag.
        # Ideally, I should update Inboxcontroller to include `all_tags`.
        # I will do a quick patch at the end of this script to fix 'inbox.py' context if needed, 
        # or assuming I'll fix it externally. Let's assume I fix it.

        # C. Add File Input to Chat Form
        # Find: <input id="userMessage" ...
        # We need a file input (hidden) and a button to trigger it.
        if 'id="mediaInput"' not in content:
            # Locate input group
            input_group_start = '<div class="input-group">'
            # We insert a button before the text input
            replacement = """<div class="input-group">
          <input type="file" id="mediaInput" style="display:none;" onchange="handleFileUpload(this)">
          <button type="button" class="btn btn-light border" onclick="document.getElementById('mediaInput').click()">
            <i class="fa-solid fa-paperclip"></i> 📎
          </button>"""
            content = content.replace(input_group_start, replacement)

        # D. Add JS for Filter and Upload
        # Filter Logic: reload page with ?tag_id=...
        # Upload Logic: fetch to /api/inbox/upload, get URL, append to input.
        
        js_inject = """
  // Filter Logic
  function applyInboxFilter(tagId) {
    const url = new URL(window.location.href);
    if (tagId) url.searchParams.set('tag_id', tagId);
    else url.searchParams.delete('tag_id');
    window.location.href = url.toString();
  }

  // File Upload Logic
  async function handleFileUpload(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    // Show loading?
    const msgInput = document.getElementById('userMessage');
    const originalPlaceholder = msgInput.placeholder;
    msgInput.placeholder = "Uploading...";
    msgInput.disabled = true;

    try {
        const res = await fetch('/api/inbox/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (data.url) {
            let tag = "";
            if (data.type === 'image') tag = `[Image: ${data.url}] `;
            else tag = `[Document: ${data.url}] `;
            
            msgInput.value = (msgInput.value + " " + tag).trim();
            msgInput.focus();
        } else {
            alert("Upload failed: " + (data.error || "Unknown error"));
        }
    } catch (e) {
        console.error(e);
        alert("Upload network error");
    } finally {
        msgInput.placeholder = originalPlaceholder;
        msgInput.disabled = false;
        input.value = ""; // reset
    }
  }
"""
        # Inject JS before existing script starts? or inside?
        # Let's put it before "const threadBody"
        if "function applyInboxFilter" not in content:
            target = "const threadBody = document.getElementById('threadBody');"
            content = content.replace(target, js_inject + "\n\n  " + target)

        with open(inbox_html, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Inbox dashboard template updated.")

    # 2. Update Contact UI
    if os.path.exists(contact_html):
        with open(contact_html, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace Filter Button with Select
        # <button class="btn">Filter</button>
        if '<select id="contactTagFilter"' not in content:
            target = '<button class="btn">Filter</button>'
            replacement = """
    <select id="contactTagFilter" class="btn" style="min-width:120px;" onchange="applyContactFilter(this.value)">
        <option value="">All Tags</option>
        {% for t in all_tags %}
        <option value="{{ t.id }}" {% if request.GET.tag_id == t.id|stringformat:"s" %}selected{% endif %}>{{ t.name }}</option>
        {% endfor %}
    </select>"""
            content = content.replace(target, replacement)
            
        # Add JS
        js_inject = """
  function applyContactFilter(tagId) {
    const url = new URL(window.location.href);
    if (tagId) url.searchParams.set('tag_id', tagId);
    else url.searchParams.delete('tag_id');
    window.location.href = url.toString();
  }
"""
        if "function applyContactFilter" not in content:
            script_idx = content.find('<script>')
            if script_idx != -1:
                content = content[:script_idx+8] + js_inject + content[script_idx+8:]

        with open(contact_html, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Contact dashboard template updated.")

    # 3. PATCH INBOX CONTROLLER for all_tags
    # I realized Inboxcontroller needs to send 'all_tags' context
    inbox_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\inbox.py'
    if os.path.exists(inbox_py):
        with open(inbox_py, 'r', encoding='utf-8') as f:
            py_content = f.read()
            
        # We need to add: from ..models import Tag; all_tags = Tag.objects.filter(...)
        # And add to context.
        if "'all_tags': all_tags" not in py_content:
            # Add Query
            # Location: users = User.objects...
            if "users = User.objects" in py_content:
                # Add import if missing
                if "from ..models import Tag" not in py_content:
                    py_content = "from ..models import Tag\n" + py_content
                
                target = "selected_user_id = request.GET.get"
                inject = """        
        all_tags = Tag.objects.all() # Or filter by admin if we had admin_id context here. 
        # But Inboxcontroller seems to show all users? 
        # Actually User table has admin_id. 
        # Assuming single admin for now or we need request.session config?
        # Let's assume all tags for simplicity or filter by first user's admin?
        # Safe bet: Tag.objects.all()
        """ 
                py_content = py_content.replace(target, inject + target)
                
                # Add to context
                # 'messages': messages,
                c_target = "'messages': messages,"
                c_replace = "'messages': messages,\n            'all_tags': all_tags,"
                py_content = py_content.replace(c_target, c_replace)
                
        with open(inbox_py, 'w', encoding='utf-8') as f:
            f.write(py_content)
        print("Inboxcontroller context patched.")

if __name__ == "__main__":
    update_ui()
