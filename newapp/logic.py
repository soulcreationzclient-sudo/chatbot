import requests
import json
from .models import ExternalAPI

def execute_tool(tool_name, arguments, admin):
    """
    Execute a defined ExternalAPI tool.
    
    Args:
        tool_name (str): Name of the tool to execute
        arguments (dict): Dictionary of arguments extracted by AI (e.g. {"booking_id": "123"})
        admin (Admin): The admin instance to look up tools for
        
    Returns:
        str: JSON response string or error message
    """
    try:
        # Find the tool config
        tool_config = ExternalAPI.objects.filter(admin=admin, name=tool_name).first()
        if not tool_config:
            return f"Error: Tool '{tool_name}' not configured."

        # Prepare URL and Payload with variable substitution
        # We use simple string replacement for {{variable}} style placeholders
        
        target_url = tool_config.url
        target_payload = tool_config.payload or {}
        target_headers = tool_config.headers or {}

        # Replace in URL
        for key, value in arguments.items():
            placeholder = "{{" + key + "}}"
            target_url = target_url.replace(placeholder, str(value))

        # Replace in Payload (recursively if needed, but let's stick to simple string dump for now)
        # Convert payload to string, replace, then parse back to JSON could be unsafe but easiest for flexible schemas
        payload_str = json.dumps(target_payload)
        for key, value in arguments.items():
            placeholder = "{{" + key + "}}"
            payload_str = payload_str.replace(placeholder, str(value))
            
        final_payload = json.loads(payload_str)

        # Execute Request
        method = tool_config.method.upper()
        
        if method == 'GET':
            response = requests.get(target_url, headers=target_headers, params=final_payload)
        elif method == 'POST':
            response = requests.post(target_url, headers=target_headers, json=final_payload)
        else:
            return f"Error: Unsupported method {method}"

        # Return results
        try:
            return json.dumps(response.json())
        except:
            return response.text

    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}"
