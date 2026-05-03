import requests

from config import settings
from utils.logger import get_logger

log = get_logger()


def send_telegram(message: str):

    if not settings.TELEGRAM_ENABLED:
        return

    try:

        url = (
            f"https://api.telegram.org/bot"
            f"{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }

        requests.post(url, json=payload, timeout=10)

    except Exception as e:
        log.error(f"Telegram error: {e}")