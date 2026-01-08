
import requests
import sys

def test_api():
    url = "http://127.0.0.1:8000/api/inbox/new_messages"
    params = {'user_id': '14', 'last_id': '0'}
    
    print(f"Testing API: {url} with params {params}")
    
    try:
        response = requests.get(url, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Content Type: {response.headers.get('Content-Type')}")
        print(f"Response Text: {response.text[:500]}") # First 500 chars
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("JSON Parsed Successfully.")
                print(f"Message Count: {len(data.get('messages', []))}")
                return True
            except Exception as e:
                print(f"JSON Parse Error: {e}")
        else:
            print("API returned non-200 status.")
            
    except Exception as e:
        print(f"Request Failed: {e}")
        
    return False

if __name__ == "__main__":
    test_api()
