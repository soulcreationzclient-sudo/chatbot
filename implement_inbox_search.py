
import os

inbox_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\inbox.py'
dashboard_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def apply_inbox_search():
    # 1. Update inbox.py
    if os.path.exists(inbox_py):
        with open(inbox_py, 'r', encoding='utf-8') as f:
            py = f.read()
        
        # Add Q import
        if "from django.db.models import Q" not in py:
            py = py.replace("from django.db.models import Max", "from django.db.models import Max, Q")

        # Update dashboard method
        if "search_query = request.GET.get('search')" not in py:
            # 1. Get search param
            target_vars = "tag_id = request.GET.get('tag_id')"
            replace_vars = "tag_id = request.GET.get('tag_id')\n        search_query = request.GET.get('search')"
            py = py.replace(target_vars, replace_vars)
            
            # 2. Apply search filter
            # Find where we apply tag filter, add search after
            target_filter = "users = users.filter(usertag__tag_id=tag_id)"
            replace_filter = "users = users.filter(usertag__tag_id=tag_id)\n\n        if search_query:\n            users = users.filter(Q(name__icontains=search_query) | Q(phone_no__icontains=search_query))"
            py = py.replace(target_filter, replace_filter)

        with open(inbox_py, 'w', encoding='utf-8') as f:
            f.write(py)
        print("Inbox controller updated with Search logic.")

    # 2. Update dashboard.html
    if os.path.exists(dashboard_html):
        with open(dashboard_html, 'r', encoding='utf-8') as f:
            html = f.read()

        # Insert Search Input
        if 'id="userSearch"' not in html:
            # Find list header
            target_header = '<div class="list-head d-flex justify-content-between align-items-center">'
            # We want to change structure slightly to stack them
            # Replace the entire opening div and contents until the end of that div?
            # It's safer to just inject into the div, but we want a new line.
            
            # Let's replace the whole header block regex-style or just a known chunk
            chunk_start = '<div class="list-head d-flex justify-content-between align-items-center">'
            chunk_end = '</div>'  # risky if multiple divs
            
            # Actually, let's just use the `list-head` class as anchor.
            # We will rewrite the list-head div content.
            
            new_header = """<div class="list-head">
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
    </div>"""
            
            # We need to replace the EXISTING list-head.
            # It starts with <div class="list-head ..."> and ends with </div>
            # Let's find index.
            start_idx = html.find('<div class="list-head')
            if start_idx != -1:
                # Find the closing div for this specific div.
                # Assuming indentation is reliable or snippet is small.
                # The existing snippet (from view_file):
                # <div class="list-head d-flex justify-content-between align-items-center">
                #   <span>Inbox</span>
                #   <select ...>
                #     ...
                #   </select>
                # </div>
                
                # We can search for the closing `</div>` after the `</select>`.
                select_end = html.find('</select>', start_idx)
                div_end = html.find('</div>', select_end) + 6
                
                old_block = html[start_idx:div_end]
                html = html.replace(old_block, new_header)

        # Update JS
        if "function debounceSearch()" not in html:
            js_logic = """
  // SEARCH & FILTER
  let searchTimeout;
  function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyFilters();
    }, 500);
  }

  function applyFilters() {
    const tagId = document.getElementById('tagFilter').value;
    const search = document.getElementById('userSearch').value.trim();
    
    const url = new URL(window.location.href);
    
    if (tagId) url.searchParams.set('tag_id', tagId);
    else url.searchParams.delete('tag_id');
    
    if (search) url.searchParams.set('search', search);
    else url.searchParams.delete('search');
    
    window.location.href = url.toString();
  }
"""
            # Inject before existing applyInboxFilter (which we will retire or overwrite?)
            # Existing: function applyInboxFilter(tagId) { ... }
            # We can replace the existing function with our new logic.
            
            if "function applyInboxFilter(tagId)" in html:
                 # We simply append our new functions and update the HTML to call them.
                 # The HTML update above calls `applyFilters()` and `debounceSearch()`.
                 # The old function references `onchange="applyInboxFilter(this.value)"` inside the <select>, 
                 # BUT we specifically replaced that HTML block in the step above with `onchange="applyFilters()"`.
                 # So the old function is dead code, which is fine to leave or remove.
                 # We'll just append.
                 html = html.replace('// Filter Logic', '// Filter Logic' + js_logic)
        
        with open(dashboard_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print("Dashboard HTML updated with Search UI.")

if __name__ == "__main__":
    apply_inbox_search()
