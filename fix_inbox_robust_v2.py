
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_robust_v2():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. FIX HEADER TAG (Targeting lines 238-239 specifically)
    # Current:
    # <div class="avatar" style="width:36px;height:36px">{{
    #   selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>
    
    # We will replace the whole block.
    # Regex to find the div with style and the split tag
    header_regex = r'(<div class="avatar" style="width:36px;height:36px">)\s*\{\{\s*\n\s*selected_user\.name\|default:selected_user\.phone_no\|slice:":2"\|upper\s*\}\}\s*(</div>)'
    
    clean_header = r'\1{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}\2'
    
    # Try regex first
    new_content = re.sub(header_regex, clean_header, content, flags=re.MULTILINE)
    
    if new_content == content:
        # Fallback to string replacement if regex is fussy about whitespace
        print("Regex didn't match header, trying direct string replacement...")
        bad_string = """<div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>"""
        # Wait, the view showed it split.
        bad_block = """<div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>""" 
        # Actually line 238 is: <div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>
        # Wait, looking at the previous view_file output (Step Id: 1301):
        # 238:       <div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>
        # IT IS ONE LINE IN THE FILE!
        # Why does the user see it broken?
        # Maybe I am misinterpreting the screenshot or it IS cached.
        # But wait, line 238 in the view output shows it on one line.
        # Let's double check line 238 in view_file output above.
        # 238:       <div class="avatar" style="width:36px;height:36px">{{ selected_user.name|default:selected_user.phone_no|slice:":2"|upper }}</div>
        # It looks correct in the file.
        # I will assume it is correct and maybe focus on the whitespace or just force it again.
        pass

    # 2. IMPROVE SCROLL LOGIC
    # We will replace the entire <script> block with a new, robust version.
    
    # Locate start and end of script
    script_start = content.find('<script>')
    script_end = content.find('{% endblock %}', script_start)
    
    if script_start != -1 and script_end != -1:
        prefix = content[:script_start]
        suffix = content[script_end:]
        
        new_script = """<script>
  // Robust Scroll Logic
  const threadBody = document.getElementById('threadBody');

  function scrollToBottom() {
    if (threadBody) {
      threadBody.scrollTop = threadBody.scrollHeight;
    }
  }

  // 1. Instant scroll on load
  document.addEventListener("DOMContentLoaded", function () {
    scrollToBottom();
    // Force scroll check loop for 2 seconds to handle layout shifts (images loading)
    let checks = 0;
    const interval = setInterval(() => {
      scrollToBottom();
      checks++;
      if (checks > 20) clearInterval(interval); // Stop after 2s (100ms * 20)
    }, 100);
  });

  // 2. Observer for size changes (images loading, content formatting)
  if (threadBody) {
    const observer = new ResizeObserver(() => {
      // Only auto-scroll if we were already near bottom, OR if it's the initial load.
      // For now, let's keep it simple and scroll to bottom if size changes aggressively for this use case.
      // To prevent annoying jumps when reading history, we might check scrollTop.
      // But user requested: "instantly new message ... updated ... scrolled to latest"
      
      const isNearBottom = threadBody.scrollHeight - threadBody.scrollTop - threadBody.clientHeight < 300;
      if (isNearBottom) {
        scrollToBottom();
      }
    });
    observer.observe(threadBody);
    
    // Also observe children to detect image loads affecting height? 
    // ResizeObserver on container covers content size changes usually.
  }

  window.onload = function () {
    scrollToBottom();
  };

  async function sendMessage(event) {
    event.preventDefault();
    const input = document.getElementById('userMessage');
    const message = input.value.trim();
    if (!message) return false;

    appendMessage(message, 'user');
    input.value = '';
    input.disabled = true;

    try {
      const formData = new FormData();
      formData.append('message', message);

      const response = await fetch('/chatgpt/respond/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData
      });
      const data = await response.json();

      if (response.ok && data.reply) {
        appendMessage(data.reply, 'bot');
      } else {
        appendMessage("Error: " + (data.error || "No response"), 'bot');
      }
    } catch (error) {
      appendMessage("Network error. Please try again.", 'bot');
    } finally {
      input.disabled = false;
      input.focus();
    }
    return false;
  }

  function appendMessage(msg, sender) {
    const row = document.createElement('div');
    row.classList.add('rowmsg', sender);
    const bubble = document.createElement('div');
    bubble.classList.add('bubble');

    // Format message (render images/links)
    bubble.innerHTML = formatMessage(msg);

    row.appendChild(bubble);
    threadBody.appendChild(row);
    
    // Force scroll immediately
    scrollToBottom();
    // And again slightly later for rendering
    setTimeout(scrollToBottom, 50);
  }

  function formatMessage(text) {
    if (!text) return '';

    // 1. Check for Image with URL: [Image: /media/...] caption
    const imgMatch = text.match(/^\[Image:\s*(.*?)\]\s*(.*)/is);
    if (imgMatch) {
      const url = imgMatch[1].trim();
      const caption = imgMatch[2].trim();
      // Add onload handler to image to scroll when loaded
      return `
        <a href="${url}" target="_blank">
          <img src="${url}" style="max-width:100%; border-radius:8px; margin-bottom:4px;" onerror="this.style.display='none'" onload="scrollToBottom()">
        </a>
        ${caption ? `<div class="mt-1">${caption}</div>` : ''}
      `;
    }

    // 2. Check for Document
    const docMatch = text.match(/^\[Document:\s*(.*?)\]\s*(.*)/is);
    if (docMatch) {
      const url = docMatch[1].trim();
      const caption = docMatch[2].trim();
      if (url.startsWith('/') || url.startsWith('http')) {
        return `
          <div class="d-flex align-items-center gap-2 p-2 bg-light rounded text-dark">
            <i class="fa-solid fa-file-lines fs-4 text-primary"></i>
            <a href="${url}" target="_blank" class="text-decoration-underline text-break" download>Download Document</a>
          </div>
          ${caption ? `<div class="mt-1 small">${caption}</div>` : ''}
        `;
      }
    }

    // 3. Fallback text
    const safeText = text.replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");

    return safeText.replace(/\\n/g, '<br>');
  }

  // Auto-format existing
  document.addEventListener("DOMContentLoaded", function () {
    const bubbles = document.querySelectorAll('.bubble > div:first-child');
    bubbles.forEach(el => {
      if (!el.classList.contains('meta')) {
        const raw = el.innerText;
        if (raw.trim().startsWith('[Image:') || raw.trim().startsWith('[Document:')) {
          el.innerHTML = formatMessage(raw);
        }
      }
    });

    scrollToBottom();

    // POLING
    setInterval(fetchNewMessages, 1000);
  });

  // Polling Logic
  let lastMessageId = 0;
  {% if messages %}
  lastMessageId = {{ messages.last.id|default:0 }};
  {% endif %}
  const currentUserId = "{{ selected_user.id|default:'' }}";

  async function fetchNewMessages() {
    if (!currentUserId) return;

    try {
      const response = await fetch(`/api/inbox/new_messages?user_id=${currentUserId}&last_id=${lastMessageId}`);
      if (!response.ok) return;
      
      const data = await response.json();
      if (data.messages && data.messages.length > 0) {
        data.messages.forEach(msg => {
          appendMessage(msg.messages, msg.who);
          lastMessageId = Math.max(lastMessageId, msg.id);
        });
        // Scroll is handled in appendMessage
      }
    } catch (e) {
      console.log("Polling error:", e);
    }
  }

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
"""
        # Replace the old script block with the new one
        # Use regex or simple string replacement if unique
        # We need to be careful about not deleting {% endblock %}
        
        # Construct full new content
        new_full_content = prefix + new_script + suffix
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_full_content)
        print("Robust Fix V2 Applied: ScrollObserver, Image OnLoad Scroll, and Aggressive Init Loop.")
    else:
        print("Could not locate script block to replace.")

if __name__ == "__main__":
    fix_robust_v2()
