"""
Management command to set up the CNB Carpets Sales Pipeline.
Creates 7 stages and 7 automation rules.

Usage: python manage.py setup_cnb_pipeline
"""
from django.core.management.base import BaseCommand
from newapp.models import (
    Pipeline, PipelineStage, PipelineAutomation,
    Organization, Tag, CustomField
)


class Command(BaseCommand):
    help = 'Set up CNB Carpets Sales Pipeline with stages and automation rules'

    def handle(self, *args, **options):
        # Find the CNB Carpets organization
        org = Organization.objects.filter(name__icontains='CNB').first()
        if not org:
            # List all orgs so user can identify the right one
            all_orgs = Organization.objects.all().values_list('id', 'name')
            self.stderr.write(f"No org with 'CNB' in name. Available orgs: {list(all_orgs)}")
            return

        self.stdout.write(f"Found org: {org.name} (ID: {org.id})")

        # --- Step 1: Get or create the pipeline ---
        pipeline = Pipeline.objects.filter(organization=org).first()
        if pipeline:
            old_name = pipeline.name
            pipeline.name = 'CNB Sales Pipeline'
            pipeline.save()
            self.stdout.write(f"Renamed pipeline '{old_name}' → 'CNB Sales Pipeline'")
        else:
            pipeline = Pipeline.objects.create(
                organization=org,
                name='CNB Sales Pipeline'
            )
            self.stdout.write("Created pipeline: CNB Sales Pipeline")

        # --- Step 2: Delete existing default stages ---
        existing_stages = PipelineStage.objects.filter(pipeline=pipeline)
        if existing_stages.exists():
            count = existing_stages.count()
            existing_stages.delete()
            self.stdout.write(f"Deleted {count} existing default stages")

        # --- Step 3: Create 7 stages ---
        stages_config = [
            ('New Lead',            '#7c3aed', 0),
            ('Product Selection',   '#6366f1', 1),
            ('Customer Profiling',  '#3b82f6', 2),
            ('Budget & Estimate',   '#0ea5e9', 3),
            ('Billing & Quotation', '#14b8a6', 4),
            ('Closed — Won',        '#22c55e', 5),
            ('Closed — Lost',       '#ef4444', 6),
        ]

        created_stages = {}
        for name, color, order in stages_config:
            stage = PipelineStage.objects.create(
                pipeline=pipeline,
                name=name,
                color=color,
                order=order
            )
            created_stages[name] = stage
            self.stdout.write(f"  ✅ Stage {order + 1}: {name}")

        # --- Step 4: Create missing tags ---
        for tag_name in ['Lost', 'Completed']:
            tag, created = Tag.objects.get_or_create(
                name=tag_name,
                organization=org,
                defaults={'keyword': tag_name.lower()}
            )
            if created:
                self.stdout.write(f"  ✅ Created tag: {tag_name}")
            else:
                self.stdout.write(f"  ⏭️  Tag already exists: {tag_name}")

        # --- Step 5: Delete existing automation rules for this pipeline ---
        old_autos = PipelineAutomation.objects.filter(pipeline=pipeline)
        if old_autos.exists():
            count = old_autos.count()
            old_autos.delete()
            self.stdout.write(f"Deleted {count} existing automation rules")

        # --- Step 6: Create 7 automation rules ---
        self.stdout.write("\nCreating automation rules...")

        # Helper to find tag by name
        def get_tag(name):
            return Tag.objects.filter(name=name, organization=org).first()

        # Rule 1: Tag "New_Lead" → Add to "New Lead" stage
        tag = get_tag('New_Lead')
        if tag:
            PipelineAutomation.objects.create(
                pipeline=pipeline,
                trigger_type='tag_applied',
                trigger_tag=tag,
                target_stage=created_stages['New Lead'],
                is_active=True,
            )
            self.stdout.write("  ✅ Rule 1: Tag 'New_Lead' applied → New Lead")
        else:
            self.stderr.write("  ⚠️  Tag 'New_Lead' not found — Rule 1 skipped (will be created by bot on first use)")

        # Rule 2: Custom field "Product_Category" changed → Product Selection
        PipelineAutomation.objects.create(
            pipeline=pipeline,
            trigger_type='custom_field_changed',
            trigger_field_name='Product_Category',
            trigger_field_value='',  # any value
            target_stage=created_stages['Product Selection'],
            is_active=True,
        )
        self.stdout.write("  ✅ Rule 2: Product_Category changed → Product Selection")

        # Rule 3: Custom field "Customer_Type" changed → Customer Profiling
        PipelineAutomation.objects.create(
            pipeline=pipeline,
            trigger_type='custom_field_changed',
            trigger_field_name='Customer_Type',
            trigger_field_value='',  # any value
            target_stage=created_stages['Customer Profiling'],
            is_active=True,
        )
        self.stdout.write("  ✅ Rule 3: Customer_Type changed → Customer Profiling")

        # Rule 4: Custom field "Service_Type" changed → Budget & Estimate
        PipelineAutomation.objects.create(
            pipeline=pipeline,
            trigger_type='custom_field_changed',
            trigger_field_name='Service_Type',
            trigger_field_value='',  # any value
            target_stage=created_stages['Budget & Estimate'],
            is_active=True,
        )
        self.stdout.write("  ✅ Rule 4: Service_Type changed → Budget & Estimate")

        # Rule 5: Tag "Data_Collection_Started" → Billing & Quotation
        tag = get_tag('Data_Collection_Started')
        if tag:
            PipelineAutomation.objects.create(
                pipeline=pipeline,
                trigger_type='tag_applied',
                trigger_tag=tag,
                target_stage=created_stages['Billing & Quotation'],
                is_active=True,
            )
            self.stdout.write("  ✅ Rule 5: Tag 'Data_Collection_Started' → Billing & Quotation")
        else:
            self.stderr.write("  ⚠️  Tag 'Data_Collection_Started' not found — Rule 5 skipped")

        # Rule 6: Tag "Completed" → Closed — Won
        tag = get_tag('Completed')
        if tag:
            PipelineAutomation.objects.create(
                pipeline=pipeline,
                trigger_type='tag_applied',
                trigger_tag=tag,
                target_stage=created_stages['Closed — Won'],
                is_active=True,
            )
            self.stdout.write("  ✅ Rule 6: Tag 'Completed' → Closed — Won")
        else:
            self.stderr.write("  ⚠️  Tag 'Completed' not found — Rule 6 skipped")

        # Rule 7: Tag "Lost" → Closed — Lost
        tag = get_tag('Lost')
        if tag:
            PipelineAutomation.objects.create(
                pipeline=pipeline,
                trigger_type='tag_applied',
                trigger_tag=tag,
                target_stage=created_stages['Closed — Lost'],
                is_active=True,
            )
            self.stdout.write("  ✅ Rule 7: Tag 'Lost' → Closed — Lost")
        else:
            self.stderr.write("  ⚠️  Tag 'Lost' not found — Rule 7 skipped")

        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 CNB Sales Pipeline setup complete! "
            f"7 stages + automation rules created for org '{org.name}'."
        ))
