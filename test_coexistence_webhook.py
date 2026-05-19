"""
Test script for WhatsApp Coexistence Mode webhook handling.
Sends 3 test payloads to verify the webhook correctly dispatches:
  1. smb_message_echoes (phone-sent message echo)
  2. smb_app_state_sync (contact sync)
  3. Normal messages (existing behavior)

Usage:
  1. Start Django dev server: python manage.py runserver
  2. Run this script: python test_coexistence_webhook.py

NOTE: Requires a valid phone_number_id in the database.
      Update PHONE_NUMBER_ID below to match your setup.
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/get_message"
PHONE_NUMBER_ID = "811624148710340"  # Must match a valid admin/org in DB


def test_smb_message_echoes():
    """Test: phone-sent message echo should save as bot message."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "1234567890",
                        "phone_number_id": PHONE_NUMBER_ID
                    },
                    "message_echoes": [{
                        "from": "1234567890",
                        "to": "919327606510",
                        "id": "wamid.ECHO_TEST_001",
                        "timestamp": "1710000000",
                        "type": "text",
                        "text": {"body": "Hello from the phone app! (COEX TEST)"}
                    }]
                },
                "field": "smb_message_echoes"
            }]
        }]
    }

    print("=" * 60)
    print("TEST 1: smb_message_echoes (phone-sent text echo)")
    print("=" * 60)
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text}")
        print(f"  {'✅ PASS' if response.status_code == 200 else '❌ FAIL'}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()


def test_smb_app_state_sync():
    """Test: contact sync from phone should be logged (not crash)."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "action": "add",
                    "contact": {
                        "wa_id": "16505550123",
                        "name": "Test Contact"
                    }
                },
                "field": "smb_app_state_sync"
            }]
        }]
    }

    print("=" * 60)
    print("TEST 2: smb_app_state_sync (contact sync)")
    print("=" * 60)
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text}")
        print(f"  {'✅ PASS' if response.status_code == 200 else '❌ FAIL'}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()


def test_normal_messages():
    """Test: normal message webhook still works (no regression)."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "1234567890",
                        "phone_number_id": PHONE_NUMBER_ID
                    },
                    "contacts": [{
                        "profile": {"name": "Meet Vaghasiya"},
                        "wa_id": "919327606510"
                    }],
                    "messages": [{
                        "from": "919327606510",
                        "id": "wamid.COEX_REGRESSION_TEST",
                        "timestamp": "1710000001",
                        "type": "text",
                        "text": {"body": "hi (regression test)"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    print("=" * 60)
    print("TEST 3: Normal messages (regression check)")
    print("=" * 60)
    try:
        response = requests.post(BASE_URL, json=payload, timeout=30)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text}")
        print(f"  {'✅ PASS' if response.status_code == 200 else '❌ FAIL'}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()


if __name__ == "__main__":
    print("\n🧪 WhatsApp Coexistence Mode - Webhook Tests\n")
    test_smb_message_echoes()
    test_smb_app_state_sync()
    test_normal_messages()
    print("Done! Check Django console for [COEX_ECHO] and [COEX_SYNC] logs.")
