import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mynewsite.settings")

app = Celery("mynewsite")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

# Celery Beat Schedule - Periodic Tasks
app.conf.beat_schedule = {
    'process-pending-followups': {
        'task': 'newapp.tasks.process_pending_followups',
        'schedule': 60.0,  # Run every 60 seconds
    },
}
