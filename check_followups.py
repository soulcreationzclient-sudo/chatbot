"""Check image assets and prompt for JamYou"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import ImageAsset, ChatGPTPrompt

print("=== ALL Image Assets ===")
for a in ImageAsset.objects.all():
    print(f"  ID={a.id} Name='{a.name}' Org={a.organization_id} Admin={a.admin_id} File={a.image}")

print("\n=== ChatGPT Prompts (last 500 chars of each) ===")
for p in ChatGPTPrompt.objects.all():
    # Check if prompt mentions image tags
    text = p.prompt_text
    has_image_ref = 'image:' in text.lower() or 'image_assets' in text.lower() or '{{image' in text
    print(f"\n  Prompt ID={p.id} Org={p.organization_id} Admin={p.admin_id}")
    print(f"  Has image references: {has_image_ref}")
    if has_image_ref:
        # Find the image-related section
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'image' in line.lower():
                start = max(0, i-1)
                end = min(len(lines), i+3)
                for j in range(start, end):
                    print(f"    L{j}: {lines[j][:150]}")
                print("    ---")
