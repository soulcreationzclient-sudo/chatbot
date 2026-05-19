# Generated for channel prompts, interactive buttons, and social channels

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('newapp', '0027_organization_hide_logo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='instagram_page_id',
            field=models.TextField(blank=True, default='', help_text='Instagram-connected Facebook Page ID'),
        ),
        migrations.AddField(
            model_name='organization',
            name='instagram_token',
            field=models.TextField(blank=True, default='', help_text='Page Access Token for Instagram'),
        ),
        migrations.AddField(
            model_name='organization',
            name='instagram_account_id',
            field=models.TextField(blank=True, default='', help_text='Instagram Business Account ID'),
        ),
        migrations.AddField(
            model_name='organization',
            name='facebook_page_id',
            field=models.TextField(blank=True, default='', help_text='Facebook Page ID'),
        ),
        migrations.AddField(
            model_name='organization',
            name='facebook_token',
            field=models.TextField(blank=True, default='', help_text='Page Access Token for Messenger'),
        ),
        migrations.AddField(
            model_name='message',
            name='channel',
            field=models.CharField(
                choices=[
                    ('whatsapp', 'WhatsApp'),
                    ('instagram', 'Instagram'),
                    ('facebook', 'Facebook'),
                    ('webchat', 'WebChat'),
                ],
                default='whatsapp',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='chatgptprompt',
            name='channels',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Channels this prompt is active on. Empty = all channels. Options: whatsapp, instagram, facebook, webchat',
            ),
        ),
        migrations.CreateModel(
            name='ButtonGroup',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Tag name used in prompt (e.g., main_menu)', max_length=100)),
                ('description', models.TextField(blank=True, help_text='Description for the AI explaining when to show these buttons')),
                ('header_text', models.CharField(blank=True, default='', help_text='Optional header text above buttons', max_length=60)),
                ('body_text', models.TextField(default='Please choose an option:', help_text='Message body text shown with the buttons')),
                ('footer_text', models.CharField(blank=True, default='', help_text='Optional footer text below buttons', max_length=60)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('admin', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='newapp.admin')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='button_groups', to='newapp.organization')),
            ],
            options={
                'db_table': 'button_groups',
                'unique_together': {('admin', 'name'), ('organization', 'name')},
            },
        ),
        migrations.CreateModel(
            name='ButtonItem',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Button display text (max 20 chars for WhatsApp)', max_length=20)),
                ('button_type', models.CharField(choices=[('reply', 'Quick Reply'), ('url', 'URL Link')], default='reply', max_length=10)),
                ('payload', models.TextField(help_text='For reply: description fed to AI when tapped. For URL: the target URL.')),
                ('order', models.IntegerField(default=0)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='buttons', to='newapp.buttongroup')),
            ],
            options={
                'db_table': 'button_items',
                'ordering': ['order'],
            },
        ),
    ]
