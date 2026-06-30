"""Telegram notification sender."""

from __future__ import annotations

import httpx

from assemblix_api.core.settings import get_settings

TELEGRAM_API_TIMEOUT = 10.0
DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class TelegramSender:
    """Sends a message via the Telegram Bot API (sendMessage)."""

    async def send(self, data: dict, message: str) -> None:
        bot_token = data["bot_token"]
        chat_id = data["chat_id"]

        base_url = self._resolve_base_url()
        url = f"{base_url}/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        async with httpx.AsyncClient(timeout=TELEGRAM_API_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    @staticmethod
    def _resolve_base_url() -> str:
        """Telegram Bot API base URL: custom override (TELEGRAM_API_BASE_URL) or public default."""
        custom_base_url = get_settings().telegram_api_base_url.strip()
        base_url = custom_base_url or DEFAULT_TELEGRAM_API_BASE_URL
        return base_url.rstrip("/")
