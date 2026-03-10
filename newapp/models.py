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
    waba_id = models.TextField(blank=True, default='', help_text='WhatsApp Business Account ID')
    display_phone_no = models.TextField(blank=True, default='')
    
    # OpenAI Configuration
    openai_api_key = models.TextField(blank=True, null=True)
    GPT_MODEL_CHOICES = (
        ('gpt-5.2', 'GPT-5.2 (Most Powerful)'),
        ('gpt-5', 'GPT-5 (Advanced)'),
        ('gpt-5-mini', 'GPT-5 Mini (Fast & Smart)'),
        ('gpt-5-nano', 'GPT-5 Nano (Fastest & Cheapest)'),
        ('o3-mini', 'o3-mini (Reasoning)'),
        ('gpt-4.1', 'GPT-4.1 (Reliable)'),
        ('gpt-4.1-mini', 'GPT-4.1 Mini (Affordable)'),
        ('gpt-4.1-nano', 'GPT-4.1 Nano (Ultra Fast)'),
        ('gpt-4o-mini', 'GPT-4o Mini (Legacy)'),
        ('gpt-4-turbo', 'GPT-4 Turbo (Legacy)'),
    )
    gpt_model = models.CharField(max_length=50, default='gpt-4o-mini')
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

    # Organization Logo (shown in topbar)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True, help_text="Custom logo for the topbar")
    # Feature Flag / Canary Deployment
    is_beta_tester = models.BooleanField(
        default=False,
        help_text="If True, this org sees new features before general rollout"
    )
    APP_VERSION_CHOICES = (
        ('stable', 'Stable'),
        ('beta', 'Beta'),
        ('canary', 'Canary'),
    )
    app_version = models.CharField(
        max_length=20,
        choices=APP_VERSION_CHOICES,
        default='stable',
        help_text="Which version of features this org uses"
    )

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
    # Per-user bot toggle: when False, bot won't auto-reply and follow-ups are paused
    bot_enabled = models.BooleanField(default=True)
    # Soft-delete for inbox: When False, contact is archived from inbox but still visible in All Contacts
    is_in_inbox = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['organization_id']),
            models.Index(fields=['admin_id']),
            models.Index(fields=['is_in_inbox']),
            models.Index(fields=['phone_no']),
            models.Index(fields=['created_at']),
        ]



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
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user_id']),
        ]


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
        indexes = [
            models.Index(fields=['keyword']),
            models.Index(fields=['organization_id']),
            models.Index(fields=['admin_id']),
        ]



class UserTag(models.Model):
    id = models.AutoField(primary_key=True)
    # user = models.ForeignKey('newapp.User', on_delete=models.CASCADE, db_column='user_id')
    # tag = models.ForeignKey('newapp.Tag', on_delete=models.CASCADE, db_column='tag_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, db_column='tag_id')

    class Meta:
        db_table = 'user_tags'  # New table for user-tag relationships
        unique_together = ('user', 'tag')  # prevent duplicate mappings



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
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100, default='Default Agent', help_text="Agent name (e.g. Sales Agent, Support Agent)")
    pdf_file = models.FileField(upload_to='ai_agent_pdfs/')  # PDFs will be uploaded to MEDIA_ROOT/ai_agent_pdfs/
    instruction = models.TextField(blank=True)
    pdf_text = models.TextField(blank=True, null=True)               
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="If true, this agent is used for incoming messages")
    uploaded_at = models.DateTimeField(auto_now_add=True)    

    class Meta:
        db_table = 'ai_agent_config'
        
    def __str__(self):
        default_label = " ⭐ DEFAULT" if self.is_default else ""
        return f"AI Agent: {self.name}{default_label}"  
    
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


class CalendlyLink(models.Model):
    """
    Named Calendly booking links that can be referenced in AI prompts
    using the {{calendly:link_name}} tag syntax.
    """
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='calendly_links')
    name = models.CharField(max_length=100, help_text="Tag name used in prompt (e.g., quick_call)")
    description = models.TextField(blank=True, help_text="Description (e.g., 30 minute consultation)")
    url = models.URLField(max_length=500, help_text="Calendly scheduling URL")
    custom_field_name = models.CharField(max_length=100, blank=True, default='', help_text="Custom field to update when booking is confirmed (e.g., appointment_status)")
    booking_message = models.TextField(blank=True, default='', help_text="Custom message to send when booking is confirmed")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} → {self.url}"

    class Meta:
        db_table = 'calendly_links'


class CalendlyBookingTracker(models.Model):
    """
    Tracks which Calendly link was sent to which WhatsApp user.
    This allows the Calendly webhook to match a booking back to the
    correct WhatsApp contact (since Calendly only provides email/name).
    """
    STATUS_CHOICES = [
        ('link_sent', 'Link Sent'),
        ('booked', 'Booked'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendly_bookings')
    calendly_link = models.ForeignKey(CalendlyLink, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='link_sent')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.phone_no} → {self.calendly_link.name} ({self.status})"

    class Meta:
        db_table = 'calendly_booking_tracker'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['calendly_link', 'status']),
        ]


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
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('textarea', 'Long Text'),
        ('number', 'Number'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
        ('boolean', 'Yes/No'),
        ('select', 'Dropdown'),
    ]
    
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True, related_name='custom_fields')
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True, related_name='custom_fields')
    name = models.CharField(max_length=100, help_text="Field name (e.g., name, email, address)")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text', help_text="Data type for this field")
    description = models.TextField(blank=True, help_text="Description for the AI explaining when to capture this field")
    is_required = models.BooleanField(default=False, help_text="Whether this field is required")
    is_active = models.BooleanField(default=True, help_text="Whether this field is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.organization:
            return f"{self.name} ({self.organization.name})"
        return f"{self.name} ({self.admin.assistant_name if self.admin else 'No Admin'})"

    class Meta:
        db_table = 'custom_fields'
        unique_together = [('admin', 'name'), ('organization', 'name')]

class CustomFieldValue(models.Model):
    id = models.AutoField(primary_key=True)
    custom_field = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name='values')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_field_values')
    value = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.custom_field.name}: {self.value} ({self.user.phone_no})"

    class Meta:
        db_table = 'custom_field_values'
        unique_together = ('custom_field', 'user')
        indexes = [
            models.Index(fields=['user', 'custom_field']),
        ]




class UserLog(models.Model):
    """
    Track user-related logs for the inbox right panel.
    Includes message send failures, API errors, custom field updates, window closed events, etc.
    """
    LOG_TYPE_CHOICES = [
        ('message_failed', 'Message Failed'),
        ('api_error', 'API Error'),
        ('custom_field_update', 'Custom Field Update'),
        ('window_closed', 'Window Closed'),
        ('bot_toggle', 'Bot Toggle'),
        ('tag_update', 'Tag Update'),
        ('system', 'System'),
    ]

    LOG_LEVEL_CHOICES = [
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
        ('success', 'Success'),
    ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logs')
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True, related_name='user_logs')
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True, related_name='user_logs')
    log_type = models.CharField(max_length=50, choices=LOG_TYPE_CHOICES, default='info')
    level = models.CharField(max_length=20, choices=LOG_LEVEL_CHOICES, default='info')
    message = models.TextField(help_text="The log message/details")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional JSON metadata")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.user.phone_no} - {self.log_type}: {self.message[:50]}"

    class Meta:
        db_table = 'user_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['log_type', 'created_at']),
        ]

# ==================== BROADCAST SYSTEM MODELS ====================

class WhatsAppTemplate(models.Model):
    """
    Synced templates from Meta WhatsApp Business API.
    Only APPROVED templates can be used for broadcasting.
    """
    STATUS_CHOICES = [
        ('APPROVED', 'Approved'),
        ('PENDING', 'Pending'),
        ('REJECTED', 'Rejected'),
    ]
    CATEGORY_CHOICES = [
        ('MARKETING', 'Marketing'),
        ('UTILITY', 'Utility'),
        ('AUTHENTICATION', 'Authentication'),
    ]
    
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    template_id = models.CharField(max_length=100, help_text="Meta's template ID")
    name = models.CharField(max_length=100)
    language = models.CharField(max_length=10, default='en_US')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='MARKETING')
    components = models.JSONField(default=list, help_text="Template components (header, body, buttons)")
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.status})"

    class Meta:
        db_table = 'whatsapp_templates'
        unique_together = ('admin', 'organization', 'template_id')


class BroadcastJob(models.Model):
    """
    A broadcast campaign to send a template message to multiple contacts.
    Uses rate-limiting to comply with Meta's throughput limits.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    template = models.ForeignKey(WhatsAppTemplate, on_delete=models.PROTECT)
    tag = models.ForeignKey(Tag, on_delete=models.SET_NULL, null=True, blank=True, help_text="Send to users with this tag")
    name = models.CharField(max_length=200, blank=True, help_text="Optional campaign name")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    template_variables = models.JSONField(default=dict, blank=True, help_text="Variables for template placeholders")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Broadcast {self.id}: {self.template.name} ({self.status})"

    class Meta:
        db_table = 'broadcast_jobs'
        ordering = ['-created_at']


class BroadcastMessage(models.Model):
    """
    Track individual message status within a broadcast job.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ]
    
    id = models.AutoField(primary_key=True)
    broadcast_job = models.ForeignKey(BroadcastJob, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    meta_message_id = models.CharField(max_length=100, blank=True, help_text="Message ID from Meta API")
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Msg to {self.user.phone_no}: {self.status}"

    class Meta:
        db_table = 'broadcast_messages'
        indexes = [
            models.Index(fields=['broadcast_job', 'status']),
        ]


# ==================== FOLLOW-UP SCHEDULING MODEL ====================

class ScheduledFollowUp(models.Model):
    """
    Persistent follow-up scheduling - checked by periodic Celery Beat task.
    Replaces in-memory countdown-based scheduling for reliability.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),  # Locked for sending
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),  # User replied before follow-up
        ('failed', 'Failed'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scheduled_followups')
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True, blank=True)
    step = models.IntegerField(default=1, help_text="Follow-up step (1-4)")
    scheduled_for = models.DateTimeField(db_index=True, help_text="When to send this follow-up")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(help_text="The follow-up message content")
    attempts = models.IntegerField(default=0, help_text="Number of send attempts")
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"FollowUp Step {self.step} for {self.user.phone_no}: {self.status}"

    class Meta:
        db_table = 'scheduled_followups'
        ordering = ['scheduled_for']
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
        ]


# ==================== WEBCHAT MODELS ====================

class WebChatSession(models.Model):
    """
    Manages web chat sessions.
    Each session represents a single conversation on a website.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('abandoned', 'Abandoned'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ar', 'Arabic'),
        ('both', 'Both (Bilingual)'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='webchat_sessions',
        null=True,
        blank=True
    )
    anonymous_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Temporary ID for users not yet in the system"
    )
    session_id = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Unique session identifier for the widget"
    )
    
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey(
        'Organization', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    
    visitor_name = models.CharField(max_length=100, blank=True, null=True)
    visitor_email = models.EmailField(blank=True, null=True)
    
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    message_count = models.IntegerField(default=0)
    
    def __str__(self):
        if self.visitor_name:
            return f"Session {self.session_id} - {self.visitor_name}"
        elif self.user:
            return f"Session {self.session_id} - {self.user.name}"
        return f"Session {self.session_id} (Anonymous)"

    class Meta:
        db_table = 'webchat_sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['status', 'last_activity']),
            models.Index(fields=['user', 'started_at']),
        ]


class WebChatMessage(models.Model):
    """
    Stores individual messages in a web chat session.
    """
    SENDER_CHOICES = [
        ('user', 'User/Visitor'),
        ('bot', 'Bot'),
        ('agent', 'Live Agent'),
    ]
    
    CONTENT_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('system', 'System Message'),
    ]
    
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        WebChatSession, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    
    content = models.TextField(help_text="The message text")
    content_type = models.CharField(
        max_length=20, 
        choices=CONTENT_TYPE_CHOICES, 
        default='text'
    )
    
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES, default='user')
    ai_response = models.TextField(blank=True, null=True)
    
    attachment_url = models.URLField(blank=True, null=True)
    attachment_name = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='replies'
    )
    
    def __str__(self):
        preview = self.content[:30] + '...' if len(self.content) > 30 else self.content
        return f"Msg in {self.session.session_id}: {preview}"

    class Meta:
        db_table = 'webchat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
        ]


class WebChatWidget(models.Model):
    """
    Configuration for the web chat widget.
    Each organization can have multiple widgets for different websites.
    """
    DISPLAY_CHOICES = [
        ('button', 'Floating Button'),
        ('embedded', 'Embedded Chat'),
        ('popup', 'Popup Chat'),
    ]
    
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('custom', 'Custom Colors'),
    ]
    
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, null=True, blank=True)
    organization = models.ForeignKey(
        'Organization', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    name = models.CharField(
        max_length=100, 
        help_text="Internal name for this widget"
    )
    website_url = models.URLField(
        max_length=500, 
blank=True, 
        null=True,
        help_text="URL where this widget will be embedded"
    )
    
    display_mode = models.CharField(
        max_length=20, 
        choices=DISPLAY_CHOICES, 
        default='button'
    )
    theme = models.CharField(
        max_length=20, 
        choices=THEME_CHOICES, 
        default='light'
    )
    
    primary_color = models.CharField(max_length=7, default='#007bff')
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    text_color = models.CharField(max_length=7, default='#000000')
    background_color = models.CharField(max_length=7, default='#ffffff')
    
    position = models.CharField(
        max_length=20, 
        choices=[('bottom-right', 'Bottom Right'), ('bottom-left', 'Bottom Left')],
        default='bottom-right'
    )
    
    initial_greeting = models.TextField(blank=True, null=True)
    offline_message = models.TextField(blank=True, null=True)
    
    welcome_en = models.TextField(
        default="Welcome! How can we help you today?",
        help_text="English welcome message"
    )
    welcome_ar = models.TextField(
        default="مرحبا! كيف يمكننا مساعدتك اليوم؟",
        help_text="Arabic welcome message"
    )
    
    show_language_selector = models.BooleanField(default=True)
    default_language = models.CharField(max_length=10, default='en')
    
    file_uploads_enabled = models.BooleanField(default=True)
    voice_input_enabled = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    embed_code = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} ({self.admin.assistant_name if self.admin else self.organization.name if self.organization else 'No Org'})"

    class Meta:
        db_table = 'webchat_widgets'
        unique_together = [('admin', 'name'), ('organization', 'name')]


class WebChatAnalytics(models.Model):
    """
    Track analytics and metrics for web chat.
    """
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        WebChatSession, 
        on_delete=models.CASCADE, 
        related_name='analytics'
    )
    
    response_time_seconds = models.IntegerField(null=True, blank=True)
    message_count = models.IntegerField(default=0)
    session_duration_seconds = models.IntegerField(null=True, blank=True)
    
    was_escalated = models.BooleanField(default=False)
    user_feedback = models.CharField(
        max_length=20, 
        choices=[
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
            ('', 'No Feedback'),
        ],
        blank=True,
        default=''
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Analytics for {self.session.session_id}"

    class Meta:
        db_table = 'webchat_analytics'
        ordering = ['-created_at']


# ==================== PIPELINE CRM MODELS ====================

class Pipeline(models.Model):
    """Multiple pipelines per organization (e.g., 'Sales Leads', 'Support Tickets')."""
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='pipelines')
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pipelines'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class PipelineStage(models.Model):
    """Columns in the Kanban board."""
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=0)
    color = models.CharField(max_length=7, default='#3b82f6', help_text="Hex color for column header")

    class Meta:
        db_table = 'pipeline_stages'
        ordering = ['order']

    def __str__(self):
        return f"{self.pipeline.name} → {self.name}"


class Opportunity(models.Model):
    """Contact cards on the Kanban board."""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('abandoned', 'Abandoned'),
    ]

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='opportunities')
    stage = models.ForeignKey(PipelineStage, on_delete=models.CASCADE, related_name='opportunities')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='opportunities', null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='opportunities')
    title = models.CharField(max_length=200, blank=True, default='')
    opportunity_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    description = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    created_by = models.CharField(max_length=100, default='Manual')
    moved_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'opportunities'
        ordering = ['-created_at']

    def __str__(self):
        name = self.user.name if self.user and self.user.name else self.title or f"Opp #{self.id}"
        return f"{name} - {self.stage.name}"


class OpportunityComment(models.Model):
    """Comments on an opportunity."""
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=100, default='Admin')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'opportunity_comments'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on {self.opportunity} by {self.author}"


class PipelineAutomation(models.Model):
    """Automation rules: when trigger fires, move opportunity to target stage."""
    TRIGGER_CHOICES = [
        ('tag_applied', 'When tag is applied'),
        ('tag_removed', 'When tag is removed'),
        ('custom_field_changed', 'When custom field value changes'),
    ]

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='automations')
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    # For tag triggers
    trigger_tag = models.ForeignKey('Tag', on_delete=models.CASCADE, null=True, blank=True,
                                     help_text="Tag that triggers the automation")
    # For custom field triggers
    trigger_field_name = models.CharField(max_length=100, blank=True, default='',
                                           help_text="Custom field name to watch")
    trigger_field_value = models.CharField(max_length=200, blank=True, default='',
                                            help_text="Value that triggers the move (empty = any change)")
    # Target
    target_stage = models.ForeignKey(PipelineStage, on_delete=models.CASCADE,
                                      help_text="Move opportunity to this stage")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pipeline_automations'

    def __str__(self):
        return f"{self.get_trigger_type_display()} → {self.target_stage.name}"

