import requests

TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzY1NDQzMDUyLCJqdGkiOiIyMWY1YmIyMC0yNjcxLTQ5MDUtOGRiZS0xMTg3ZDRlYTkwMDMiLCJ1c2VyX3V1aWQiOiI0N2Y2OGNiMi04ODRhLTQ2ZGMtOWIzMC1hNzE1MTZhZTk0ZjIifQ.Gpuvge2TU8AUT31ssVRoVWdJ6FcmS2wehicXP-PAHYWYTpEvdHX-iiWzhn2XOx-olE7_RjPnCnLixxnapk94iw"
WEBHOOK_URL = "https://overslight-shirley-overhearty.ngrok-free.dev/api/calendly/webhook/"

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Get org URI
print("Getting user info...")
r = requests.get("https://api.calendly.com/users/me", headers=headers)
org_uri = r.json()["resource"]["current_organization"]
print(f"Org: {org_uri}")

# Register webhook
print(f"Registering webhook: {WEBHOOK_URL}")
data = {
    "url": WEBHOOK_URL,
    "events": ["invitee.created", "invitee.canceled"],
    "organization": org_uri,
    "scope": "organization"
}
r = requests.post("https://api.calendly.com/webhook_subscriptions", headers=headers, json=data)
print(f"Status: {r.status_code}")
print(r.text)
