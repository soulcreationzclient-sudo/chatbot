"""
Script to register Calendly webhook for booking notifications
Run this once to set up the webhook
"""
import requests

# Calendly API Token
TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzY1NDQzMDUyLCJqdGkiOiIyMWY1YmIyMC0yNjcxLTQ5MDUtOGRiZS0xMTg3ZDRlYTkwMDMiLCJ1c2VyX3V1aWQiOiI0N2Y2OGNiMi04ODRhLTQ2ZGMtOWIzMC1hNzE1MTZhZTk0ZjIifQ.Gpuvge2TU8AUT31ssVRoVWdJ6FcmS2wehicXP-PAHYWYTpEvdHX-iiWzhn2XOx-olE7_RjPnCnLixxnapk94iw"

# Your ngrok URL - UPDATE THIS before running!
WEBHOOK_URL = input("Enter your ngrok URL (e.g., https://xxx.ngrok-free.dev): ").strip()
if not WEBHOOK_URL:
    print("No URL provided, exiting.")
    exit()

WEBHOOK_URL = f"{WEBHOOK_URL}/api/calendly/webhook/"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# First, get the organization URI
print("\n1. Getting user info...")
user_resp = requests.get("https://api.calendly.com/users/me", headers=headers)
if user_resp.status_code != 200:
    print(f"Error getting user: {user_resp.text}")
    exit()

user_data = user_resp.json()["resource"]
org_uri = user_data.get("current_organization")
user_uri = user_data.get("uri")
print(f"   User: {user_data.get('name')}")
print(f"   Organization: {org_uri}")

# Check existing webhooks
print("\n2. Checking existing webhooks...")
webhooks_resp = requests.get(
    f"https://api.calendly.com/webhook_subscriptions?organization={org_uri}&scope=organization",
    headers=headers
)
if webhooks_resp.status_code == 200:
    existing = webhooks_resp.json().get("collection", [])
    for wh in existing:
        print(f"   Found: {wh.get('callback_url')}")
        if "ngrok" in wh.get('callback_url', ''):
            # Delete old ngrok webhook
            wh_uri = wh.get('uri')
            print(f"   Deleting old webhook: {wh_uri}")
            requests.delete(wh_uri, headers=headers)

# Create new webhook
print(f"\n3. Creating webhook: {WEBHOOK_URL}")
webhook_data = {
    "url": WEBHOOK_URL,
    "events": ["invitee.created", "invitee.canceled"],
    "organization": org_uri,
    "scope": "organization"
}

create_resp = requests.post(
    "https://api.calendly.com/webhook_subscriptions",
    headers=headers,
    json=webhook_data
)

if create_resp.status_code in [200, 201]:
    result = create_resp.json()
    print("\n✅ Webhook registered successfully!")
    print(f"   Callback URL: {result.get('resource', {}).get('callback_url')}")
    print(f"   Events: {result.get('resource', {}).get('events')}")
else:
    print(f"\n❌ Failed to create webhook: {create_resp.status_code}")
    print(create_resp.text)
