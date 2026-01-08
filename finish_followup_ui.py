
import os

settings_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\settings.py'
followup_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\set\followup_settings.html'

def finish_followup():
    # 1. Update settings.py
    if os.path.exists(settings_py):
        with open(settings_py, 'r', encoding='utf-8') as f:
            py_content = f.read()
            
        # A. Import Tag in followup_settings and add to context
        if "from ..models import Tag" not in py_content:
             # Add to imports inside method or global? Global is cleaner but method is safer for regex replacing.
             # existing: def followup_settings(request):
             #           from ..models import FollowUpMessage
             target_def = "def followup_settings(request):\n        from ..models import FollowUpMessage"
             replacement = "def followup_settings(request):\n        from ..models import FollowUpMessage, Tag"
             py_content = py_content.replace(target_def, replacement)
             
             # Fetch Tags
             # followups = FollowUpMessage...
             target_query = "followups = FollowUpMessage.objects.filter(admin=admin).order_by('step')"
             inject_query = "\n        tags = Tag.objects.filter(admin=admin)"
             py_content = py_content.replace(target_query, target_query + inject_query)
             
             # Add to context
             # 'followups': followups
             target_ctx = "'followups': followups"
             replace_ctx = "'followups': followups,\n            'tags': tags"
             py_content = py_content.replace(target_ctx, replace_ctx)

        # B. Update create logic
        # data.get('message', '') -> add tag_id
        if "tag_id=data.get('tag_id')" not in py_content:
             # Find create call
             # followup = FollowUpMessage.objects.create(
             #    ...
             #    message=data.get('message', '')
             # )
             target_create = "message=data.get('message', '')"
             replace_create = "message=data.get('message', ''),\n                tag_id=data.get('tag_id') or None"
             py_content = py_content.replace(target_create, replace_create)

        # C. Update update logic
        # followup.delay_minutes = ...
        if "followup.tag_id = data.get('tag_id')" not in py_content:
             target_update = "followup.message = data.get('message', followup.message)"
             # We want to allow clearing tag, so we might need check if key exists?
             # For simplicity, if sent, update.
             replace_update = "followup.message = data.get('message', followup.message)\n            if 'tag_id' in data:\n                followup.tag_id = data.get('tag_id') or None"
             py_content = py_content.replace(target_update, replace_update)

        with open(settings_py, 'w', encoding='utf-8') as f:
            f.write(py_content)
        print("Settings controller updated.")

    # 2. Update HTML
    if os.path.exists(followup_html):
        with open(followup_html, 'r', encoding='utf-8') as f:
            html = f.read()

        # A. Add Select to Card
        # <div class="col-md-9 mb-3">
        if 'name="tag_select"' not in html:
            # We'll split the 9 cols into 3 tag + 6 message, or row break?
            # Let's add a NEW row for Tag Filter above Message? 
            # Or make Delay col-md-3, Tag col-md-3, Message col-md-6?
            
            # Current:
            # <div class="col-md-3 mb-3"> delay </div>
            # <div class="col-md-9 mb-3"> message </div>
            
            target_cols = '<div class="col-md-9 mb-3">'
            # We want to insert a col before this or change existing structure.
            # Let's insert BEFORE message col
            new_col = """<div class="col-md-3 mb-3">
                    <label class="form-label">Tag Filter (Optional)</label>
                    <select class="form-select tag-input" data-id="{{ followup.id }}">
                        <option value="">All Users</option>
                        {% for t in tags %}
                        <option value="{{ t.id }}" {% if followup.tag_id == t.id %}selected{% endif %}>{{ t.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                """
            # We need to change message col to 6
            html = html.replace('col-md-9 mb-3', 'col-md-6 mb-3')
            # Insert new col before the (now modified) message col
            html = html.replace('<div class="col-md-6 mb-3">', new_col + '<div class="col-md-6 mb-3">')

        # B. Add Select to Add Modal
        # <div class="mb-3"> label Delay </div>
        if 'id="newTag"' not in html:
            target_delay = '<div class="form-text">Time to wait before sending this follow-up</div>\n                </div>'
            new_field = """
                <div class="mb-3">
                    <label class="form-label">Tag Filter (Optional)</label>
                    <select class="form-select" id="newTag">
                        <option value="">All Users</option>
                        {% for t in tags %}
                        <option value="{{ t.id }}">{{ t.name }}</option>
                        {% endfor %}
                    </select>
                </div>"""
            html = html.replace(target_delay, target_delay + new_field)

        # C. Update JS createFollowup
        if "tag_id: document.getElementById('newTag').value" not in html:
            # const message = ...
            # body: JSON.stringify({... message: message })
            target_js_create = "message: message })"
            replace_js_create = "message: message, tag_id: document.getElementById('newTag').value })"
            html = html.replace(target_js_create, replace_js_create)

        # D. Update JS saveFollowup
        if "const tag = card.querySelector('.tag-input').value;" not in html:
            # const message = card.querySelector('.message-input').value;
            target_get_val = "const message = card.querySelector('.message-input').value;"
            replace_get_val = "const message = card.querySelector('.message-input').value;\n        const tag = card.querySelector('.tag-input').value;"
            html = html.replace(target_get_val, replace_get_val)
            
            # Update fetch body
            # body: JSON.stringify({ delay_minutes: parseInt(delay), message: message })
            target_js_save = "message: message })"
            replace_js_save = "message: message, tag_id: tag })"
            html = html.replace(target_js_save, replace_js_save)

        with open(followup_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print("Follow-up HTML updated.")

if __name__ == "__main__":
    finish_followup()
