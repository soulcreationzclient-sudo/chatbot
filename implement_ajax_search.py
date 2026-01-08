
import os

inbox_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\inbox.py'
dashboard_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'
partial_dir = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\partials'
partial_html = os.path.join(partial_dir, 'user_list.html')

def implement_ajax():
    # 0. Ensure partials dir exists
    if not os.path.exists(partial_dir):
        os.makedirs(partial_dir)

    # 1. Create Partial
    # Fixing is_active logic to check against selected_user.id
    partial_content = """{% for u in users %}
<a class="item {% if selected_user and selected_user.id == u.id %}active{% endif %}" href="{% url 'inbox_dashboard' %}?user_id={{ u.id }}{% if request.GET.search %}&search={{ request.GET.search }}{% endif %}{% if request.GET.tag_id %}&tag_id={{ request.GET.tag_id }}{% endif %}">
  <div class="avatar">{{ u.name|default:u.phone_no|slice:":2"|upper }}</div>
  <div>
    <div class="name">{{ u.name|default:"User" }}</div>
    <div class="preview">{{ u.phone_no }}</div>
  </div>
  <div class="time"></div>
</a>
{% empty %}
<div class="p-3 text-muted">No users found.</div>
{% endfor %}
"""
    with open(partial_html, 'w', encoding='utf-8') as f:
        f.write(partial_content)
    print("Created user_list.html partial.")

    # 2. Update inbox.py
    if os.path.exists(inbox_py):
        with open(inbox_py, 'r', encoding='utf-8') as f:
            py = f.read()
        
        # Check for AJAX logic
        if "if request.GET.get('ajax'):" not in py:
            # We insert it before the final return render
            # Find the return render block
            target_return = "return render(request, 'inbox/dashboard.html', {"
            
            # Construct insertion
            ajax_logic = """
        if request.GET.get('ajax'):
            return render(request, 'inbox/partials/user_list.html', {
                'users': users,
                'selected_user': selected_user
            })

        """
            py = py.replace(target_return, ajax_logic + target_return)
            
            with open(inbox_py, 'w', encoding='utf-8') as f:
                f.write(py)
            print("Updated inbox.py for AJAX.")

    # 3. Update dashboard.html
    if os.path.exists(dashboard_html):
        with open(dashboard_html, 'r', encoding='utf-8') as f:
            html = f.read()

        # A. Replace Loop with Include and Container
        # The loop starts with {% for u in users %} and ends with {% endfor %} inside <div class="items">
        # Let's find <div class="items">
        if '<div class="items">' in html:
            start_items = html.find('<div class="items">')
            end_items = html.find('</div>', start_items + 1)
            # Actually, `items` div contains the loop. We want to KEEP the `items` div but replace contents.
            # But wait, looking at file view, `items` contains the loop directly.
            # <section class="list"> ... <div class="items"> {% for ... %} ... {% endfor %} </div> </section>
            
            # We can just replace the whole `div class="items"` block with one that has ID and include
            replacement_items = """<div class="items" id="userListContainer">
      {% include "inbox/partials/user_list.html" %}
    </div>"""
            
            # Use regex to find the block? Or just string matching if we are careful.
            # The current content is roughly known.
            # Let's try to locate the start and end of `items` div accurately.
            # It starts at `start_items`.
            # We need to find the matching closing div. Since it contains children `div`s, simpler find might fail.
            # But the loop structure is simple. 
            
            # Let's rely on wiping `items` content.
            # We'll regex replace the whole div if possible, OR replace known unique strings.
            # "{% for u in users %}" ... "{% endfor %}"
            
            loop_start = html.find('{% for u in users %}')
            loop_end = html.find('{% endfor %}') + 13 # len("{% endfor %}")
            
            if loop_start != -1 and loop_end != -1:
                # Check for empty block too? "{% empty %} ... "
                # The loop structure in dashboard.html is:
                # {% for u in users %} ... {% empty %} ... {% endfor %}
                
                # So replacing from {% for %} to {% endfor %} with the include is perfect.
                html = html[:loop_start] + '{% include "inbox/partials/user_list.html" %}' + html[loop_end:]
                
                # Also add ID to items div if not present
                html = html.replace('<div class="items">', '<div class="items" id="userListContainer">')
                print("Dashboard HTML template updated with Partial.")

        # B. Update AJAX JS
        # We need to change `window.location.href = ...` to a fetch call
        if "async function applyFilters()" not in html:
            # We replace the previous `applyFilters`
            
            new_js = """
  async function applyFilters() {
    const tagId = document.getElementById('tagFilter').value;
    const search = document.getElementById('userSearch').value.trim();
    
    const url = new URL(window.location.href);
    
    if (tagId) url.searchParams.set('tag_id', tagId);
    else url.searchParams.delete('tag_id');
    
    if (search) url.searchParams.set('search', search);
    else url.searchParams.delete('search');
    
    // Update Browser URL without reload
    window.history.pushState({}, '', url);

    // Fetch Partial
    url.searchParams.set('ajax', '1');
    try {
        const res = await fetch(url);
        if (res.ok) {
            const html = await res.text();
            document.getElementById('userListContainer').innerHTML = html;
        }
    } catch (e) {
        console.error("Search error:", e);
    }
  }
"""
            # Replace old function
            # Old: function applyFilters() { ... window.location.href = ... }
            # We can use regex or just replace the string we injected earlier.
            
            # Find the old function block
            start_fn = html.find('function applyFilters() {')
            if start_fn != -1:
                end_fn = html.find('}', html.find('window.location.href', start_fn)) + 1
                html = html[:start_fn] + new_js + html[end_fn:]
            else:
                # Maybe it's the even older applyInboxFilter?
                # No, we injected applyFilters in previous step.
                pass

        with open(dashboard_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print("Dashboard JS updated for AJAX.")

if __name__ == "__main__":
    implement_ajax()
