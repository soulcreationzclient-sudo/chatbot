# Script to add webchat models to models.py
import os

# Read the file
with open('newapp/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Webchat models to add
webchat_models = '''

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
'''

# Append to file
new_content = content + webchat_models

# Write back
with open('newapp/models.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Successfully added webchat models to models.py')
print(f'New file length: {len(new_content)} characters')
