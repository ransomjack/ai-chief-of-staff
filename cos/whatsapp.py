"""WhatsApp Cloud API (Meta's official API): check that a webhook really came from
Meta, read incoming messages, send replies, download voice notes."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict, dataclass

import requests

GRAPH = "https://graph.facebook.com"
MAX_TEXT = 4000  # WhatsApp allows 4096 characters per text message


def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """Meta signs every webhook with the app secret (X-Hub-Signature-256).
    Anything without a valid signature is rejected."""
    if not header or not header.startswith("sha256=") or not app_secret:
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


@dataclass
class Inbound:
    id: str
    sender: str
    kind: str  # "text", "audio" or "other"
    text: str = ""
    media_id: str = ""
    mime: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_webhook(payload: dict) -> list[Inbound]:
    """Pull user messages out of a webhook payload. Delivery/read statuses are ignored."""
    found: list[Inbound] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for m in value.get("messages", []) or []:
                kind = m.get("type", "")
                item = Inbound(id=m.get("id", ""), sender=m.get("from", ""), kind="other",
                               timestamp=m.get("timestamp", ""))
                if kind == "text":
                    item.kind, item.text = "text", (m.get("text") or {}).get("body", "")
                elif kind == "audio":
                    audio = m.get("audio") or {}
                    item.kind, item.media_id, item.mime = "audio", audio.get("id", ""), audio.get("mime_type", "")
                elif kind == "button":  # quick-reply button on a template
                    item.kind, item.text = "text", (m.get("button") or {}).get("text", "")
                elif kind == "interactive":
                    inter = m.get("interactive") or {}
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    item.kind, item.text = "text", reply.get("title", "")
                if item.id and item.sender:
                    found.append(item)
    return found


def chunk(text: str, size: int = MAX_TEXT) -> list[str]:
    text = text.strip() or "(empty reply)"
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        cut = cut if cut > size // 2 else size
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    parts.append(text)
    return parts


def one_line(text: str, limit: int = 900) -> str:
    """Template parameters may not contain new lines, tabs or long runs of spaces."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str, version: str = "v23.0",
                 session: requests.Session | None = None):
        self.token = token
        self.phone_number_id = phone_number_id
        self.version = version
        self.http = session or requests.Session()

    @property
    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def _post(self, body: dict) -> dict:
        url = f"{GRAPH}/{self.version}/{self.phone_number_id}/messages"
        resp = self.http.post(url, json=body, headers=self._auth, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def send_text(self, to: str, body: str) -> None:
        for part in chunk(body):
            self._post({"messaging_product": "whatsapp", "to": to, "type": "text",
                        "text": {"body": part, "preview_url": False}})

    def send_template(self, to: str, name: str, lang: str, params: list[str] | None = None) -> None:
        template: dict = {"name": name, "language": {"code": lang}}
        if params:
            template["components"] = [{"type": "body", "parameters": [
                {"type": "text", "text": one_line(p)} for p in params]}]
        self._post({"messaging_product": "whatsapp", "to": to, "type": "template", "template": template})

    def mark_read(self, message_id: str) -> None:
        self._post({"messaging_product": "whatsapp", "status": "read", "message_id": message_id})

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        meta = self.http.get(f"{GRAPH}/{self.version}/{media_id}", headers=self._auth, timeout=20)
        meta.raise_for_status()
        info = meta.json()
        data = self.http.get(info["url"], headers=self._auth, timeout=60)
        data.raise_for_status()
        return data.content, info.get("mime_type", "audio/ogg")
