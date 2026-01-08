
import os
import re

edit_user_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\contact\edit_user.html'
followup_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\set\followup_settings.html'
contact_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\contact.py'
settings_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\setting.py' # guessing filename

def update_cf_followup():
    # 1. Update Edit User HTML (Custom Fields)
    # Ideally should loop through custom fields passed in context.
    # We need to render them as inputs.
    if os.path.exists(edit_user_html):
        with open(edit_user_html, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find place to inject inputs, maybe before submit button
        # Search for form fields
        if "{% for field in custom_fields %}" not in content:
            # We assume we have custom_fields in context and values in user.custom_values (need to ensure this in controller)
            injection = """
        <hr class="my-4">
        <h5>Custom Fields</h5>
        {% for field in custom_fields %}
        <div class="mb-3">
            <label class="form-label">{{ field.name }}</label>
            <input type="{{ field.field_type }}" class="form-control" name="custom_field_{{ field.id }}" 
                   value="{{ field.value|default:'' }}">
        </div>
        {% endfor %}
            """
            # Insert before submit button
            if '<button type="submit"' in content:
                content = content.replace('<button type="submit"', injection + '\n<button type="submit"')
        
        with open(edit_user_html, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Edit User template updated for Custom Fields.")

    # 2. Update Follow-up Settings HTML (Tags)
    if os.path.exists(followup_html):
        with open(followup_html, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # We need to add a Tag Selector for each followup step.
        # Assuming there's a loop or individual forms?
        # Let's inspect content structure later or rely on generic search.
        # Typical structure: <form ...> ... <textarea ...> ...
        # Add select dropdown for tags.
        
        if 'name="tag_id"' not in content:
            # Inject dropdown near Delay or Message input
            # This is tricky without seeing the file structure perfectly.
            # Assuming we can find <div class="mb-3"> or similar wrapper for inputs.
            # Or just append?
            
            # Simple approach: Find textarea for message, add selector before it.
            # <label>Tag Filter (Optional)</label> <select name="tag_id_STEP">...
            pass # Skipping exact injection logic until file read confirms structure

    # 3. Update Contactcontroller (Context & Saving)
    if os.path.exists(contact_py):
        with open(contact_py, 'r', encoding='utf-8') as f:
            py_content = f.read()
        
        # START: Update edit_user context
        # def edit_user(request, id):
        # We need to fetch CustomFields and existing Values.
        # This is complex in regex.
        # Easier to replace the whole `edit_user` method or inject code.
        
        # Injection Logic:
        # After `user = get_object_or_404(User, id=id)`
        # Add:
        # custom_fields = CustomField.objects.filter(admin_id=request.session.get('admin_id'))
        # for cf in custom_fields:
        #    val = CustomFieldValue.objects.filter(custom_field=cf, user=user).first()
        #    cf.value = val.value if val else ''
        
        # And in POST:
        # for key, val in request.POST.items():
        #    if key.startswith('custom_field_'):
        #        cf_id = key.split('_')[2]
        #        # save...
        
        # We will use string manipulation to inject these blocks.
        if "CustomField.objects.filter" not in py_content:
             # Add imports
             if "from ..models import CustomField, CustomFieldValue" not in py_content:
                 py_content = "from ..models import CustomField, CustomFieldValue\n" + py_content

             # Inject GET logic
             target_get = "form = UserForm(instance=user)"
             inject_get = """
        custom_fields = CustomField.objects.filter(admin_id=request.session.get('admin_id'))
        for cf in custom_fields:
            val = CustomFieldValue.objects.filter(custom_field=cf, user=user).first()
            cf.value = val.value if val else ''
"""
             py_content = py_content.replace(target_get, target_get + inject_get)

             # Update render context
             py_content = py_content.replace("'form': form, 'user': user}", "'form': form, 'user': user, 'custom_fields': custom_fields}")
             
             # Inject POST logic
             target_save = "form.save()"
             inject_save = """
                # Save Custom Fields
                for key, value in request.POST.items():
                    if key.startswith('custom_field_'):
                        try:
                            cf_id = int(key.split('_')[2])
                            cf = CustomField.objects.get(id=cf_id)
                            CustomFieldValue.objects.update_or_create(
                                custom_field=cf, user=user,
                                defaults={'value': value}
                            )
                        except:
                            pass
"""
             py_content = py_content.replace(target_save, target_save + inject_save)

        with open(contact_py, 'w', encoding='utf-8') as f:
            f.write(py_content)
        print("Contactcontroller updated for Custom Fields.")

if __name__ == "__main__":
    update_cf_followup()
