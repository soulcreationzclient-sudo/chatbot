import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from django.db import connection

print("=== Applying WebChat Migration ===")
print("")

cursor = connection.cursor()

# Create tables
tables_sql = [
    # WebChatSession table
    """
    CREATE TABLE IF NOT EXISTS webchat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anonymous_id VARCHAR(100),
        session_id VARCHAR(100) UNIQUE NOT NULL,
        status VARCHAR(20) DEFAULT 'active',
        language VARCHAR(10) DEFAULT 'en',
        visitor_name VARCHAR(100),
        visitor_email VARCHAR(254),
        ip_address VARCHAR(45),
        user_agent TEXT,
        started_at DATETIME NOT NULL,
        last_activity DATETIME NOT NULL,
        ended_at DATETIME,
        message_count INTEGER DEFAULT 0,
        admin_id INTEGER,
        organization_id INTEGER,
        user_id INTEGER,
        FOREIGN KEY (admin_id) REFERENCES newapp_admin(id) ON DELETE CASCADE,
        FOREIGN KEY (organization_id) REFERENCES newapp_organization(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES newapp_user(id) ON DELETE CASCADE
    )
    """,

    # WebChatMessage table
    """
    CREATE TABLE IF NOT EXISTS webchat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        content_type VARCHAR(20) DEFAULT 'text',
        sender VARCHAR(20) DEFAULT 'user',
        ai_response TEXT,
        attachment_url VARCHAR(200),
        attachment_name VARCHAR(255),
        created_at DATETIME NOT NULL,
        parent_id INTEGER,
        session_id INTEGER NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES webchat_messages(id) ON DELETE CASCADE,
        FOREIGN KEY (session_id) REFERENCES webchat_sessions(id) ON DELETE CASCADE
    )
    """,

    # WebChatWidget table
    """
    CREATE TABLE IF NOT EXISTS webchat_widgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        website_url VARCHAR(500),
        display_mode VARCHAR(20) DEFAULT 'button',
        theme VARCHAR(20) DEFAULT 'light',
        primary_color VARCHAR(7) DEFAULT '#007bff',
        secondary_color VARCHAR(7) DEFAULT '#6c757d',
        text_color VARCHAR(7) DEFAULT '#000000',
        background_color VARCHAR(7) DEFAULT '#ffffff',
        position VARCHAR(20) DEFAULT 'bottom-right',
        initial_greeting TEXT,
        offline_message TEXT,
        welcome_en TEXT DEFAULT 'Welcome! How can we help you today?',
        welcome_ar TEXT DEFAULT 'مرحبا! كيف يمكننا مساعدتك اليوم؟',
        show_language_selector BOOLEAN DEFAULT 1,
        default_language VARCHAR(10) DEFAULT 'en',
        file_uploads_enabled BOOLEAN DEFAULT 1,
        voice_input_enabled BOOLEAN DEFAULT 1,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        embed_code TEXT,
        admin_id INTEGER,
        organization_id INTEGER,
        FOREIGN KEY (admin_id) REFERENCES newapp_admin(id) ON DELETE CASCADE,
        FOREIGN KEY (organization_id) REFERENCES newapp_organization(id) ON DELETE CASCADE
    )
    """,

    # WebChatAnalytics table
    """
    CREATE TABLE IF NOT EXISTS webchat_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_time_seconds INTEGER,
        message_count INTEGER DEFAULT 0,
        session_duration_seconds INTEGER,
        was_escalated BOOLEAN DEFAULT 0,
        user_feedback VARCHAR(20) DEFAULT '',
        created_at DATETIME NOT NULL,
        session_id INTEGER NOT NULL,
        FOREIGN KEY (session_id) REFERENCES webchat_sessions(id) ON DELETE CASCADE
    )
    """,
]

for i, sql in enumerate(tables_sql):
    sql = sql.strip()
    if sql:
        try:
            cursor.execute(sql)
            print(f"✅ Created table (operation {i+1}/4)")
        except Exception as e:
            if 'already exists' in str(e).lower():
                print(f"⚠️  Table already exists (operation {i+1})")
            else:
                print(f"❌ Error (operation {i+1}): {e}")

print("")
print("=== Adding indexes ===")

# Add indexes
indexes = [
    "CREATE INDEX IF NOT EXISTS webchat_sess_session_idx ON webchat_sessions(session_id)",
    "CREATE INDEX IF NOT EXISTS webchat_sess_status_idx ON webchat_sessions(status, last_activity)",
    "CREATE INDEX IF NOT EXISTS webchat_sess_user_idx ON webchat_sessions(user_id, started_at)",
    "CREATE INDEX IF NOT EXISTS webchat_msg_session_idx ON webchat_messages(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS webchat_msg_sender_idx ON webchat_messages(sender, created_at)",
]

for idx_sql in indexes:
    try:
        cursor.execute(idx_sql)
        print(f"✅ Index created")
    except Exception as e:
        if 'already exists' in str(e).lower():
            print(f"⚠️  Index already exists")
        else:
            print(f"❌ Index error: {e}")

print("")
print("=== Adding unique constraint for widgets ===")

try:
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS webchat_widget_admin_name ON webchat_widgets(admin_id, name)")
    print("✅ Unique index for widgets created")
except Exception as e:
    print(f"⚠️  Widget index: {e}")

try:
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS webchat_widget_org_name ON webchat_widgets(organization_id, name)")
    print("✅ Unique index for widgets (org) created")
except Exception as e:
    print(f"⚠️  Widget org index: {e}")

print("")
print("=== Verifying Tables ===")

# Verify tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'webchat%'")
tables = cursor.fetchall()
if tables:
    print("✅ All webchat tables created successfully:")
    for table in tables:
        # Get row count
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"   - {table[0]}: {count} records")
        except:
            print(f"   - {table[0]}")
else:
    print("❌ No webchat tables found!")

print("")
print("=== Migration Complete ===")
