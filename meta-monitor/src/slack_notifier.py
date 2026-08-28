from __future__ import annotations

from typing import Any

import requests


class SlackNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(
        self,
        fallback_text: str,
        *,
        text: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"text": fallback_text}
        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks
        response = requests.post(self.webhook_url, json=payload, timeout=30)
        response.raise_for_status()
