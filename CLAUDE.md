# SpeedBot Chatbot - Project Documentation

## Overview
Django-based WhatsApp chatbot platform with multi-tenant support, AI-powered responses, and CRM features.

## Tech Stack
- **Backend**: Django 4.x, Python 3.10+
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Task Queue**: Celery + Redis
- **AI**: OpenAI ChatGPT integration
- **Messaging**: WhatsApp Business API via Meta
- **Scheduling**: Calendly integration
- **Server**: Gunicorn + Nginx on AWS EC2

## Project Structure
```
chatbot/
├── mynewsite/          # Django project settings
│   ├── settings.py
│   ├── urls.py         # Main URL routing
│   ├── celery.py       # Celery configuration
│   └── wsgi.py
├── newapp/             # Main application
│   ├── controllers/    # View controllers (MVC pattern)
│   │   ├── whatsapp.py       # WhatsApp webhook & messaging
│   │   ├── inbox.py          # Inbox/chat management
│   │   ├── contact.py        # Contact CRUD & search
│   │   ├── settings.py       # Settings management
│   │   ├── login.py          # Authentication
│   │   ├── broadcast.py      # Bulk messaging
│   │   ├── integration.py    # Third-party integrations
│   │   ├── superadmin_views.py  # Super admin portal
│   │   └── auth_views.py     # Auth helpers
│   ├── models.py       # Database models
│   ├── views.py        # Additional views
│   ├── tasks.py        # Celery async tasks
│   ├── templates/      # HTML templates
│   ├── static/         # CSS, JS, images
│   └── migrations/     # Database migrations
├── media/              # User uploads
└── manage.py
```

## Key Models
| Model | Purpose |
|-------|---------|
| `Organization` | Multi-tenant client company |
| `Admin` | Legacy single-tenant admin |
| `User` | WhatsApp contacts/customers |
| `Message` | Chat messages (user/bot) |
| `Tag` | Contact labels/categories |
| `UserTag` | Many-to-many user-tag relation |
| `Role` | Permission roles (super_admin, client_admin, agent, viewer) |
| `OrganizationUser` | Links Django User to Organization with Role |
| `FollowupSetting` | Automated follow-up configuration |
| `BroadcastJob` | Bulk message campaigns |
| `ImageAsset` | Reusable image assets |
| `ExternalAPI` | External API configurations |

## Authentication
Supports dual authentication:
1. **Organization-based** (new): `request.session.get("organization_id")`
2. **Admin-based** (legacy): `request.session.get("admin_id")`

Always check both in controllers for backward compatibility.

## Key API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/` | POST | WhatsApp incoming messages |
| `/api/contact/search/` | GET | Advanced contact search with pagination |
| `/api/user/tag/add/` | POST | Add tag to contact |
| `/api/user/tag/remove/` | POST | Remove tag from contact |
| `/api/inbox/upload_media/` | POST | Upload media files |
| `/api/broadcast/create/` | POST | Create broadcast campaign |
| `/api/calendly/*` | Various | Calendly booking integration |

## Development Commands
```bash
# Run development server
python manage.py runserver

# Run Celery worker
celery -A mynewsite worker -l info

# Run Celery beat (scheduler)
celery -A mynewsite beat -l info

# Database migrations
python manage.py makemigrations
python manage.py migrate
```

## AWS Deployment
```bash
# SSH to server
ssh -i key.pem ubuntu@your-ec2-ip

# Project location
cd ~/speedbot

# Pull & restart
git pull origin main
sudo systemctl restart chatbot celery celery-beat

# View logs
sudo journalctl -u chatbot -f
sudo journalctl -u celery -f
```

## Services (systemd)
| Service | Description |
|---------|-------------|
| `chatbot.service` | Gunicorn Django app (port 8000) |
| `celery.service` | Celery worker |
| `celery-beat.service` | Celery scheduler |

## Important Files
- `newapp/controllers/whatsapp.py` - Core WhatsApp logic (~83KB)
- `newapp/views.py` - Main views (~69KB)
- `newapp/models.py` - All database models
- `newapp/tasks.py` - Background tasks (follow-ups, broadcasts)
- `newapp/password_utils.py` - Secure password hashing (bcrypt)

## Code Patterns
1. **Controllers**: Use `@staticmethod` or `@csrf_exempt` decorators
2. **Multi-tenancy**: Always filter by `organization_id` OR `admin_id`
3. **API responses**: Return `JsonResponse` with `success` or `error` keys
4. **Validation**: Use `validate_phone_number()` and `validate_name()` from contact.py

## Environment Variables
- `SECRET_KEY` - Django secret
- `DATABASE_URL` - Database connection
- `REDIS_URL` - Redis for Celery
- `OPENAI_API_KEY` - ChatGPT integration
- `CALENDLY_API_KEY` - Calendly integration

## Common Tasks

### Add New API Endpoint
1. Add method to appropriate controller in `newapp/controllers/`
2. Add URL route in `mynewsite/urls.py`
3. Restart services on server

### Add New Model Field
1. Update `newapp/models.py`
2. Run `python manage.py makemigrations`
3. Run `python manage.py migrate`
4. Update related controllers/templates

### Debug WhatsApp Messages
1. Check `newapp/controllers/whatsapp.py` → `get_message()` method
2. View logs: `sudo journalctl -u chatbot -f`
3. Check Meta webhook configuration in WhatsApp Business settings

---

## Logging System

### Overview
SpeedBot uses a centralized logging system in `newapp/logging_config.py` for comprehensive tracking of all operations.

### Log Files Location
```bash
# On server
~/speedbot/logs/
├── webhook.log       # All incoming/outgoing WhatsApp messages
├── tasks.log         # Celery task execution (follow-ups, broadcasts)
├── auth.log          # Login/authentication events
├── api.log           # External API calls
└── combined.log      # All logs in one file
```

### Viewing Logs

```bash
# Real-time webhook logs
tail -f ~/speedbot/logs/webhook.log

# Real-time task logs (follow-ups)
tail -f ~/speedbot/logs/tasks.log

# Combined logs
tail -f ~/speedbot/logs/combined.log

# Search for specific phone number
grep "919876543210" ~/speedbot/logs/webhook.log

# Search for specific time range
grep "2026-02-03 18:" ~/speedbot/logs/webhook.log

# View last 100 follow-up events
grep "FOLLOWUP" ~/speedbot/logs/tasks.log | tail -100
```

### Log Format
```
2026-02-03 09:35:00 | 📝 INFO     | [INCOMING] 📨 type=text | from=919876543210 | source=phone_id=123456 | content=Hello...
2026-02-03 09:35:01 | 📝 INFO     | [OUTGOING] ✅ type=text | to=919876543210 | content=Welcome to SpeedBot...
2026-02-03 09:35:02 | 📝 INFO     | [FOLLOWUP] scheduled | phone=919876543210 | step=1 | delay=10min
```

### Log Levels
| Level | Emoji | Description |
|-------|-------|-------------|
| DEBUG | 🔍 | Detailed debugging info |
| INFO | 📝 | Normal operations |
| WARNING | ⚠️ | Potential issues |
| ERROR | ❌ | Errors that need attention |
| CRITICAL | 🔥 | Critical failures |

### Using Logging in Code
```python
from newapp.logging_config import get_logger, log_message_received, log_error

logger = get_logger('my_module')

# Log events
logger.info(f"Processing request for {phone}")
logger.error(f"API call failed: {error}")

# Helper functions
log_message_received(phone, msg_type='text', content='Hello')
log_error('whatsapp', exception, context={'phone': phone})
```

### Debugging Ghost Messages
If you see unexpected messages:
1. Check webhook log for the timestamp: `grep "18:40" ~/speedbot/logs/webhook.log`
2. Look for `msg_id` to trace the message source
3. Check if message came from Meta webhook replay (server downtime)
4. Verify `timestamp` field matches when message was actually sent

### Log Rotation
Logs are automatically rotated:
- Individual logs: 10MB max, 5 backups
- Combined log: 50MB max, 10 backups

### Practical Debugging Commands

```bash
# Find messages from a specific time (use Unix timestamp prefix)
grep "timestamp=177" ~/speedbot/logs/webhook.log

# Find all messages from a specific phone number
grep "from=919327606510" ~/speedbot/logs/webhook.log

# Check for duplicate messages that were skipped
grep "Skipping duplicate" ~/speedbot/logs/webhook.log

# View message delivery status
grep "status=" ~/speedbot/logs/webhook.log

# Find errors
grep "ERROR\|❌" ~/speedbot/logs/combined.log

# Track a specific message by ID
grep "wamid.HBgM" ~/speedbot/logs/webhook.log
```

---

## Deployment Update - 2026-05-04

Deployed commit: `e8095cc` (`Fix pipeline inbox and webchat sync issues`)

Fixes deployed:
- Pipeline opportunity amount edits now validate numeric input, persist as Decimal, return updated totals, and refresh the visible board card/stage amount without a full page reload.
- Inbox tag add/remove endpoints were added at `/api/inbox/user_tag/add/` and `/api/inbox/user_tag/remove/`; both support tag names from the inbox panel and trigger pipeline automations.
- Contact tag removal now triggers `tag_removed` pipeline automations.
- Inbox email editing now persists through the existing `CustomField`/`CustomFieldValue` system instead of pretending `User.email` exists.
- Inbox archive now preserves messages, tags, custom fields, logs, and opportunities; it only hides the contact from inbox and cancels pending follow-ups.
- Webchat visitor emails are stored in the email custom field when provided.
- Webchat AI responses now process `{{custom_field:name:value}}` tags for linked webchat users.
- Test chat now respects the selected `prompt_id`, creates/links a test inbox user, mirrors test messages into inbox, persists detected tags/custom fields, and sends the selected prompt for audio tests too.

Validation:
- Local syntax check passed with `python -m py_compile` for all changed Python files.
- Local `python manage.py check` could not run because local Python does not have Django installed.
- Server check passed: `cd /home/ubuntu/speedbot && source venv/bin/activate && python manage.py check`.
- Server smoke check after reload returned HTTP `302` from `http://127.0.0.1:8000/`.

Deployment actions:
- Pushed `main` to `origin`.
- Pulled on server with `git pull origin main`.
- No migration was required.
- Reloaded Django Gunicorn master PID `511076` with `kill -HUP 511076`.
- Confirmed Django Gunicorn workers restarted under master PID `511076`.

Local SSH key note:
- Older docs mention `C:\Users\Meet\Downloads\speedbot-key.pem`.
- On this workstation the key was found at `C:\Users\Meet Vaghasiya\.ssh\speedbot-key.pem`.

### Sample Log Output
```
2026-02-03 09:39:23 | 🔍 DEBUG    | [RAW_WEBHOOK] Received data: {"object": "whatsapp_business_account"...
2026-02-03 09:39:23 | 📝 INFO     | [INCOMING] 📨 type=text | from=919327606510 | source=phone_id=811624148710340 | content=hello buddy...
2026-02-03 09:39:23 | 📝 INFO     | 📨 [INCOMING] msg_id=wamid.HBgM... | from=919327606510 | type=text | timestamp=1770091761 | creds_source=organization
```


