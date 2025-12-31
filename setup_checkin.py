import os
import django
import json

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from newapp.models import ExternalAPI, Admin, ChatGPTPrompt

def setup():
    # 1. Get Admin (assuming first admin is the target)
    admin = Admin.objects.first()
    if not admin:
        print("Error: No Admin found. Please create an admin user first.")
        return

    print(f"Configuring for Admin: {getattr(admin, 'email', 'Unknown')}")

    # 2. Define System Prompt for Timurbay Check-in (Strictly matching User's Analysis Prompt)
    timurbay_prompt = """
You are the AI Check-in Assistant for "Timurbay Seafront Residence & Suites".

### STEP 1: BOOKING VERIFICATION (Vision Analysis)
When the user uploads a booking slip (Image/PDF), you must analyze it using the following strict rules:

**Your task is to verify and extract booking details only if the slip belongs to "Timurbay Seafront Residences".**

**Verification Rules:**
*   If the booking slip is NOT for "Timurbay Seafront Residences", or the name is missing or unclear, DO NOT call the tool. Instead, reply: "no".
*   If it is valid, extract the details below and **CALL THE TOOL `process_booking_slip`** with the extracted values.

**Fields to Extract (Arguments for the tool):**
- platform_name
- hotel_name
- address
- phone
- booking_reference
- confirmation_number
- pin_number
- guest_name
- check_in_date
- check_in_time
- check_out_date
- check_out_time
- number_of_rooms
- number_of_nights
- number_of_guests
- room_type
- room_info
- meals_included
- occupancy_limit
- price_paid_online
- tax_amount
- extra_charges_due
- extra_charge_description
- total_amount
- currency
- cancellation_policy
- booking_status
- contact_info
- notes
- verified ("yes" if valid)

### STEP 2: FLOW CONTINUATION
After calling the tool, if the API returns success, proceed to:
1.  Ask specifically for the **Guest Details** (Name, IC, Car Plate, etc.) required for registration.
2.  Explain the payments (Refundable Deposit RM100, etc.).

### RULES
*   **Do NOT output raw JSON text.** You must use the `process_booking_slip` function to submit the data.
*   Keep text exactly as written in the slip.
*   If a field is missing, send empty string "".
    """

    # Update or Create Prompt
    prompt_obj = ChatGPTPrompt.objects.last()
    if not prompt_obj:
        prompt_obj = ChatGPTPrompt.objects.create(prompt_text=timurbay_prompt)
    else:
        prompt_obj.prompt_text = timurbay_prompt
        prompt_obj.save()
    
    print("✅ System Prompt Updated.")

    # 3. Define External Tools
    # Mapping to the User's provided API: https://speedbots.io/booking_api.php
    
    tools = [
        {
            "name": "process_booking_slip",
            "description": "Submits extracted booking slip details to the backend system. Call this ONLY if 'verified' is 'yes'.",
            "url": "https://speedbots.io/booking_api.php",
            "method": "POST",
            "payload": {
                "platform_name": "{{platform_name}}",
                "hotel_name": "{{hotel_name}}",
                "address": "{{address}}",
                "phone": "{{phone}}",
                "booking_reference": "{{booking_reference}}",
                "confirmation_number": "{{confirmation_number}}",
                "pin_number": "{{pin_number}}",
                "guest_name": "{{guest_name}}",
                "check_in_date": "{{check_in_date}}",
                "check_in_time": "{{check_in_time}}",
                "check_out_date": "{{check_out_date}}",
                "check_out_time": "{{check_out_time}}",
                "number_of_rooms": "{{number_of_rooms}}",
                "number_of_nights": "{{number_of_nights}}",
                "number_of_guests": "{{number_of_guests}}",
                "room_type": "{{room_type}}",
                "room_info": "{{room_info}}",
                "meals_included": "{{meals_included}}",
                "occupancy_limit": "{{occupancy_limit}}",
                "price_paid_online": "{{price_paid_online}}",
                "tax_amount": "{{tax_amount}}",
                "extra_charges_due": "{{extra_charges_due}}",
                "extra_charge_description": "{{extra_charge_description}}",
                "total_amount": "{{total_amount}}",
                "currency": "{{currency}}",
                "cancellation_policy": "{{cancellation_policy}}",
                "booking_status": "{{booking_status}}",
                "contact_info": "{{contact_info}}",
                "notes": "{{notes}}",
                "verified": "{{verified}}"
            }
        },
        {
            "name": "register_guest",
            "description": "Registers the guest details (Step 3).",
            "url": "https://httpbin.org/anything/register_guest",
            "method": "POST",
            "payload": {
                "name": "{{name}}",
                "ic": "{{ic}}",
                "phone": "{{phone}}",
                "car_plate": "{{car_plate}}",
                "email": "{{email}}",
                "address": "{{address}}",
                "status": "registered"
            }
        }
    ]

    # Clear existing tools
    ExternalAPI.objects.filter(admin=admin).delete()

    for t in tools:
        ExternalAPI.objects.create(
            admin=admin,
            name=t["name"],
            description=t["description"],
            url=t["url"],
            method=t["method"],
            payload=t["payload"]
        )
    
    print(f"✅ {len(tools)} External Tools Configured.")
    print("Setup Complete! The bot is now ready to handle Timurbay Check-ins.")

if __name__ == "__main__":
    setup()
