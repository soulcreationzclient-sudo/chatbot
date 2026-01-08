
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_master():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Fix Headers Template Tag (ensure it's single line)
    # Target: {{ (newline) selected_user.name... }}
    # We'll use a broad regex to capture this specific block
    head_tag_pattern = re.compile(r'<div class="avatar"[^>]*>\{\{\s*selected_user\.name\|default:selected_user\.phone_no\|slice:":2"\|upper\s*\}\}</div>', re.DOTALL)
    
    # We want to replace it with a clean version, but wait, the current file has:
    # <div class="avatar" style="width:36px;height:36px">{{
    #   selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>
    
    # Let's clean it up to be ONE line.
    clean_tag = '<div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>'
    
    # Use simple string replacement if exact match, or regex for flexible whitespace
    regex_dirty = r'<div class="avatar" style="width:36px;height:36px">\s*\{\{\s*selected_user\.name\|default:selected_user\.phone_no\|slice:":2"\|upper\s*\}\}\s*</div>'
    content = re.sub(regex_dirty, clean_tag, content)

    # 2. Update Polling Interval to 1000ms
    content = content.replace('setInterval(fetchNewMessages, 3000);', 'setInterval(fetchNewMessages, 1000);')
    
    # 3. Clean up the end of the file (garbage code)
    # The file ends with:
    #   }
    #   return '';
    # }
    # });
    # 
    # function getCsrfToken() { ... duplicate ... }
    # </script>
    
    # We will locate the LAST function getCsrfToken and the closure before it.
    
    # Logic: Find the block starting from `function getCsrfToken() {` at line ~443 until `</script>`
    # and replace it with a clean single version.
    
    # The file content at the end is messy. Let's look for the marker of the FIRST getCsrfToken.
    start_mark = "function getCsrfToken() {"
    
    # We expect getCsrfToken to be defined once.
    # We will split by start_mark. 
    parts = content.split(start_mark)
    
    if len(parts) > 1:
        # Keep the text BEFORE the first getCsrfToken
        preamble = parts[0]
        
        # New clean ending script
        new_ending = """
  function getCsrfToken() {
    const name = 'csrftoken=';
    const decoded = decodeURIComponent(document.cookie);
    const ca = decoded.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) === 0) {
            return c.substring(name.length, c.length);
        }
    }
    return '';
  }
</script>
{% endblock %}
"""
        # We need to be careful. `preamble` ends with `  }` from fetchNewMessages usually.
        # But looking at line 441 in previous view_file:
        # 441:   }
        # 442: 
        # 443:   function getCsrfToken() {
        
        # So replacing from first 'function getCsrfToken() {' to end of string with `new_ending` (minus the </script> part since preamble has the rest? No, preamble stops at function definition).
        
        # Actually, let's just truncate at the last closing brace of `fetchNewMessages`? No, risky.
        
        # Safer strategy: find the index of the first `function getCsrfToken() {`
        idx = content.find("function getCsrfToken() {")
        if idx != -1:
             content = content[:idx] + new_ending.strip()
             # Note: new_ending includes {% endblock %} and </script> so we need to be sure we're replacing the REST of the file.
             pass

    # 4. Improve scrollToBottom logic
    # Find the scrollToBottom function
    scroll_func_regex = r'function scrollToBottom\(\) \{[\s\S]*?\}'
    
    new_scroll_func = """function scrollToBottom() {
    var el = document.getElementById('threadBody');
    if (el) {
      el.scrollTop = el.scrollHeight; // Direct jump
    }
  }"""
    
    content = re.sub(scroll_func_regex, new_scroll_func, content)

    # 5. Ensure scroll on update
    # In fetchNewMessages, we have:
    # // appendMessage handles smooth scroll.
    # We want to force it or ensure appendMessage uses it.
    
    # Let's update `appendMessage` to force scroll aggressively
    append_regex = r'function appendMessage\(msg, sender\) \{[\s\S]*?\}'
    
    new_append_func = """function appendMessage(msg, sender) {
    const threadBody = document.getElementById('threadBody');
    const row = document.createElement('div');
    row.classList.add('rowmsg', sender);
    const bubble = document.createElement('div');
    bubble.classList.add('bubble');

    // Format message (render images/links)
    bubble.innerHTML = formatMessage(msg);

    row.appendChild(bubble);
    threadBody.appendChild(row);
    
    // Force scroll to bottom
    threadBody.scrollTop = threadBody.scrollHeight;
  }"""
    
    content = re.sub(append_regex, new_append_func, content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        print("Master fix applied: Tags cleaned, JS logic updated, Polling speed increased.")

if __name__ == "__main__":
    fix_master()
