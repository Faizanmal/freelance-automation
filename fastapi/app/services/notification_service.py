from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Protocol
import asyncio
import base64
import json
import os
import random
import smtplib
import urllib.parse
import urllib.request


class NotificationChannel(str, Enum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    EMAIL = "email"
    SLACK = "slack"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass(slots=True)
class NotificationAction:
    id: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NotificationPayload:
    user_id: str
    title: str
    body: str
    channels: list[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    digest: bool = False
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    ai_summary: str | None = None
    actions: list[NotificationAction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    destinations: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class NotificationResult:
    channel: NotificationChannel
    delivered: bool
    message_id: str | None = None
    error: str | None = None


@dataclass(slots=True)
class NotificationEnvelope:
    id: str
    user_id: str
    title: str
    body: str
    channels: list[NotificationChannel]
    priority: NotificationPriority
    digest: bool
    ai_summary: str | None
    actions: list[NotificationAction]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "queued"
    attempts: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    destinations: dict[str, str] = field(default_factory=dict)


class DeliveryAdapter(Protocol):
    async def send(self, envelope: NotificationEnvelope) -> NotificationResult:
        ...


def _destinations(envelope: NotificationEnvelope) -> dict[str, str]:
    return envelope.destinations or {}


class SimulatedAdapter:
    async def send(self, envelope: NotificationEnvelope) -> NotificationResult:
        await asyncio.sleep(0.01)
        return NotificationResult(
            channel=envelope.channels[0],
            delivered=True,
            message_id=f"simulated-{random.randint(1, 100000)}",
        )


class WebhookAdapter:
    def __init__(self, endpoint: str | None, channel: NotificationChannel, destination_key: str) -> None:
        self.endpoint = endpoint
        self.channel = channel
        self.destination_key = destination_key

    def _resolve_endpoint(self, envelope: NotificationEnvelope) -> str | None:
        return _destinations(envelope).get(self.destination_key) or self.endpoint

    async def send(self, envelope: NotificationEnvelope) -> NotificationResult:
        endpoint = self._resolve_endpoint(envelope)
        if not endpoint:
            return NotificationResult(channel=self.channel, delivered=False, error="provider_not_configured")
        try:
            payload = json.dumps({"text": f"{envelope.title}\n{envelope.body}"}).encode("utf-8")
            request = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status < 400:
                    return NotificationResult(channel=self.channel, delivered=True, message_id=str(response.status))
        except Exception as exc:  # pragma: no cover - network path
            return NotificationResult(channel=self.channel, delivered=False, error=str(exc))
        return NotificationResult(channel=self.channel, delivered=False, error="provider_error")


class TelegramAdapter:
    def __init__(self) -> None:
        self.channel = NotificationChannel.TELEGRAM
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")

    async def send(self, envelope: NotificationEnvelope) -> NotificationResult:
        chat_id = _destinations(envelope).get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
        if not (self.token and chat_id):
            return NotificationResult(channel=self.channel, delivered=False, error="provider_not_configured")
        try:
            endpoint = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = json.dumps({"chat_id": chat_id, "text": f"{envelope.title}\n{envelope.body}"}).encode("utf-8")
            request = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status < 400:
                    return NotificationResult(channel=self.channel, delivered=True, message_id=str(response.status))
        except Exception as exc:  # pragma: no cover - network path
            return NotificationResult(channel=self.channel, delivered=False, error=str(exc))
        return NotificationResult(channel=self.channel, delivered=False, error="provider_error")


class SlackAdapter(WebhookAdapter):
    def __init__(self) -> None:
        super().__init__(os.getenv("SLACK_WEBHOOK_URL"), NotificationChannel.SLACK, "slack_webhook_url")


class DiscordAdapter(WebhookAdapter):
    def __init__(self) -> None:
        super().__init__(os.getenv("DISCORD_WEBHOOK_URL"), NotificationChannel.DISCORD, "discord_webhook_url")


class WhatsAppAdapter:
    def __init__(self) -> None:
        self.channel = NotificationChannel.WHATSAPP

    async def send(self, envelope: NotificationEnvelope) -> NotificationResult:
        account_sid = os.getenv("WHATSAPP_TWILIO_SID")
        auth_token = os.getenv("WHATSAPP_TWILIO_TOKEN")
        from_number = os.getenv("WHATSAPP_TWILIO_FROM")
        to_number = _destinations(envelope).get("whatsapp_to") or os.getenv("WHATSAPP_TO")
        if not (account_sid and auth_token and from_number and to_number):
            return NotificationResult(channel=self.channel, delivered=False, error="provider_not_configured")
        try:
            payload = urllib.parse.urlencode(
                {"To": to_number, "From": from_number, "Body": f"{envelope.title}\n{envelope.body}"}
            ).encode("utf-8")
            credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
            request = urllib.request.Request(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                data=payload,
                headers={"Authorization": f"Basic {credentials}"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status < 400:
                    return NotificationResult(channel=self.channel, delivered=True, message_id=str(response.status))
        except Exception as exc:  # pragma: no cover - network path
            return NotificationResult(channel=self.channel, delivered=False, error=str(exc))
        return NotificationResult(channel=self.channel, delivered=False, error="provider_error")


class EmailAdapter:
    def __init__(self) -> None:
        self.channel = NotificationChannel.EMAIL

    async def send(self, envelope: NotificationEnvelope) -> NotificationResult:
        smtp_host = os.getenv("EMAIL_SMTP_HOST")
        smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        username = os.getenv("EMAIL_USERNAME")
        password = os.getenv("EMAIL_PASSWORD")
        from_address = os.getenv("EMAIL_FROM")
        to_address = _destinations(envelope).get("email") or os.getenv("EMAIL_TO") or username
        if not (smtp_host and username and password and from_address and to_address):
            return NotificationResult(channel=self.channel, delivered=False, error="provider_not_configured")
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as smtp:
                smtp.starttls()
                smtp.login(username, password)
                message = f"Subject: {envelope.title}\n\n{envelope.body}"
                smtp.sendmail(from_address, [to_address], message)
            return NotificationResult(channel=self.channel, delivered=True, message_id="smtp")
        except Exception as exc:  # pragma: no cover - network path
            return NotificationResult(channel=self.channel, delivered=False, error=str(exc))


class NotificationService:
    def __init__(
        self,
        adapter: DeliveryAdapter | None = None,
        rate_limit_per_user: int = 10,
        rate_limit_window_seconds: int = 60,
    ) -> None:
        self.adapter = adapter
        self.rate_limit_per_user = rate_limit_per_user
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self._channel_adapters: dict[NotificationChannel, DeliveryAdapter] = {
            NotificationChannel.TELEGRAM: TelegramAdapter(),
            NotificationChannel.WHATSAPP: WhatsAppAdapter(),
            NotificationChannel.DISCORD: DiscordAdapter(),
            NotificationChannel.EMAIL: EmailAdapter(),
            NotificationChannel.SLACK: SlackAdapter(),
        }
        self._retry_queue: list[NotificationEnvelope] = []
        self._history: list[NotificationEnvelope] = []
        self._rate_limit_state: dict[str, deque[datetime]] = {}

    async def dispatch(self, payload: NotificationPayload) -> list[NotificationResult]:
        envelope = NotificationEnvelope(
            id=f"notif-{random.randint(1, 1000000)}",
            user_id=payload.user_id,
            title=payload.title,
            body=payload.body,
            channels=payload.channels,
            priority=payload.priority,
            digest=payload.digest,
            ai_summary=payload.ai_summary,
            actions=payload.actions,
            metadata=payload.metadata,
            destinations=payload.destinations,
        )
        self._history.append(envelope)
        if self._is_rate_limited(payload.user_id):
            envelope.status = "rate-limited"
            envelope.last_error = "rate_limited"
            return [NotificationResult(channel=channel, delivered=False, error="rate_limited") for channel in payload.channels]
        if self._should_quiet_hours(payload):
            envelope.status = "quiet-hours"
            self._retry_queue.append(envelope)
            return []

        results: list[NotificationResult] = []
        for channel in payload.channels:
            adapter = self.adapter or self._channel_adapters.get(channel, SimulatedAdapter())
            result = await adapter.send(
                NotificationEnvelope(
                    id=envelope.id,
                    user_id=envelope.user_id,
                    title=envelope.title,
                    body=envelope.body,
                    channels=[channel],
                    priority=envelope.priority,
                    digest=envelope.digest,
                    ai_summary=envelope.ai_summary,
                    actions=envelope.actions,
                    metadata=envelope.metadata,
                    destinations=envelope.destinations,
                )
            )
            results.append(result)
        envelope.status = "sent" if all(result.delivered for result in results) else "failed"
        return results

    async def retry_failed(self) -> list[NotificationEnvelope]:
        retried: list[NotificationEnvelope] = []
        while self._retry_queue:
            envelope = self._retry_queue.pop(0)
            envelope.attempts += 1
            envelope.status = "retrying"
            retried.append(envelope)
        return retried

    def get_history(self, user_id: str) -> list[NotificationEnvelope]:
        return [entry for entry in self._history if entry.user_id == user_id]

    def get_retry_queue(self) -> list[NotificationEnvelope]:
        return list(self._retry_queue)

    def _should_quiet_hours(self, payload: NotificationPayload) -> bool:
        now = datetime.now(timezone.utc).time()
        if payload.quiet_hours_start is None or payload.quiet_hours_end is None:
            return False
        if payload.quiet_hours_start <= payload.quiet_hours_end:
            return payload.quiet_hours_start <= now <= payload.quiet_hours_end
        return now >= payload.quiet_hours_start or now <= payload.quiet_hours_end

    def _is_rate_limited(self, user_id: str) -> bool:
        now = datetime.now(timezone.utc)
        bucket = self._rate_limit_state.setdefault(user_id, deque())
        while bucket and now - bucket[0] > timedelta(seconds=self.rate_limit_window_seconds):
            bucket.popleft()
        if len(bucket) >= self.rate_limit_per_user:
            return True
        bucket.append(now)
        return False

    def build_ai_summary(self, title: str, body: str) -> str:
        return f"AI summary: {title} — {body[:120]}"

    def build_digest(self, items: list[NotificationPayload]) -> NotificationPayload:
        joined = " | ".join(f"{item.title}: {item.body}" for item in items)
        destinations = items[0].destinations if items else {}
        return NotificationPayload(
            user_id=items[0].user_id if items else "system",
            title="Daily digest",
            body=joined,
            channels=[NotificationChannel.EMAIL],
            priority=NotificationPriority.NORMAL,
            digest=True,
            ai_summary=self.build_ai_summary("Daily digest", joined),
            destinations=destinations,
        )
