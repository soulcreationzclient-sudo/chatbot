import requests
import json

url = "http://127.0.0.1:8000/get_message"

# Sample Payload mimicking a WhatsApp text message
payload = {
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "123456789",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "1234567890",
              "phone_number_id": "811624148710340" # Matches the ID in views.py line 59
            },
            "contacts": [{
              "profile": {"name": "Meet Vaghasiya"},
              "wa_id": "919327606510"
            }],
            "messages": [
              {
                "from": "919327606510",
                "id": "wamid.HBgLMTIzNDU2Nzg5MAUCABEYEjEyMzQ1Njc4OTAxMjM0NTY3AA==",
                "timestamp": "1706246820",
                "type": "text",
                "text": {
                    "body": "hi"
                }
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}

try:
    print(f"Sending POST to {url}...")
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")
except Exception as e:
    print(f"Error: {e}")
