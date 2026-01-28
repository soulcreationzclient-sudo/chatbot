
"""
Action Tag Processor for WhatsApp Messages

This module handles the processing of action tags in AI responses, 
allowing the chatbot to perform backend actions triggered by the prompt.

Supported Tags:
1. {{tag:add:tag_name}}    - Adds a tag to the user
2. {{tag:remove:tag_name}} - Removes a tag from the user
3. {{api:tool_name}}       - Executes a defined ExternalAPI tool

Usage in AI prompts:
    "I've marked you as a VIP. {{tag:add:vip}}"
    "Checking your invoice status... {{api:fetch_invoice}}"
    
The processor will:
1. Parse the tags from the response
2. Execute the corresponding actions (using logic.py)
3. Return the results and the cleaned text
"""

import re
import json
from . import logic

def parse_action_tags(text):
    """
    Extract all action tags from text.
    
    Returns:
        List of dicts: [{'type': 'tag_add', 'name': 'vip', 'full_tag': '{{tag:add:vip}}'}, ...]
    """
    actions = []
    
    # 1. Tag Add: {{tag:add:name}}
    tag_add_matches = re.finditer(r'\{\{tag:add:([a-zA-Z0-9_\-\s]+)\}\}', text)
    for match in tag_add_matches:
        actions.append({
            'type': 'tag_add',
            'name': match.group(1).strip(),
            'full_tag': match.group(0)
        })
        
    # 2. Tag Remove: {{tag:remove:name}}
    tag_remove_matches = re.finditer(r'\{\{tag:remove:([a-zA-Z0-9_\-\s]+)\}\}', text)
    for match in tag_remove_matches:
        actions.append({
            'type': 'tag_remove',
            'name': match.group(1).strip(),
            'full_tag': match.group(0)
        })
        
    # 3. API Call: {{api:name}}
    # Matches {{api:name}} or {{api:name:args}} (args support for future, regex keeps it simple for now)
    api_matches = re.finditer(r'\{\{api:([a-zA-Z0-9_]+)\}\}', text)
    for match in api_matches:
        actions.append({
            'type': 'api_call',
            'name': match.group(1).strip(),
            'full_tag': match.group(0)
        })
        
    return actions


def process_response_actions(text, admin, phone, organization=None):
    """
    Process an AI response, extracting and executing action tags.
    
    Args:
        text (str): The full AI response text
        admin (Admin): The Admin model instance
        phone (str): User's phone number
        
    Returns:
        dict with:
            - 'original_text': str
            - 'final_text': str - Text with tags removed
            - 'actions_executed': list of results
            - 'api_responses': list of text responses from APIs (to be appended/sent)
    """
    result = {
        'original_text': text,
        'final_text': text,
        'actions_executed': [],
        'api_responses': []
    }
    
    # Set context for logic functions
    logic.set_current_context(phone, admin, organization)
    
    actions = parse_action_tags(text)
    
    if not actions:
        return result
        
    print(f"[ActionTag] Found {len(actions)} action(s) in response")
    
    # Sort actions by their position in text to process in order? 
    # Actually regex finditer yields in order.
    
    replacement_text = text
    
    for action in actions:
        tag = action['full_tag']
        action_type = action['type']
        name = action['name']
        
        # Remove tag from text
        replacement_text = replacement_text.replace(tag, "").strip()
        
        outcome = ""
        
        try:
            if action_type == 'tag_add':
                outcome = logic.apply_user_tag(name, admin, phone)
                
            elif action_type == 'tag_remove':
                outcome = logic.remove_user_tag(name, admin, phone)
                
            elif action_type == 'api_call':
                # Execute API
                # Pass phone/name as context args if needed by substitution
                # logic.execute_tool uses `arguments` to substitute properties
                # We'll provide standard context variables
                context_args = {
                    "phone": phone,
                    "phone_no": phone
                    # "name": user.name # We'd need to fetch user object to get name, logic.py does that internally
                }
                
                api_response = logic.execute_tool(name, context_args, admin)
                
                # For API calls, we might want to return the result text to the user?
                # The user request said: "so whenever some one wants to ... external api ... they just mention this type"
                # It usually implies the bot should 'see' the result or the user should see it.
                # If the bot outputs {{api:chk_bal}}, it likely expects the system to fetch balance.
                # If we just suppress the tag, the user sees nothing.
                # We should probably append the API result to the message or send it as a follow-up.
                # Let's append meaningful text results.
                
                outcome = f"API '{name}' executed."
                
                # Check if response looks like JSON or plain text
                try:
                    json_res = json.loads(api_response)
                    # If it's a simple dict/list, dump it. If complex, maybe just success?
                    # For now, let's treat the api response as text to show the user.
                    # Or maybe the prompt was "Check balance {{api:bal}}". 
                    # If we remove tag, it becomes "Check balance ". 
                    # Then we append "Balance is $10".
                    
                    # If the API reponse is a JSON string, we might want to format it?
                    # Let's just store the string raw for now.
                    if isinstance(json_res, dict) and 'text' in json_res:
                         # Common pattern: API returns {"text": "..."}
                         result['api_responses'].append(json_res['text'])
                    else:
                         result['api_responses'].append(str(json_res))
                         
                except ValueError:
                    # Not JSON, plain text
                    result['api_responses'].append(api_response)
                    
        except Exception as e:
            outcome = f"Error processing {tag}: {str(e)}"
            print(f"[ActionTag] {outcome}")
            
        result['actions_executed'].append({
            'tag': tag,
            'result': outcome
        })
        
    # Clean up whitespace
    replacement_text = re.sub(r'\n\s*\n', '\n\n', replacement_text).strip()
    result['final_text'] = replacement_text
    
    return result
