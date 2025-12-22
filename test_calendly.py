import requests

TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzY1NDQzMDUyLCJqdGkiOiIyMWY1YmIyMC0yNjcxLTQ5MDUtOGRiZS0xMTg3ZDRlYTkwMDMiLCJ1c2VyX3V1aWQiOiI0N2Y2OGNiMi04ODRhLTQ2ZGMtOWIzMC1hNzE1MTZhZTk0ZjIifQ.Gpuvge2TU8AUT31ssVRoVWdJ6FcmS2wehicXP-PAHYWYTpEvdHX-iiWzhn2XOx-olE7_RjPnCnLixxnapk94iw"

headers = {"Authorization": f"Bearer {TOKEN}"}

print("Testing Calendly API...")
print("=" * 50)

# Test 1: Get User
r = requests.get("https://api.calendly.com/users/me", headers=headers)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    user = r.json().get("resource", {})
    print(f"User: {user.get('name')}")
    print(f"Email: {user.get('email')}")
    user_uri = user.get("uri")
    
    # Test 2: Get Event Types
    print("\n" + "=" * 50)
    print("Event Types:")
    r2 = requests.get(f"https://api.calendly.com/event_types?user={user_uri}", headers=headers)
    for et in r2.json().get("collection", []):
        print(f"  - {et.get('name')} ({et.get('duration')} min)")
        print(f"    URL: {et.get('scheduling_url')}")
else:
    print(f"Error: {r.text}")
