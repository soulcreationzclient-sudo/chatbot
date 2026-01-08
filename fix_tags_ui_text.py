
import os

file_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\set\tags.html'

def update_ui_text():
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to find the entire div class="ai-hint" block and replace it.
    # Since exact matching failed via tool, we'll look for start and end markers.
    
    start_marker = '<div class="ai-hint">'
    end_marker = '</div>'
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("Error: Could not find start marker")
        return

    # Find the closing div for this block. 
    # Since nested divs exist, we need to balance them or just look for the known content structure.
    # The block ends before <!-- Tags List -->
    
    next_section_marker = '<!-- Tags List -->'
    end_idx = content.find(next_section_marker)
    
    if end_idx == -1:
        print("Error: Could not find next section marker")
        return
        
    # The actual end of the div should be the last </div> before next_section_marker
    # Let's just scan backwards from end_idx
    block_end_idx = content.rfind('</div>', 0, end_idx)
    
    if block_end_idx == -1 or block_end_idx < start_idx:
         print("Error: Could not find closing div properly")
         return

    # Extract the chunk to verify we are replacing the right thing
    old_chunk = content[start_idx:block_end_idx+6] # +6 for </div>
    # print("DEBUG: Found chunk:\n", old_chunk)
    
    new_html = """<div class="ai-hint">
        <strong>🤖 Automatic AI Mode (Functions)</strong>
        <p class="mb-0 mt-2 small">Use this when you want the AI to decide. Add instructions to your ChatGPT Prompt like:<br>
            <code>If user seems interested, use the apply_tag function.</code>
        </p>

        <div class="mt-3 pt-3 border-top border-warning-subtle">
            <strong>⚡ Manual Rule Mode (Macros)</strong>
            <p class="mb-0 mt-1 small">Use this to force a tag when a specific rule is met. Example instruction:</p>
            <p class="mb-1 small"><code>If user says 'STOP', output {% templatetag openvariable %}tag:add:blocked{% templatetag closevariable %}</code></p>
            <div class="d-flex gap-2 mt-2">
                <code>{% templatetag openvariable %}tag:add:tag_name{% templatetag closevariable %}</code>
                <code>{% templatetag openvariable %}tag:remove:tag_name{% templatetag closevariable %}</code>
            </div>
        </div>
    </div>"""
    
    new_content = content[:start_idx] + new_html + content[block_end_idx+6:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Successfully updated tags.html UI text.")

if __name__ == "__main__":
    update_ui_text()
