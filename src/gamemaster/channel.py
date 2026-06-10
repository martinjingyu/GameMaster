from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .agent import OutboundMessage


@dataclass
class ChannelGatewayClient:
    url: str | None = None
    token: str | None = None
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "ChannelGatewayClient":
        return cls(
            url=os.getenv("CHANNEL_GATEWAY_URL"),
            token=os.getenv("CHANNEL_GATEWAY_TOKEN"),
        )

    def send(self, messages: list[OutboundMessage]) -> None:
        if not self.url or not messages:
            return
        payload = json.dumps(
            {"messages": [message.to_dict() for message in messages]},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=payload,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Channel Gateway send failed: {exc}") from exc

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
