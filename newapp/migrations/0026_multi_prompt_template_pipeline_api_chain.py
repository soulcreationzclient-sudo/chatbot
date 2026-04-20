# Generated migration for Features 1, 2, 3, 5

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('newapp', '0025_add_contact_id_and_booking_token'),
    ]

    operations = [
        # ==================== Feature 1: Multi-Agent Prompts ====================
        migrations.AddField(
            model_name='chatgptprompt',
            name='name',
            field=models.CharField(default='Default Prompt', help_text='Prompt name (e.g. Sales Agent, Support Agent)', max_length=100),
        ),
        migrations.AddField(
            model_name='chatgptprompt',
            name='gpt_model',
            field=models.CharField(blank=True, default='', help_text='Override GPT model for this prompt (empty = use org default)', max_length=50),
        ),
        migrations.AddField(
            model_name='chatgptprompt',
            name='is_default',
            field=models.BooleanField(default=False, help_text='If true, this prompt is used for incoming messages'),
        ),

        # ==================== Feature 2: Template Messages in Follow-ups ====================
        migrations.AddField(
            model_name='followupmessage',
            name='use_template',
            field=models.BooleanField(default=False, help_text='Use WhatsApp template instead of plain text'),
        ),
        migrations.AddField(
            model_name='followupmessage',
            name='template',
            field=models.ForeignKey(blank=True, help_text='WhatsApp template to send (when use_template=True)', null=True, on_delete=django.db.models.deletion.SET_NULL, to='newapp.whatsapptemplate'),
        ),
        migrations.AddField(
            model_name='followupmessage',
            name='template_variables',
            field=models.JSONField(blank=True, default=dict, help_text='Variable mapping for template parameters'),
        ),

        # ==================== Feature 3: Pipeline Auto-Send ====================
        migrations.AddField(
            model_name='pipelinestage',
            name='auto_send_enabled',
            field=models.BooleanField(default=False, help_text='Automatically send template when lead moves to this stage'),
        ),
        migrations.AddField(
            model_name='pipelinestage',
            name='auto_send_template',
            field=models.ForeignKey(blank=True, help_text='Template to auto-send when lead enters this stage', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pipeline_stages', to='newapp.whatsapptemplate'),
        ),
        migrations.AddField(
            model_name='pipelinestage',
            name='template_variables',
            field=models.JSONField(blank=True, default=dict, help_text='Variable mapping for template parameters'),
        ),

        # ==================== Feature 5: API Chaining ====================
        migrations.AddField(
            model_name='externalapi',
            name='depends_on',
            field=models.ForeignKey(blank=True, help_text='Run this API after the referenced API completes', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dependents', to='newapp.externalapi'),
        ),
        migrations.AddField(
            model_name='externalapi',
            name='execution_order',
            field=models.IntegerField(default=0, help_text='Order for chained execution (lower runs first)'),
        ),
    ]
