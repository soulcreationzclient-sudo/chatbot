# Generated migration for CustomField model updates

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('newapp', '0015_broadcastjob_user_archived_at_user_is_in_inbox_and_more'),
    ]

    operations = [
        # Add new fields to CustomField model
        migrations.AddField(
            model_name='customfield',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='custom_fields', to='newapp.organization'),
        ),
        migrations.AddField(
            model_name='customfield',
            name='description',
            field=models.TextField(blank=True, help_text="Description for the AI explaining when to capture this field"),
        ),
        migrations.AddField(
            model_name='customfield',
            name='is_active',
            field=models.BooleanField(default=True, help_text="Whether this field is active"),
        ),
        migrations.AddField(
            model_name='customfield',
            name='is_required',
            field=models.BooleanField(default=False, help_text="Whether this field is required"),
        ),
        migrations.AddField(
            model_name='customfield',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Add index to CustomFieldValue
        migrations.AddField(
            model_name='customfieldvalue',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        
        # Add index for performance
        migrations.AddIndex(
            model_name='customfieldvalue',
            index=models.Index(fields=['user', 'custom_field'], name='custom_field_user_idx'),
        ),
        
        # Add related_name to existing foreign keys
        migrations.AlterField(
            model_name='customfield',
            name='admin',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='custom_fields', to='newapp.admin'),
        ),
        migrations.AlterField(
            model_name='customfieldvalue',
            name='custom_field',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='newapp.customfield'),
        ),
        migrations.AlterField(
            model_name='customfieldvalue',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_field_values', to='newapp.user'),
        ),
    ]
