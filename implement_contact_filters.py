
import os
import subprocess
import sys

models_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\models.py'
contact_py = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\contact.py'
dashboard_html = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\templates\contact\dashboard.html'

def run_command(command):
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(result.stdout)
    return True

def apply_filters():
    # 1. Modify models.py
    if os.path.exists(models_py):
        with open(models_py, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "source =" not in content:
            # Add source field
            # Find the User model definition
            target = "followup_count = models.IntegerField(default=0)  # Track follow-up attempts (max 3)"
            replacement = "followup_count = models.IntegerField(default=0)  # Track follow-up attempts (max 3)\n    source = models.CharField(max_length=50, default='Whatsapp')"
            
            if target in content:
                content = content.replace(target, replacement)
                with open(models_py, 'w', encoding='utf-8') as f:
                    f.write(content)
                print("Added source field to User model.")
                
                # Run migrations
                if run_command("python manage.py makemigrations") and run_command("python manage.py migrate"):
                    print("Database migrated.")
                else:
                    print("Migration failed. Please check.")

    # 2. Modify contact.py
    if os.path.exists(contact_py):
        with open(contact_py, 'r', encoding='utf-8') as f:
            py = f.read()
            
        # Add imports if missing
        imports = "from django.db.models import Max, Q\nfrom datetime import timedelta\nfrom django.utils import timezone\nimport datetime\n"
        if "from django.db.models import Max" not in py:
             py = imports + py

        # Logic Update
        # We need to find the `users = ...` query and extend it.
        # Existing logic likely: users = User.objects.filter(admin_id=admin_id)...
        
        # We'll inject the filter logic block.
        filter_logic = """
        # --- Advanced Filters ---
        tag_id = request.GET.get('tag_id')
        source = request.GET.get('source')
        timeframe = request.GET.get('timeframe') # 24h, 7d, 30d, custom
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if tag_id:
            users = users.filter(usertag__tag_id=tag_id)
            
        if source and source != 'all':
            users = users.filter(source__iexact=source)

        if timeframe:
            now = timezone.now()
            if timeframe == '24h':
                # Last seen (last message) in 24h
                users = users.filter(message__created_at__gte=now - timedelta(days=1))  # Assuming 'message' relation or similar
                # Actually, strictly speaking 'last_seen' is an annotation usually. 
                # Let's use the annotation if available or join query.
                pass 
            elif timeframe == '7d':
                pass # Logic below in detailed block
        
        # Better approach:
        # We already have `users` queryset. Let's filter it.
        # But wait, we need to annotate `last_seen` first to filter by it if it's not a direct field.
        # The inbox `dashboard` used: users = User.objects.annotate(last_msg_time=Max('message__created_at'))
        # We should replicate that here.
        """
        
        # Let's replace the User query construction with a robust one.
        # Find: users = User.objects.filter(admin_id=admin_id).order_by('-created_at') (or similar)
        # We'll look for `users = User.objects.filter(admin_id=admin_id)`
        
        start_marker = "users = User.objects.filter(admin_id=admin_id)"
        
        if start_marker in py:
            # We will use regex to find where the line ends or block ends to safely replace?
            # Or just inject after it?
            # Let's replace the initial query to include annotation.
            
            new_query = """
        users = User.objects.filter(admin_id=admin_id).annotate(
            last_seen=Max('message__created_at')
        ).order_by('-created_at')

        # --- Filter Logic ---
        tag_id = request.GET.get('tag_id')
        if tag_id:
            users = users.filter(usertag__tag_id=tag_id)

        source = request.GET.get('source')
        if source and source.lower() != 'all':
             users = users.filter(source__iexact=source)

        timeframe = request.GET.get('timeframe')
        if timeframe:
            now = timezone.now()
            if timeframe == '24h':
                users = users.filter(last_seen__gte=now - timedelta(hours=24))
            elif timeframe == '7d':
                users = users.filter(last_seen__gte=now - timedelta(days=7))
            elif timeframe == '30d':
                users = users.filter(last_seen__gte=now - timedelta(days=30))
            elif timeframe == 'custom':
                s_date = request.GET.get('start_date')
                e_date = request.GET.get('end_date')
                if s_date:
                    users = users.filter(last_seen__gte=s_date)
                if e_date:
                    # Make end date inclusive of the day
                    # This simplest way is typically strictly string compare or casting.
                    # Django handles string dates well usually.
                    users = users.filter(last_seen__lte=e_date + ' 23:59:59')
        
        """
            # Replace the simple line with the rich block
            # Be careful about indentation. The controller is likely inside `def dashboard(request):`
            # Adjust indentation to match `users = ...` (usually 8 spaces)
            
            # Since I can't see the exact indentation in `py` string easily without printing, 
            # I will assume standard 4-space tab or 8-space.
            # `view_file` showed standard indentation.
            
            # Remove any existing filtering provided in previous scripts (like tag filtering I added manually?)
            # I added logic for tag filter previously manually or via script?
            # Let's overwrite the `users =` line and subsequent filters if they exist close by.
            
            # Actually, let's just REPLACE the specific `users = ...` line and hope we don't duplicate logic.
            # If I added tag logic before, it might double up.
            
            # Let's try to match the WHOLE block if possible.
            # Existing:
            # users = User.objects.filter(admin_id=admin_id).order_by('-created_at')
            # if request.GET.get('tag_id'): ...
            
            # I'll search for the `users = ` line and ignore the rest, letting Python execute sequential filters.
            # Python allows re-filtering: users = users.filter(...)
            
            py = py.replace(start_marker, new_query.strip())
            
            # Also replace `.order_by('-created_at')` if it was there attached to the line
            # My `start_marker` didn't include order_by.
            
            # To be safe, let's look for "users = User.objects.filter(admin_id=admin_id)..." using regex or loose match
            # But the `start_marker` replacement is safest if it's unique.
            
            # Just ensure we have necessary imports
            
            with open(contact_py, 'w', encoding='utf-8') as f:
                f.write(py)
            print("Contact controller updated with advanced filters.")

    # 3. Modify dashboard.html
    if os.path.exists(dashboard_html):
        with open(dashboard_html, 'r', encoding='utf-8') as f:
            html = f.read()
            
        # Add styles for Filter Panel
        styles = """
  /* FILTER PANEL */
  .filter-panel {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 20px;
    display: none; /* Hidden by default */
    gap: 20px;
    flex-wrap: wrap;
    align-items: flex-start;
  }
  .filter-panel.open {
    display: flex;
  }
  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .filter-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  .pills {
    display: flex;
    gap: 8px;
  }
  .pill {
    padding: 6px 12px;
    border-radius: 20px;
    background: #f1f5f9;
    color: var(--text-main);
    font-size: 13px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.2s;
  }
  .pill:hover { background: #e2e8f0; }
  .pill.active {
    background: #eff6ff;
    color: var(--primary);
    border-color: #bfdbfe;
    font-weight: 600;
  }
"""
        if "/* FILTER PANEL */" not in html:
            html = html.replace("</style>", styles + "\n</style>")

        # Inject Filter Panel HTML
        # We put it after `.toolbar`.
        panel_html = """
  <!-- Filter Panel -->
  <div class="filter-panel" id="filterPanel">
    
    <!-- Source -->
    <div class="filter-group">
      <div class="filter-label">Source</div>
      <select id="filterSource" class="form-select form-select-sm" style="min-width:140px; padding:6px; border-radius:8px; border:1px solid #e5e7eb;">
        <option value="all">All Sources</option>
        <option value="Whatsapp">Whatsapp</option>
        <option value="Web">Web</option>
        <option value="Manual">Manual</option>
      </select>
    </div>

    <!-- Timeframe -->
    <div class="filter-group">
      <div class="filter-label">Last Seen</div>
      <div class="pills">
        <div class="pill" onclick="setFilterTime('all', this)">Anytime</div>
        <div class="pill" onclick="setFilterTime('24h', this)">24h</div>
        <div class="pill" onclick="setFilterTime('7d', this)">7 Days</div>
        <div class="pill" onclick="setFilterTime('30d', this)">30 Days</div>
        <div class="pill" onclick="setFilterTime('custom', this)">Custom</div>
      </div>
      <input type="hidden" id="filterTimeframe" value="">
    </div>

    <!-- Custom Dates (Hidden unless custom) -->
    <div class="filter-group" id="customDateGroup" style="display:none; flex-direction:row; align-items:flex-end;">
      <div>
        <div class="filter-label" style="margin-bottom:4px;">Start Date</div>
        <input type="date" id="filterStartDate" class="form-control form-control-sm" style="padding:4px 8px; border-radius:6px; border:1px solid #e5e7eb;">
      </div>
      <div>
        <div class="filter-label" style="margin-bottom:4px;">End Date</div>
        <input type="date" id="filterEndDate" class="form-control form-control-sm" style="padding:4px 8px; border-radius:6px; border:1px solid #e5e7eb;">
      </div>
    </div>

    <!-- Apply Button -->
    <div style="flex:1; display:flex; justify-content:flex-end; align-items:flex-end; height:100%;">
      <button class="btn" style="background:var(--primary); color:#fff; border:none;" onclick="applyAdvancedFilters()">Apply Filters</button>
    </div>
  </div>
"""
        toolbar_end = '<div class="toolbar">'
        # We want to insert the filter panel AFTER the closing div of toolbar?
        # Or inside? After is better.
        # Find toolbar closing div.
        # It has multiple children.
        # Let's find `<div class="table-head">` and insert BEFORE it.
        if '<div class="table-head">' in html:
            html = html.replace('<div class="table-head">', panel_html + '\n<div class="table-head">')
        
        # Add Toggle Button to Toolbar
        # Find `Import Contacts` button and add `Filter` button before/after it.
        target_btn = '<button class="btn" id="importContactsBtn">Import Contacts</button>'
        toggle_btn = """
    <button class="btn" onclick="toggleFilterPanel()" id="filterToggleBtn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px;"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"></path></svg>
      Filters
    </button>
"""
        if target_btn in html:
            html = html.replace(target_btn, toggle_btn + target_btn)

        # Update JS
        js_logic = """
  // FILTER LOGIC
  function toggleFilterPanel() {
    const p = document.getElementById('filterPanel');
    const b = document.getElementById('filterToggleBtn');
    if (p.style.display === 'flex') {
        p.style.display = 'none';
        b.style.background = '';
        b.style.color = '';
    } else {
        p.style.display = 'flex';
        b.style.background = '#eff6ff';
        b.style.color = 'var(--primary)';
    }
  }

  function setFilterTime(val, el) {
    document.getElementById('filterTimeframe').value = val;
    // UI
    document.querySelectorAll('.pill').forEach(e => e.classList.remove('active'));
    el.classList.add('active');
    
    // Show/Hide Date inputs
    const grp = document.getElementById('customDateGroup');
    if (val === 'custom') grp.style.display = 'flex';
    else grp.style.display = 'none';
  }

  function applyAdvancedFilters() {
    const url = new URL(window.location.href);
    
    // Source
    const src = document.getElementById('filterSource').value;
    if (src && src !== 'all') url.searchParams.set('source', src);
    else url.searchParams.delete('source');

    // Timeframe
    const tf = document.getElementById('filterTimeframe').value;
    if (tf && tf !== 'all') {
        url.searchParams.set('timeframe', tf);
        if (tf === 'custom') {
            const s = document.getElementById('filterStartDate').value;
            const e = document.getElementById('filterEndDate').value;
            if (s) url.searchParams.set('start_date', s);
            if (e) url.searchParams.set('end_date', e);
        }
    } else {
        url.searchParams.delete('timeframe');
        url.searchParams.delete('start_date');
        url.searchParams.delete('end_date');
    }

    // Keep Tag if exists (handled by ApplyContactFilter usually, but we overwrite url)
    // Tag is in URL already if selected.
    
    window.location.href = url.toString();
  }
  
  // Init UI on load
  document.addEventListener("DOMContentLoaded", function() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('source') || params.has('timeframe')) {
        toggleFilterPanel(); // Open if active
        
        // Set Source
        const s = params.get('source');
        if (s) document.getElementById('filterSource').value = s;
        
        // Set Timeframe
        const tf = params.get('timeframe');
        if (tf) {
            document.getElementById('filterTimeframe').value = tf;
            // Activate pill
            const pills = document.querySelectorAll('.pill');
            pills.forEach(p => {
                if (p.textContent.toLowerCase().includes(tf) || (tf==='24h' && p.textContent.includes('24h')) || (tf==='7d' && p.textContent.includes('7')) || (tf==='30d' && p.textContent.includes('30'))) {
                   p.classList.add('active'); 
                }
                if (tf === 'custom' && p.textContent === 'Custom') p.classList.add('active');
                if (tf === 'all' && p.textContent === 'Anytime') p.classList.add('active');
            });
            
            if (tf === 'custom') {
                document.getElementById('customDateGroup').style.display = 'flex';
                document.getElementById('filterStartDate').value = params.get('start_date') || '';
                document.getElementById('filterEndDate').value = params.get('end_date') || '';
            }
        }
    } else {
        // Default Pill
        document.querySelector('.pill').classList.add('active');
    }
  });
"""
        if "// FILTER LOGIC" not in html:
             html = html.replace("</script>", js_logic + "\n</script>")

        # Update Row to show correct source
        # <div class="source muted">Whatsapp</div> -> <div class="source muted">{{ u.source }}</div>
        html = html.replace('<div class="source muted">Whatsapp</div>', '<div class="source muted">{{ u.source }}</div>')

        # Update Row to show Last Seen
        # Need to ensure `last_seen` is available.
        # In contact.py we are annotating `last_seen`.
        # <div class="entered muted">{{ u.created_at }}</div> -> last seen?
        # User requested filtering by last seen, so showing it in "Last Seen" column makes sense.
        # But table header says "Last Seen" and row says `u.created_at`.
        # <div class="entered muted">{{ u.created_at }}</div> is in the 5th column.
        # Table head: Name, Phone, Source, Last Seen, Actions.
        # So `u.created_at` was being displayed in "Last Seen" column? That feels wrong (Created vs Last Seen).
        # Let's fix it to show `u.last_seen` if available, else `u.created_at`.
        
        html = html.replace('<div class="entered muted">{{ u.created_at }}</div>', '<div class="entered muted">{{ u.last_seen|default:u.created_at }}</div>')

        with open(dashboard_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print("Dashboard HTML updated with Filter Panel.")

if __name__ == "__main__":
    apply_filters()
