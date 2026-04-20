"""
Migration: Add WebChat Models
Adds support for web chat functionality alongside existing WhatsApp support.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('newapp', '0017_userlog_and_more'),
    ]

    operations = [
        # Create WebChatSession model
        migrations.CreateModel(
            name='WebChatSession',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('anonymous_id', models.CharField(blank=True, help_text='Temporary ID for users not yet in the system', max_length=100, null=True)),
                ('session_id', models.CharField(help_text='Unique session identifier for the widget', max_length=100, unique=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('ended', 'Ended'), ('abandoned', 'Abandoned')], default='active', max_length=20)),
                ('language', models.CharField(choices=[('en', 'English'), ('ar', 'Arabic'), ('both', 'Both (Bilingual)')], default='en', max_length=10)),
                ('visitor_name', models.CharField(blank=True, max_length=100, null=True)),
                ('visitor_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('message_count', models.IntegerField(default=0)),
                ('admin', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='newapp.admin')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='newapp.organization')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='webchat_sessions', to='newapp.user')),
            ],
            options={
                'db_table': 'webchat_sessions',
                'ordering': ['-started_at'],
                'indexes': [
                    models.Index(fields=['session_id'], name='webchat_sess_session_idx'),
                    models.Index(fields=['status', 'last_activity'], name='webchat_sess_status_idx'),
                    models.Index(fields=['user', 'started_at'], name='webchat_sess_user_idx'),
                ],
            },
        ),
        
        # Create WebChatMessage model
        migrations.CreateModel(
            name='WebChatMessage',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('content', models.TextField(help_text='The message text')),
                ('content_type', models.CharField(choices=[('text', 'Text'), ('image', 'Image'), ('file', 'File'), ('audio', 'Audio'), ('system', 'System Message')], default='text', max_length=20)),
                ('sender', models.CharField(choices=[('user', 'User/Visitor'), ('bot', 'Bot'), ('agent', 'Live Agent')], default='user', max_length=20)),
                ('ai_response', models.TextField(blank=True, null=True)),
                ('attachment_url', models.URLField(blank=True, null=True)),
                ('attachment_name', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='newapp.webchatmessage')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='newapp.webchatsession')),
            ],
            options={
                'db_table': 'webchat_messages',
                'ordering': ['created_at'],
                'indexes': [
                    models.Index(fields=['session', 'created_at'], name='webchat_msg_session_idx'),
                    models.Index(fields=['sender', 'created_at'], name='webchat_msg_sender_idx'),
                ],
            },
        ),
        
        # Create WebChatWidget model
        migrations.CreateModel(
            name='WebChatWidget',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('name', models.CharField(help_text='Internal name for this widget', max_length=100)),
                ('website_url', models.URLField(blank=True, help_text='URL where this widget will be embedded', max_length=500, null=True)),
                ('display_mode', models.CharField(choices=[('button', 'Floating Button'), ('embedded', 'Embedded Chat'), ('popup', 'Popup Chat')], default='button', max_length=20)),
                ('theme', models.CharField(choices=[('light', 'Light'), ('dark', 'Dark'), ('custom', 'Custom Colors')], default='light', max_length=20)),
                ('primary_color', models.CharField(default='#007bff', max_length=7)),
                ('secondary_color', models.CharField(default='#6c757d', max_length=7)),
                ('text_color', models.CharField(default='#000000', max_length=7)),
                ('background_color', models.CharField(default='#ffffff', max_length=7)),
                ('position', models.CharField(choices=[('bottom-right', 'Bottom Right'), ('bottom-left', 'Bottom Left')], default='bottom-right', max_length=20)),
                ('initial_greeting', models.TextField(blank=True, null=True)),
('offline_message', models.TextField(blank=True, null=True)),
                ('welcome_en', models.TextField(default='Welcome! How can we help you today?', help_text='English welcome message')),
                ('welcome_ar', models.TextField(default='مرحبا! كيف يمكننا مساعدتك اليوم؟', help_text='Arabic welcome message')),
                ('show_language_selector', models.BooleanField(default=True)),
                ('default_language', models.CharField(default='en', max_length=10)),
                ('file_uploads_enabled', models.BooleanField(default=True)),
                ('voice_input_enabled', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('embed_code', models.TextField(blank=True, null=True)),
                ('admin', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='newapp.admin')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='newapp.organization')),
            ],
            options={
                'db_table': 'webchat_widgets',
                'unique_together': {('admin', 'name'), ('organization', 'name')},
            },
        ),
        
        # Create WebChatAnalytics model
        migrations.CreateModel(
            name='WebChatAnalytics',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('response_time_seconds', models.IntegerField(blank=True, null=True)),
                ('message_count', models.IntegerField(default=0)),
                ('session_duration_seconds', models.IntegerField(blank=True, null=True)),
                ('was_escalated', models.BooleanField(default=False)),
                ('user_feedback', models.CharField(blank=True, choices=[('positive', 'Positive'), ('neutral', 'Neutral'), ('negative', 'Negative'), ('', 'No Feedback')], default='', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics', to='newapp.webchatsession')),
            ],
            options={
                'db_table': 'webchat_analytics',
                'ordering': ['-created_at'],
            },
        ),
    ]
