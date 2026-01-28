from django.db import models
from django.contrib.auth.models import User as DjangoUser


class Organization(models.Model):
    """
    Represents a client organization/company.
    Each organization has its own WhatsApp config, users, and data isolation.
    """
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="URL-friendly identifier")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # WhatsApp Configuration
    whatsapp_phone_id = models.TextField(blank=True, default='')
    whatsapp_token = models.TextField(blank=True, default='')
    display_phone_no = models.TextField(blank=True, default='')
    
    # OpenAI Configuration
    openai_api_key = models.TextField(blank=True, null=True)
    assistant_name = models.CharField(max_length=100, null=True, blank=True, default='')
    CHATGPT_MODE_CHOICES = (
        ('prompt', 'Prompt'),
        ('ai_agent', 'AI Agent'),
    )
    chatgpt_mode = models.CharField(max_length=20, choices=CHATGPT_MODE_CHOICES, default='prompt')
    
    # Pinecone Configuration
    pinecone_token = models.TextField(blank=True, default='')
    
    # Calendly Integration
    calendly_token = models.TextField(blank=True, null=True)
    calendly_scheduling_url = models.TextField(blank=True, null=True)
    
    # Follow-up Settings
    followup_delay_minutes = models.IntegerField(default=10)
    followup_enabled = models.BooleanField(default=True)
    
    # Google Calendar
    google_calendar = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'organizations'
        ordering = ['name']

    def __str__(self):
        return self.name


class Role(models.Model):
    """
    Define roles and their permissions.
    Default roles: Super Admin, Client Admin, Agent, Viewer
    """
    ROLE_SUPER_ADMIN = 'super_admin'
    ROLE_CLIENT_ADMIN = 'client_admin'
    ROLE_AGENT = 'agent'
    ROLE_VIEWER = 'viewer'
    
    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, 'Super Admin'),
        (ROLE_CLIENT_ADMIN, 'Client Admin'),
        (ROLE_AGENT, 'Agent'),
        (ROLE_VIEWER, 'Viewer'),
    ]
    
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    
    # Permission flags
    can_manage_organizations = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)
    can_view_inbox = models.BooleanField(default=True)
    can_send_messages = models.BooleanField(default=True)
    can_manage_tags = models.BooleanField(default=False)
    can_manage_ai = models.BooleanField(default=False)
    can_manage_contacts = models.BooleanField(default=True)
    can_broadcast = models.BooleanField(default=False)

    class Meta:
        db_table = 'roles'

    def __str__(self):
        return self.get_name_display()
    
    @classmethod
    def create_default_roles(cls):
        """Create default roles with appropriate permissions."""
        roles = [
            {
                'name': cls.ROLE_SUPER_ADMIN,
                'description': 'Full system access. Can manage all organizations and users.',
                'can_manage_organizations': True,
                'can_manage_users': True,
                'can_manage_settings': True,
                'can_view_inbox': True,
                'can_send_messages': True,
                'can_manage_tags': True,
                'can_manage_ai': True,
                'can_manage_contacts': True,
                'can_broadcast': True,
            },
            {
                'name': cls.ROLE_CLIENT_ADMIN,
                'description': 'Full access within their organization.',
                'can_manage_organizations': False,
                'can_manage_users': True,
                'can_manage_settings': True,
                'can_view_inbox': True,
                'can_send_messages': True,
                'can_manage_tags': True,
                'can_manage_ai': True,
                'can_manage_contacts': True,
                'can_broadcast': True,
            },
            {
                'name': cls.ROLE_AGENT,
                'description': 'Can view inbox and send messages.',
                'can_manage_organizations': False,
                'can_manage_users': False,
                'can_manage_settings': False,
                'can_view_inbox': True,
                'can_send_messages': True,
                'can_manage_tags': False,
                'can_manage_ai': False,
                'can_manage_contacts': True,
                'can_broadcast': False,
            },
            {
                'name': cls.ROLE_VIEWER,
                'description': 'Read-only access.',
                'can_manage_organizations': False,
                'can_manage_users': False,
                'can_manage_settings': False,
                'can_view_inbox': True,
                'can_send_messages': False,
                'can_manage_tags': False,
                'can_manage_ai': False,
                'can_manage_contacts': False,
                'can_broadcast': False,
            },
        ]
        
        created_roles = []
        for role_data in roles:
            role, created = cls.objects.update_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            created_roles.append(role)
        return created_roles


class OrganizationUser(models.Model):
    """
    Links a Django User to an Organization with a specific Role.
    Super Admins may have organization=None (they manage all orgs).
    """
    user = models.OneToOneField(DjangoUser, on_delete=models.CASCADE, related_name='org_user')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='members')
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_users'

    def __str__(self):
        org_name = self.organization.name if self.organization else 'All Organizations'
        return f"{self.user.username} - {org_name} ({self.role.get_name_display()})"
    
    @property
    def is_super_admin(self):
        return self.role.name == Role.ROLE_SUPER_ADMIN
    
    @property
    def is_client_admin(self):
        return self.role.name == Role.ROLE_CLIENT_ADMIN
    
    def has_permission(self, permission_name):
        return getattr(self.role, permission_name, False)


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
    """Contact/User model - represents a WhatsApp contact."""
    id = models.AutoField(primary_key=True)
    # Legacy field - kept for backward compatibility during migration
    admin_id = models.ForeignKey(Admin, on_delete=models.DO_NOTHING, db_column='admin_id', null=True, blank=True)
    # New organization field for multi-tenant support
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='contacts',
        db_column='organization_id'
    )
    name = models.CharField(max_length=100)
    phone_no = models.CharField(max_length=20)
    created_at = models.DateTimeField()
    is_escalation = models.BooleanField(default=False)
    followup_count = models.IntegerField(default=0)  # Track follow-up attempts (max 3)
    source = models.CharField(max_length=50, default='Whatsapp')

    class Meta:
        db_table = 'users'

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
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True, related_name='tags')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='tags')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, help_text="Description for the AI explaining when to apply this tag")
    # Manual Rule Mode (Macros) - keyword-based auto-tagging
    keyword = models.CharField(max_length=100, blank=True, null=True, help_text="Keyword that triggers this tag when user types it (e.g., 'STOP')")
    auto_apply = models.BooleanField(default=False, help_text="If True, tag is auto-applied when keyword matches user input")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        db_table = 'tags'
        # Note: unique_together with nullable fields needs careful handling
        # Django allows multiple NULL values in unique_together



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
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    admin = models.ForeignKey('Admin', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'chatgpt_prompts'

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
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='external_apis')
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
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100, help_text="Unique name to reference this image (e.g., menu_card)")
    description = models.TextField(blank=True, help_text="Description for the AI explaining when to use this image")
    image = models.ImageField(upload_to='image_assets/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.organization:
            return f"{self.name} ({self.organization.name})"
        return f"{self.name} ({self.admin.assistant_name if self.admin else 'No Admin'})"

    class Meta:
        db_table = 'image_assets'


class FollowUpMessage(models.Model):
    """
    Multi-step follow-up messages configuration.
    Each admin can have up to 4 follow-up steps that are sent sequentially.
    """
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, related_name='followup_messages')
    step = models.IntegerField(help_text="Step number (1-4)")
    delay_minutes = models.IntegerField(default=10, help_text="Delay in minutes before sending this follow-up")
    message = models.TextField(help_text="The follow-up message content")
    tag = models.ForeignKey('Tag', on_delete=models.SET_NULL, null=True, blank=True, help_text="Only send to users with this tag (optional)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Step {self.step} - {self.delay_minutes}min ({self.admin.assistant_name if self.admin else 'No Admin'})"

    class Meta:
        db_table = 'followup_messages'
        unique_together = ('admin', 'step')
        ordering = ['step']



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
