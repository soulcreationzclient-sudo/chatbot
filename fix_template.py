"""
Fix polling UI: appendMessage should render messages identically to Django template,
including timestamps. Also update the API to return created_at for proper rendering.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# FIX 1: Update appendMessage in dashboard.html to include timestamp
# and match the Django template rendering structure
# ============================================================

dashboard_path = os.path.join(BASE, 'newapp', 'templates', 'inbox', 'dashboard.html')

with open(dashboard_path, 'r', encoding='utf-8') as f:
    content = f.read()

fixes = []

# --- Fix appendMessage function to include timestamp ---
OLD_APPEND = """  function appendMessage(msg, sender, msgId = null) {
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
  }"""

NEW_APPEND = """  function appendMessage(msg, sender, msgId = null, createdAt = null) {
    // De-duplication check
    if (msgId && displayedMessageIds.has(msgId)) {
      console.log("Duplicate message ignored:", msgId);
      return;
    }
    if (msgId) displayedMessageIds.add(msgId);

    const row = document.createElement('div');
    row.classList.add('rowmsg', sender === 'human' ? 'user' : sender);
    const bubble = document.createElement('div');
    bubble.classList.add('bubble');

    // Render message content
    const msgDiv = document.createElement('div');
    if (msg === '[Voice Message]') {
      msgDiv.innerHTML = '<div class="voice-message"><audio controls preload="none" style="height:32px;width:200px;"><source type="audio/ogg;codecs=opus">Your browser does not support audio.</audio><div class="voice-label">🎤 Voice Message</div></div>';
    } else {
      msgDiv.innerHTML = formatMessage(msg);
    }
    bubble.appendChild(msgDiv);

    // Add timestamp
    const meta = document.createElement('div');
    meta.classList.add('meta');
    if (createdAt) {
      const d = new Date(createdAt);
      meta.textContent = d.getHours().toString().padStart(2,'0') + ':' + d.getMinutes().toString().padStart(2,'0');
    } else {
      const now = new Date();
      meta.textContent = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
    }
    bubble.appendChild(meta);

    row.appendChild(bubble);
    threadBody.appendChild(row);

    scrollToBottom();
    setTimeout(scrollToBottom, 50);
  }"""

if OLD_APPEND in content:
    content = content.replace(OLD_APPEND, NEW_APPEND)
    fixes.append("Updated appendMessage to include timestamps and voice message support")
else:
    print("WARNING: Could not find appendMessage function - checking if already fixed...")
    if 'createdAt = null' in content:
        print("  Already fixed.")
    else:
        print("  ERROR: appendMessage has unexpected content")

# --- Fix fetchNewMessages to pass created_at to appendMessage ---
OLD_FETCH_CALL = """          appendMessage(msg.messages, msg.who, mId);"""
NEW_FETCH_CALL = """          appendMessage(msg.messages, msg.who, mId, msg.created_at);"""

if OLD_FETCH_CALL in content:
    content = content.replace(OLD_FETCH_CALL, NEW_FETCH_CALL)
    fixes.append("Updated fetchNewMessages to pass created_at to appendMessage")
elif NEW_FETCH_CALL in content:
    print("  fetchNewMessages call already passes created_at")

# --- Fix the manual send to also pass timestamp ---
OLD_SEND_APPEND = """        appendMessage(displayMsg, 'bot');"""
NEW_SEND_APPEND = """        appendMessage(displayMsg, 'bot', null, new Date().toISOString());"""

if OLD_SEND_APPEND in content:
    content = content.replace(OLD_SEND_APPEND, NEW_SEND_APPEND)
    fixes.append("Updated manual send to include timestamp")

# Save
if fixes:
    with open(dashboard_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nApplied {len(fixes)} fix(es) to dashboard.html:")
    for f_item in fixes:
        print(f"  - {f_item}")
else:
    print("\nNo changes needed for dashboard.html")

print("\nDone!")
