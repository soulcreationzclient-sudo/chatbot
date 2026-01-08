
import os
import re

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\inbox\dashboard.html'

def fix_usability():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to remove the aggressive loop in DOMContentLoaded
    # Pattern to find:
    # let checks = 0;
    # const interval = setInterval(() => {
    #   scrollToBottom();
    #   checks++;
    #   if (checks > 20) clearInterval(interval); // Stop after 2s (100ms * 20)
    # }, 100);

    # We'll use regex to match this block loosely
    aggressive_loop_regex = r'let\s*checks\s*=\s*0;\s*const\s*interval\s*=\s*setInterval\(\(\)\s*=>\s*\{[\s\S]*?clearInterval\(interval\);\s*//\s*Stop\s*after\s*2s[\s\S]*?\}\s*,\s*100\);'
    
    # We will replace it with a single delayed check just in case, or nothing.
    # Let's replace with a single double-check to be safe, but non-blocking.
    # actually, just removing it is best if ResizeObserver is working.
    # But let's leave one small timeout for safety.
    replacement = """
    // Single check after short delay to handle immediate rendering
    setTimeout(scrollToBottom, 100);
    """
    
    new_content, count = re.subn(aggressive_loop_regex, replacement, content)
    
    if count == 0:
        print("Could not match regex for aggressive loop. Trying explicit string search.")
        # Fallback: simpler string matching if exact formatting matches
        target_str = """    let checks = 0;
    const interval = setInterval(() => {
      scrollToBottom();
      checks++;
      if (checks > 20) clearInterval(interval); // Stop after 2s (100ms * 20)
    }, 100);"""
        if target_str in content:
            new_content = content.replace(target_str, replacement)
            count = 1
    
    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Fixed: Removed aggressive scroll loop.")
    else:
        print("Error: Could not find the scroll loop to remove.")

if __name__ == "__main__":
    fix_usability()
