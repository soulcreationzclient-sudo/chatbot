
import os
import re

dashboard_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_html():
    if not os.path.exists(dashboard_html):
        print("File not found")
        return

    with open(dashboard_html, 'r', encoding='utf-8') as f:
        content = f.read()

    # We want to replace everything from <section class="list"> to </section> (inclusive)
    # But since regex might be tricky with newlines, we'll look for markers.
    
    start_marker = '<!-- Conversation list -->'
    end_marker = '<!-- Thread -->'
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        print("Markers not found.")
        return

    # The clean list section
    clean_section = """<!-- Conversation list -->
  <section class="list">
    <div class="list-head">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <span>Inbox</span>
        <select id="tagFilter" class="form-select form-select-sm" style="width:auto;" onchange="applyFilters()">
          <option value="">All Tags</option>
          {% for t in all_tags %}
          <option value="{{ t.id }}" {% if request.GET.tag_id == t.id|stringformat:"s" %}selected{% endif %}>{{ t.name }}</option>
          {% endfor %}
        </select>
      </div>
      <input type="text" id="userSearch" class="form-control form-control-sm" placeholder="Search name or phone..." value="{{ request.GET.search|default:'' }}" onkeyup="debounceSearch()">
    </div>
    <div class="items" id="userListContainer">
      {% include "inbox/partials/user_list.html" %}
    </div>
  </section>

  """
    
    # Replace the chunk
    new_content = content[:start_idx] + clean_section + content[end_idx:]
    
    with open(dashboard_html, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Dashboard HTML fixed.")

if __name__ == "__main__":
    fix_html()
