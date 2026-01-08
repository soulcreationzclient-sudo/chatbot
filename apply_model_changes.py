
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\models.py'

def apply_model_changes():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add CustomField and CustomFieldValue models if not present
    if 'class CustomField(models.Model):' not in content:
        print("Adding CustomField and CustomFieldValue models...")
        new_models = """

class CustomField(models.Model):
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, default='text') # text, number, date
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'custom_fields'
        unique_together = ('admin', 'name')

class CustomFieldValue(models.Model):
    id = models.AutoField(primary_key=True)
    custom_field = models.ForeignKey(CustomField, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    value = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'custom_field_values'
        unique_together = ('custom_field', 'user')
"""
        content += new_models
    else:
        print("CustomField models already exist.")

    # 2. Modify FollowUpMessage to include tag field
    # Find class FollowUpMessage
    # We want to add: tag = models.ForeignKey('Tag', on_delete=models.SET_NULL, null=True, blank=True)
    # inside the class definition.
    
    if 'class FollowUpMessage(models.Model):' in content and 'tag = models.ForeignKey' not in content.split('class FollowUpMessage')[1].split('class Meta')[0]:
        print("Adding tag field to FollowUpMessage...")
        # Use simple string replacement to inject the field after 'message = ...'
        target = "message = models.TextField(help_text=\"The follow-up message content\")"
        inject = "\n    tag = models.ForeignKey('Tag', on_delete=models.SET_NULL, null=True, blank=True, help_text=\"Only send to users with this tag (optional)\")"
        content = content.replace(target, target + inject)
    else:
        print("FollowUpMessage already has a tag field or class not found.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Models updated successfully.")

if __name__ == "__main__":
    apply_model_changes()
