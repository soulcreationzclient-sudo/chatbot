# SpeedBots - WhatsApp FAQ Chatbot

A Django-based WhatsApp chatbot platform with AI-powered FAQ responses, Calendly integration, PDF/Image analysis, and automated follow-up messages.

## Features

- **FAQ Chatbot**: AI-powered responses using OpenAI GPT
- **Calendly Integration**: Automatic appointment booking via WhatsApp
- **PDF/Image Analysis**: Extract and analyze content from documents and images
- **Automated Follow-ups**: Configurable timed follow-up messages
- **Inbox Dashboard**: View and manage all conversations
- **Multi-tenant**: Supports multiple admin accounts

## Tech Stack

- **Backend**: Django 4.2
- **Task Queue**: Celery + Redis (Upstash)
- **AI**: OpenAI GPT API
- **Messaging**: WhatsApp Business API (Meta)
- **Appointments**: Calendly API
- **Database**: SQLite (dev) / MySQL (prod)

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/meet0209/chatbot.git
cd chatbot
pip install -r requirements.txt
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Start Services

```bash
# Terminal 1 - Django Server
python manage.py runserver

# Terminal 2 - Celery Worker (for follow-ups)
python -m celery -A mynewsite worker -l info --pool=solo

# Terminal 3 - Ngrok (for WhatsApp webhook)
ngrok http 8000
```

### 4. Access Dashboard

- **URL**: http://127.0.0.1:8000
- **Login**: Use your admin credentials

---

## Configuration

### Settings > Integration

| Integration | Purpose |
|-------------|---------|
| **ChatGPT** | AI responses - Enter OpenAI API key and prompt |
| **Calendly** | Appointment booking - Enter PAT and scheduling URL |
| **Pinecone** | Vector search (optional) |

### Follow-up Settings (in Calendly modal)

- **Delay**: 1-60 minutes between follow-ups
- **Enable/Disable**: Toggle follow-up messages

---

## WhatsApp Setup

1. Create Meta Developer App at https://developers.facebook.com
2. Add WhatsApp Business product
3. Get Phone Number ID and Access Token
4. Configure webhook URL: `https://your-ngrok-url/get_message/`
5. Add webhook subscriptions: `messages`

---

## Project Structure

```
chatbot/
├── mynewsite/           # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── newapp/
│   ├── controllers/
│   │   ├── whatsapp.py  # Main message handler
│   │   ├── inbox.py     # Inbox dashboard
│   │   └── settings.py  # Settings pages
│   ├── templates/       # HTML templates
│   ├── models.py        # Database models
│   ├── tasks.py         # Celery tasks (follow-ups)
│   ├── calendly_views.py
│   └── calendly_integration_views.py
└── manage.py
```

---

## Environment Variables

For production, move these to environment variables:

```
OPENAI_API_KEY=your_openai_key
CELERY_BROKER_URL=redis://...
CALENDLY_ACCESS_TOKEN=your_calendly_pat
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/get_message/` | POST | WhatsApp webhook |
| `/connect_calendly/` | POST | Connect Calendly |
| `/disconnect_calendly/` | POST | Disconnect Calendly |
| `/update_followup_settings/` | POST | Update follow-up timing |

---

## License

Private - All rights reserved

---

## Support

Contact: meet0209
