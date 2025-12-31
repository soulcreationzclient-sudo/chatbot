from django.db import models

class Admin(models.Model):
    id=models.AutoField(primary_key=True)
    email=models.TextField()
    password=models.TextField()
    whatsapp_phone_id=models.TextField()
    whatsapp_token=models.TextField()
    pinecone_token=models.TextField()
    assistant_name = models.CharField(max_length=100, null=True, blank=True, default='')
    created_at=models.DateTimeField(auto_now_add=True)
    display_phone_no=models.TextField()
    goolgle_calendar=models.TextField()
    openai_api_key = models.TextField(blank=True, null=True)
    CHATGPT_MODE_CHOICES = (
        ('prompt', 'Prompt'),
        ('ai_agent', 'AI Agent'),
    )
    chatgpt_mode = models.CharField(max_length=20, choices=CHATGPT_MODE_CHOICES, default='prompt')
    
    # Calendly Integration
    calendly_token = models.TextField(blank=True, null=True)           # Personal Access Token
    calendly_scheduling_url = models.TextField(blank=True, null=True)  # Event type URL for booking
    
    # Follow-up Settings  
    followup_delay_minutes = models.IntegerField(default=10)           # Minutes between follow-ups
    followup_enabled = models.BooleanField(default=True)               # Enable/disable follow-ups

    
    
    class Meta:
        managed=True
        db_table='admins'

class User(models.Model):
    id = models.AutoField(primary_key=True)
    admin_id=models.ForeignKey(Admin,on_delete=models.DO_NOTHING,db_column='admin_id')
    name = models.CharField(max_length=100)
    phone_no= models.CharField(max_length=20)
    created_at = models.DateTimeField()
    is_escalation = models.BooleanField(default=False)
    followup_count = models.IntegerField(default=0)  # Track follow-up attempts (max 3)

    class Meta:
        # managed = False  # This tells Django: don't create or modify this table
        db_table = 'users'  # Must exactly match your phpMyAdmin table name

class Message(models.Model):
    WHO_CHOICES=[
        ('user','User'),
        ('bot','Bot')
    ]
    id = models.AutoField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='user_id')
    # user_id = models.ForeignKey('newapp.User', on_delete=models.DO_NOTHING, db_column='user_id')
    messages = models.TextField()
    created_at = models.DateTimeField()
    who=models.CharField(max_length=10, choices=WHO_CHOICES)

    class Meta:
        managed = True
        db_table = 'conversations' 


# Create your models here.
# models.py (add these below your existing models)

class Tag(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tags'  # You can create this new table via migrations later


class UserTag(models.Model):
    id = models.AutoField(primary_key=True)
    # user = models.ForeignKey('newapp.User', on_delete=models.CASCADE, db_column='user_id')
    # tag = models.ForeignKey('newapp.Tag', on_delete=models.CASCADE, db_column='tag_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, db_column='tag_id')

    class Meta:
        db_table = 'user_tags'  # New table for user-tag relationships
        unique_together = ('user', 'tag')  # prevent duplicate mappings

# class User(models.Model):
#     id = models.AutoField(primary_key=True)
#     admin_id = models.ForeignKey(Admin, on_delete=models.DO_NOTHING, db_column='admin_id')
#     name = models.CharField(max_length=100)
#     phone_no = models.CharField(max_length=20)
#     created_at = models.DateTimeField()

#     class Meta:
#         managed = False
#         db_table = 'users'

#     def __str__(self):
#         return f"{self.name} ({self.phone_no})"
     
class ChatGPTPrompt(models.Model):
    prompt_text = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ChatGPT Prompt (updated {self.updated_at})"
    
class AIAgentConfig(models.Model):
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE)
    pdf_file = models.FileField(upload_to='ai_agent_pdfs/')  # PDFs will be uploaded to MEDIA_ROOT/ai_agent_pdfs/
    instruction = models.TextField(blank=True)
    pdf_text = models.TextField(blank=True, null=True)               
    is_active = models.BooleanField(default=True)            
    uploaded_at = models.DateTimeField(auto_now_add=True)    

    class Meta:
        db_table = 'ai_agent_config'
        
    def __str__(self):
        return f"AI Agent Config - {self.pdf_file.name} - Active: {self.is_active}"  
    
from django import forms
from .models import AIAgentConfig

class AIAgentConfigForm(forms.ModelForm):
    class Meta:
        model = AIAgentConfig
        fields = ['pdf_file', 'instruction']

class ExternalAPI(models.Model):
    HTTP_METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ]
    BODY_TYPE_CHOICES = [
        ('json', 'JSON'),
        ('form', 'Form-encoded'),
        ('none', 'No Body'),
    ]
    
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, help_text="Name of the function for the AI to call (e.g., check_booking)")
    description = models.TextField(help_text="Description for the AI explaining when to use this tool")
    url = models.URLField(max_length=500)
    method = models.CharField(max_length=10, choices=HTTP_METHOD_CHOICES, default='POST')
    headers = models.JSONField(default=dict, blank=True, help_text="JSON headers")
    body_type = models.CharField(max_length=20, choices=BODY_TYPE_CHOICES, default='json')
    payload = models.JSONField(default=dict, blank=True, help_text="JSON payload with {{placeholders}}")
    response_mapping = models.JSONField(default=list, blank=True, help_text="List of {jsonpath, custom_field} mappings")

    def __str__(self):
        return f"{self.name} ({self.admin.assistant_name if self.admin else 'No Admin'})"

    class Meta:
        db_table = 'external_apis'


class ImageAsset(models.Model):
    """
    Store images with custom names that can be referenced in AI prompts.
    Usage: {{image:menu_card}} in prompts to send the image named 'menu_card'
    """
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, help_text="Unique name to reference this image (e.g., menu_card)")
    description = models.TextField(blank=True, help_text="Description for the AI explaining when to use this image")
    image = models.ImageField(upload_to='image_assets/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.admin.assistant_name if self.admin else 'No Admin'})"

    class Meta:
        db_table = 'image_assets'
        unique_together = ('admin', 'name')
