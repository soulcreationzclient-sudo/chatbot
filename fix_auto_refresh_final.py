
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_auto_refresh_final():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to completely replace the <script> block again to be safe and clean.
    # It's better than regex patching piecemeal.
    
    script_start = content.find('<script>')
    script_end = content.find('{% endblock %}', script_start)
    
    if script_start != -1 and script_end != -1:
        prefix = content[:script_start]
        suffix = content[script_end:]
        
        # New robust script
        new_script = """<script>
  // Robust Scroll & Auto-Refresh Logic (Final)
  const threadBody = document.getElementById('threadBody');
  // Track displayed IDs to prevent duplicates
  const displayedMessageIds = new Set();

  function scrollToBottom() {
    if (threadBody) {
      threadBody.scrollTop = threadBody.scrollHeight;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // 1. Index existing messages
    const existingIds = document.querySelectorAll('.rowmsg');
    // We don't have IDs on the DOM elements easily unless we add them. 
    // But we can just rely on the Set for NEW messages. 
    // Actually, let's try to populate the Set from the initial `lastMessageId` logic strictly?
    // No, better to just let the Set track what we fetch via API.
    // The initial messages are "static". We won't re-fetch them because lastMessageId starts at the end.
    
    scrollToBottom();
    setTimeout(scrollToBottom, 100);

    // 2. Start Polling
    console.log("Starting Auto-Refresh Polling...");
    setInterval(fetchNewMessages, 2000); // 2 seconds
  });

  // Resize Observer for images/content
  if (threadBody) {
    const observer = new ResizeObserver(() => {
      const isNearBottom = threadBody.scrollHeight - threadBody.scrollTop - threadBody.clientHeight < 300;
      if (isNearBottom) scrollToBottom();
    });
    observer.observe(threadBody);
  }

  window.onload = function () { scrollToBottom(); };

  async function sendMessage(event) {
    event.preventDefault();
    const input = document.getElementById('userMessage');
    const message = input.value.trim();
    if (!message) return false;

    // Optimistic append (ID unknown, so not in Set)
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

  function appendMessage(msg, sender, msgId = null) {
    // De-duplication check
    if (msgId && displayedMessageIds.has(msgId)) {
        console.log("Duplicate message ignored:", msgId);
        return; 
    }
    if (msgId) displayedMessageIds.add(msgId);

    const row = document.createElement('div');
    row.classList.add('rowmsg', sender);
    const bubble = document.createElement('div');
    bubble.classList.add('bubble');

    bubble.innerHTML = formatMessage(msg);

    row.appendChild(bubble);
    threadBody.appendChild(row);
    
    scrollToBottom();
    setTimeout(scrollToBottom, 50);
  }

  function formatMessage(text) {
    if (!text) return '';
    // Image
    const imgMatch = text.match(/^\\[Image:\\s*(.*?)\\]\\s*(.*)/is);
    if (imgMatch) {
      const url = imgMatch[1].trim();
      const caption = imgMatch[2].trim();
      return `
        <a href="${url}" target="_blank">
          <img src="${url}" style="max-width:100%; border-radius:8px; margin-bottom:4px;" onerror="this.style.display='none'" onload="scrollToBottom()">
        </a>
        ${caption ? `<div class="mt-1">${caption}</div>` : ''}
      `;
    }
    // Document
    const docMatch = text.match(/^\\[Document:\\s*(.*?)\\]\\s*(.*)/is);
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
    // Text
    const safeText = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    return safeText.replace(/\\n/g, '<br>');
  }

  // Auto-format existing
  document.addEventListener("DOMContentLoaded", function () {
    const bubbles = document.querySelectorAll('.bubble > div:first-child');
    bubbles.forEach(el => {
      // Logic to auto-format existing can be simplified or kept if needed
      if (!el.classList.contains('meta')) {
        const raw = el.innerText;
        if (raw.trim().startsWith('[Image:') || raw.trim().startsWith('[Document:')) {
            el.innerHTML = formatMessage(raw);
        }
      }
    });
  });

  // Polling Logic
  let lastMessageId = 0;
  {% if messages %}
  lastMessageId = {{ messages.last.id|default:0 }};
  {% endif %}
  const currentUserId = "{{ selected_user.id|default:'' }}";

  async function fetchNewMessages() {
    if (!currentUserId) return;
    
    // Cache buster
    const ts = new Date().getTime();

    try {
      const url = `/api/inbox/new_messages?user_id=${currentUserId}&last_id=${lastMessageId}&_t=${ts}`;
      const response = await fetch(url);
      if (!response.ok) return;
      
      const data = await response.json();
      if (data.messages && data.messages.length > 0) {
        console.log(`Fetched ${data.messages.length} new messages.`);
        data.messages.forEach(msg => {
          // Pass ID to appendMessage for de-dupe
          const mId = parseInt(msg.id);
          appendMessage(msg.messages, msg.who, mId);
          lastMessageId = Math.max(lastMessageId, mId);
        });
      }
    } catch (e) {
      console.error("Polling error:", e);
    }
  }

  function getCsrfToken() {
    const name = 'csrftoken=';
    const decoded = decodeURIComponent(document.cookie);
    const ca = decoded.split(';');
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) == ' ') c = c.substring(1);
      if (c.indexOf(name) === 0) return c.substring(name.length, c.length);
    }
    return '';
  }
</script>
"""
        # Note: I need to be careful with double backslashes for regex string in python
        # In the formatMessage function above:
        # const imgMatch = text.match(/^\[Image:\s*(.*?)\]\s*(.*)/is);
        # In python string: ^\\[Image:\\s*(.*?)\\]\\s*(.*)
        
        # Applying replacment
        new_full_content = prefix + new_script + suffix
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_full_content)
        print("Final Robust Auto-Refresh Script Applied.")

if __name__ == "__main__":
    fix_auto_refresh_final()
