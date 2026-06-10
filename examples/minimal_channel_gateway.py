from __future__ import annotations

import json
import sys
import urllib.request


SERVER = "http://127.0.0.1:8787/gateway/events"


def send(user_id: str, text: str, display_name: str | None = None, private: bool = False) -> None:
    payload = {
        "channel_id": "demo-table",
        "user_id": user_id,
        "display_name": display_name or user_id,
        "text": text,
        "is_private": private,
    }
    request = urllib.request.Request(
        SERVER,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python examples/minimal_channel_gateway.py <user_id> <text> [display_name]")
        raise SystemExit(2)
    send(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
