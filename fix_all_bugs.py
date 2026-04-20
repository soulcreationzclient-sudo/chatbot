"""
Fix all bugs in the chatbot codebase.
Run: python fix_all_bugs.py
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
fixes_applied = []
errors = []


def fix_file(filepath, replacements, label):
    """Apply a list of (old, new) replacements to a file."""
    full = os.path.join(BASE, filepath)
    if not os.path.exists(full):
        errors.append(f"[{label}] File not found: {filepath}")
        return

    with open(full, 'r', encoding='utf-8') as f:
        content = f.read()

    changed = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changed = True
            print(f"  [FIXED] {label}: replaced target string")
        elif new in content:
            print(f"  [SKIP]  {label}: already fixed")
        else:
            errors.append(f"[{label}] Could not find target string in {filepath}")

    if changed:
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        fixes_applied.append(label)


# ============================================================
# BUG #1: Follow-up message loop (tasks.py)
# ============================================================
print("\n=== BUG #1: Follow-up message loop ===")

OLD_BUG1 = """                # Schedule next step
                next_step = followup.step + 1
                schedule_followup.delay(user.id, next_step)
                
                processed += 1"""

NEW_BUG1 = """                # BUG FIX: Prevent repeated follow-up messages
                user_replied_recently = Message.objects.filter(
                    user_id=user,
                    who='human',
                    created_at__gte=now - timezone.timedelta(minutes=2)
                ).exists()

                existing_pending = ScheduledFollowUp.objects.filter(
                    user=user,
                    status='pending'
                ).exists()

                if user_replied_recently:
                    logger.info(f"\\u23ed\\ufe0f User replied recently - not scheduling next follow-up")
                    user.followup_count = 0
                    user.save(update_fields=['followup_count'])
                elif existing_pending:
                    logger.info(f"\\u23ed\\ufe0f Pending follow-up already exists - skipping duplicate")
                else:
                    # Check for "one last time" loop
                    recent_bot_message = Message.objects.filter(
                        user_id=user,
                        who='bot',
                        messages__icontains='one last time',
                        created_at__gte=now - timezone.timedelta(minutes=5)
                    ).exists()

                    if recent_bot_message:
                        logger.warning(f"\\u23ed\\ufe0f Detected one last time loop - stopping follow-ups")
                        user.followup_count = 999
                        user.save(update_fields=['followup_count'])
                    else:
                        next_step = followup.step + 1
                        schedule_followup.delay(user.id, next_step)

                processed += 1"""

fix_file('newapp/tasks.py', [(OLD_BUG1, NEW_BUG1)], 'Bug#1 Follow-up loop')


# ============================================================
# BUG #2: Generic AI error message (whatsapp.py)
# ============================================================
print("\n=== BUG #2: Generic AI error message ===")

# The file has a curly apostrophe, so search broadly
wp = os.path.join(BASE, 'newapp', 'controllers', 'whatsapp.py')
with open(wp, 'r', encoding='utf-8') as f:
    wc = f.read()

bug2_changed = False
# Find the line containing the generic error
for variant in [
    "generate a response just now",
]:
    if variant in wc:
        # Find the full line
        for line in wc.split('\n'):
            if variant in line and 'bot_response' in line:
                new_block = """                                         # BUG FIX: More specific error messages
                                         if not openai_key:
                                             bot_response = "Sorry, my AI assistant is not configured. Please contact support."
                                         elif 'rate_limit' in str(oe).lower() or 'quota' in str(oe).lower():
                                             bot_response = "Sorry, I'm experiencing high demand right now. Please try again in a few moments."
                                         elif 'timeout' in str(oe).lower():
                                             bot_response = "Sorry, the request timed out. Please try again."
                                         else:
                                             bot_response = "Sorry, I encountered an issue processing your request. Please try again.\""""
                wc = wc.replace(line, new_block)
                bug2_changed = True
                print(f"  [FIXED] Bug#2: replaced generic error message")
                break

if not bug2_changed:
    if "More specific error messages" in wc:
        print("  [SKIP]  Bug#2: already fixed")
    else:
        errors.append("[Bug#2] Could not find generic error message")


# ============================================================
# BUG #3: Context/Persona switching (whatsapp.py)
# ============================================================
print("\n=== BUG #3: Context/Persona switching ===")

OLD_BUG3 = """                            # ==================== END BOT TOGGLE CHECK ====================

                            # ==================== KEYWORD MACRO TAGGING ===================="""

NEW_BUG3 = """                            # ==================== END BOT TOGGLE CHECK ====================

                            # ==================== AUTOMATED MESSAGE DETECTION ====================
                            # BUG FIX: Detect if the incoming message is from another bot/automated system
                            # Check for common automated message patterns to prevent bot-on-bot conversations
                            automated_patterns = [
                                'demo account',
                                'follow up',
                                'one last time',
                                'check if you need',
                            ]

                            is_automated = any(pattern in msg_text.lower() for pattern in automated_patterns) if msg_text else False

                            if is_automated:
                                webhook_logger.info(f"\\U0001f916 Detected automated message from {phone}, skipping AI response")
                                # Don't generate AI response for automated messages - just log and continue
                                continue
                            # ==================== END AUTOMATED MESSAGE DETECTION ====================

                            # ==================== KEYWORD MACRO TAGGING ===================="""

if OLD_BUG3 in wc:
    wc = wc.replace(OLD_BUG3, NEW_BUG3)
    bug2_changed = True  # reuse flag to write
    print("  [FIXED] Bug#3: added automated message detection")
elif "AUTOMATED MESSAGE DETECTION" in wc:
    print("  [SKIP]  Bug#3: already fixed")
else:
    errors.append("[Bug#3] Could not find insertion point")

# Write whatsapp.py if any changes
if bug2_changed:
    with open(wp, 'w', encoding='utf-8') as f:
        f.write(wc)
    fixes_applied.append('Bug#2+#3 whatsapp.py')


# ============================================================
# BUG #4: Voice message display (dashboard.html)
# ============================================================
print("\n=== BUG #4: Voice message display ===")

OLD_BUG4_MSG = """          <div>{{ m.messages }}</div>
          <div class="meta">{{ m.created_at|localtime|date:"H:i" }}</div>"""

NEW_BUG4_MSG = """          {% if m.messages == '[Voice Message]' and m.media_url %}
          <div class="voice-message">
            <audio controls preload="none" style="height:32px;width:200px;">
              <source src="{{ m.media_url }}" type="audio/ogg;codecs=opus">
              Your browser does not support audio.
            </audio>
            <div class="voice-label">\U0001f3a4 Voice Message</div>
          </div>
          {% else %}
          <div>{{ m.messages }}</div>
          {% endif %}
          <div class="meta">{{ m.created_at|localtime|date:"H:i" }}</div>"""

fix_file(
    'newapp/templates/inbox/dashboard.html',
    [(OLD_BUG4_MSG, NEW_BUG4_MSG)],
    'Bug#4 Voice message player'
)

# Add voice message CSS
OLD_CSS = """  .copy-logs-btn {
    margin-top: 10px;
    width: 100%;
  }
</style>"""

NEW_CSS = """  .copy-logs-btn {
    margin-top: 10px;
    width: 100%;
  }

  .voice-message {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .voice-label {
    font-size: 11px;
    color: var(--text-muted);
  }
</style>"""

fix_file(
    'newapp/templates/inbox/dashboard.html',
    [(OLD_CSS, NEW_CSS)],
    'Bug#4 Voice CSS'
)


# ============================================================
# BONUS: Fix template syntax error (==tid needs spaces)
# ============================================================
print("\n=== BONUS: Template syntax fix ===")

fix_file(
    'newapp/templates/inbox/dashboard.html',
    [('request.GET.tag_id==tid', 'request.GET.tag_id == tid')],
    'Template ==tid spacing'
)


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 50)
if fixes_applied:
    print(f"SUCCESS: {len(fixes_applied)} fix(es) applied:")
    for f in fixes_applied:
        print(f"  - {f}")
else:
    print("All fixes were already applied.")

if errors:
    print(f"\nWARNINGS ({len(errors)}):")
    for e in errors:
        print(f"  ! {e}")
else:
    print("\nNo errors.")

print("\nNext: git add, commit, push, then pull on AWS and restart services.")
