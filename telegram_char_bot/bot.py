#!/usr/bin/env python3
"""Telegram bot that counts characters and stores both sides of a chat in Supabase."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
STATE_FILE = BASE_DIR / "bot_state.json"
POLL_TIMEOUT_SECONDS = 30


def safe_url(url: str) -> str:
    """Remove a Telegram bot token from diagnostic messages."""
    telegram_prefix = "https://api.telegram.org/bot"
    if url.startswith(telegram_prefix):
        method = url.rsplit("/", 1)[-1]
        return "{0}<redacted>/{1}".format(telegram_prefix, method)
    return url


def load_env(path: Path) -> None:
    """Load simple KEY=value entries without overwriting shell variables."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError("Set {0} in {1}".format(name, ENV_FILE))
    return value


def request_json(url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None, timeout: int = 45) -> Any:
    body = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read().decode("utf-8")
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError("HTTP {0} for {1}: {2}".format(error.code, safe_url(url), details)) from error
    except URLError as error:
        raise RuntimeError("Request failed for {0}: {1}".format(safe_url(url), error.reason)) from error

    return json.loads(data) if data else None


class TelegramCharacterBot:
    def __init__(self, token: str, supabase_url: str, service_role_key: str) -> None:
        self.telegram_url = "https://api.telegram.org/bot{0}".format(token)
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_headers = {
            "apikey": service_role_key,
            "Authorization": "Bearer {0}".format(service_role_key),
            "Prefer": "return=minimal",
        }
        self.bot_username: Optional[str] = None
        self.offset = self.load_offset()

    def load_offset(self) -> Optional[int]:
        if not STATE_FILE.exists():
            return None
        try:
            return int(json.loads(STATE_FILE.read_text(encoding="utf-8"))["offset"])
        except (ValueError, KeyError, json.JSONDecodeError):
            return None

    def save_offset(self, offset: int) -> None:
        temporary_path = STATE_FILE.with_suffix(".tmp")
        temporary_path.write_text(json.dumps({"offset": offset}), encoding="utf-8")
        temporary_path.replace(STATE_FILE)
        self.offset = offset

    def telegram(self, method: str, payload: Optional[Dict[str, Any]] = None,
                 timeout: int = 45) -> Any:
        result = request_json(
            "{0}/{1}".format(self.telegram_url, method),
            method="POST",
            payload=payload,
            timeout=timeout,
        )
        if not result.get("ok"):
            raise RuntimeError("Telegram {0} failed: {1}".format(method, result))
        return result["result"]

    def log_message(self, username: Optional[str], sender_type: str, message: str) -> None:
        request_json(
            "{0}/rest/v1/chat_logs".format(self.supabase_url),
            method="POST",
            payload={
                "telegram_username": username,
                "sender_type": sender_type,
                "message": message,
            },
            headers=self.supabase_headers,
        )

    def get_bot_username(self) -> str:
        profile = self.telegram("getMe")
        username = profile.get("username")
        if not username:
            raise RuntimeError("The Telegram bot must have a username.")
        return username

    @staticmethod
    def describe_non_text_message(message: Dict[str, Any]) -> str:
        for key in ("sticker", "photo", "video", "document", "voice", "audio", "animation"):
            if key in message:
                return "[{0}]".format(key)
        return "[non-text message]"

    def process_update(self, update: Dict[str, Any]) -> None:
        message = update.get("message")
        if not message:
            return

        chat = message.get("chat", {})
        sender = message.get("from", {})
        chat_id = chat.get("id")
        if chat_id is None:
            return

        username = sender.get("username")
        user_message = message.get("text")
        if user_message is None:
            user_message = self.describe_non_text_message(message)
            reply = "Я умею считать символы только в текстовых сообщениях."
        else:
            reply = "Количество символов: {0}".format(len(user_message))

        self.log_message(username, "user", user_message)
        self.telegram("sendMessage", {"chat_id": chat_id, "text": reply})
        self.log_message(self.bot_username, "bot", reply)

    def run(self) -> None:
        self.bot_username = self.get_bot_username()
        print("Bot @{0} is running. Press Ctrl+C to stop.".format(self.bot_username), flush=True)
        while True:
            payload: Dict[str, Any] = {
                "timeout": POLL_TIMEOUT_SECONDS,
                "allowed_updates": ["message"],
            }
            if self.offset is not None:
                payload["offset"] = self.offset

            try:
                updates = self.telegram("getUpdates", payload, timeout=POLL_TIMEOUT_SECONDS + 15)
                for update in updates:
                    update_id = update.get("update_id")
                    self.process_update(update)
                    if update_id is not None:
                        self.save_offset(int(update_id) + 1)
            except (RuntimeError, OSError) as error:
                print("Temporary error: {0}".format(error), file=sys.stderr, flush=True)
                time.sleep(3)


def main() -> None:
    load_env(ENV_FILE)
    bot = TelegramCharacterBot(
        token=require_env("TELEGRAM_BOT_TOKEN"),
        supabase_url=require_env("SUPABASE_URL"),
        service_role_key=require_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    bot.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped.")
    except RuntimeError as error:
        print("Configuration error: {0}".format(error), file=sys.stderr)
        raise SystemExit(1)
