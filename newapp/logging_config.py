"""
Centralized Logging Configuration for SpeedBot
===============================================
This module provides comprehensive logging for all chatbot operations.

Usage:
    from newapp.logging_config import get_logger
    logger = get_logger('whatsapp')
    logger.info("Message received", extra={'phone': phone, 'message_type': 'text'})
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)


class DetailedFormatter(logging.Formatter):
    """Custom formatter with emoji indicators and structured output."""
    
    LEVEL_EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '📝',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🔥',
    }
    
    def format(self, record):
        emoji = self.LEVEL_EMOJIS.get(record.levelname, '•')
        record.emoji = emoji
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for the specified module.
    
    Args:
        name: Logger name (e.g., 'whatsapp', 'tasks', 'login')
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f'speedbot.{name}')
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # File handler - detailed logs with rotation
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, f'{name}.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = DetailedFormatter(
        '%(asctime)s | %(emoji)s %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler - info and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = DetailedFormatter(
        '%(emoji)s [%(name)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Combined log file for all modules
    combined_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'combined.log'),
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    combined_handler.setLevel(logging.DEBUG)
    combined_handler.setFormatter(file_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(combined_handler)
    
    return logger


# Pre-configured loggers for common modules
webhook_logger = get_logger('webhook')
task_logger = get_logger('tasks')
auth_logger = get_logger('auth')
api_logger = get_logger('api')


def log_webhook_event(event_type: str, phone: str, data: dict = None):
    """
    Log a webhook event with structured data.
    
    Args:
        event_type: Type of event (message_received, message_sent, status_update, etc.)
        phone: Phone number involved
        data: Additional event data
    """
    webhook_logger.info(
        f"[WEBHOOK] {event_type} | phone={phone} | data={data or {}}"
    )


def log_message_received(phone: str, msg_type: str, content: str = None, source: str = None):
    """Log an incoming message with full details."""
    webhook_logger.info(
        f"[INCOMING] 📨 type={msg_type} | from={phone} | source={source} | content={content[:100] if content else 'N/A'}..."
    )


def log_message_sent(phone: str, msg_type: str, content: str = None, success: bool = True):
    """Log an outgoing message."""
    status = "✅" if success else "❌"
    webhook_logger.info(
        f"[OUTGOING] {status} type={msg_type} | to={phone} | content={content[:100] if content else 'N/A'}..."
    )


def log_followup_event(event_type: str, phone: str, step: int = None, details: str = None):
    """Log follow-up related events."""
    task_logger.info(
        f"[FOLLOWUP] {event_type} | phone={phone} | step={step} | {details or ''}"
    )


def log_api_call(api_name: str, method: str, url: str, status: int = None, response: str = None):
    """Log external API calls."""
    api_logger.info(
        f"[API] {api_name} | {method} {url} | status={status} | response={response[:200] if response else 'N/A'}..."
    )


def log_error(module: str, error: Exception, context: dict = None):
    """Log an error with full context."""
    logger = get_logger(module)
    logger.error(
        f"[ERROR] {type(error).__name__}: {str(error)} | context={context or {}}",
        exc_info=True
    )
