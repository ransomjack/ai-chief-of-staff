"""What each Azure Function actually does, kept free of Azure code so it can be tested."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .clock import to_iso, window_open
from .store import Store
from .whatsapp import Inbound, WhatsAppClient

log = logging.getLogger("cos")
MAX_ATTEMPTS = 3
BRIEF_WORDS = {"brief", "/brief", "morning brief", "show brief"}
RESET_WORDS = {"/reset", "reset chat"}


@dataclass
class Deps:
    store: Store
    wa: WhatsAppClient
    owner_number: str
    reminder_template: str
    checkin_template: str
    template_lang: str
    now: Callable[[], datetime]
    agent: Any = None
    brief: Callable[[], str] | None = None
    transcribe: Callable[[bytes, str], str] | None = None


def handle_inbound(item: Inbound, d: Deps) -> str | None:
    """Handle one WhatsApp message from the owner. Returns the reply sent (for tests)."""
    if item.sender != d.owner_number:
        log.warning("Ignored message from a number that is not the owner")
        return None
    if d.store.seen(item.id):
        return None
    d.store.set_state("last_inbound_at", to_iso(d.now()))
    try:
        d.wa.mark_read(item.id)
    except Exception:
        pass

    try:
        text, prefix = item.text, ""
        if item.kind == "audio":
            if not d.transcribe:
                return _send(d, "Voice notes aren't switched on yet. Please type it for now.")
            audio, mime = d.wa.download_media(item.media_id)
            text = d.transcribe(audio, mime or item.mime)
            if not text:
                return _send(d, "I couldn't make out that voice note. Could you try again?")
            prefix = f'_Heard:_ "{text}"\n\n'
        elif item.kind != "text":
            return _send(d, "I can read text and voice notes for now.")

        word = text.strip().lower()
        if word in RESET_WORDS:
            d.store.clear_history()
            return _send(d, "Fresh start. Your tasks and reminders are untouched.")
        if word in BRIEF_WORDS and d.brief:
            return _send(d, d.brief())
        return _send(d, prefix + d.agent.reply(text))
    except Exception:
        log.exception("Failed to handle message")
        return _send(d, "Something went wrong on my side and I've logged it. Please try again in a minute.")


def _send(d: Deps, text: str) -> str:
    d.wa.send_text(d.owner_number, text)
    return text


def run_reminders(d: Deps) -> list[str]:
    """Send every reminder that is due. Inside WhatsApp's 24-hour window a normal message
    is used; outside it, the approved reminder template."""
    now = d.now()
    sent = []
    open_window = window_open(d.store.get_state("last_inbound_at"), now)
    for rem in d.store.due_reminders(now):
        try:
            if open_window:
                d.wa.send_text(d.owner_number, f"⏰ Reminder: {rem['text']}")
            else:
                d.wa.send_template(d.owner_number, d.reminder_template, d.template_lang, [rem["text"]])
            d.store.set_reminder_status(rem["id"], "sent")
            sent.append(rem["id"])
        except Exception:
            attempts = int(rem.get("attempts", 0)) + 1
            d.store.set_reminder_status(rem["id"], "failed" if attempts >= MAX_ATTEMPTS else "pending", attempts)
            log.exception("Reminder %s failed (attempt %s)", rem["id"], attempts)
    return sent


def run_morning(d: Deps) -> str:
    """9 AM: send the brief if the chat window is open, otherwise a check-in template
    with a button; tapping it opens the window and the brief follows."""
    if window_open(d.store.get_state("last_inbound_at"), d.now()) and d.brief:
        d.wa.send_text(d.owner_number, d.brief())
        return "brief"
    d.wa.send_template(d.owner_number, d.checkin_template, d.template_lang)
    return "checkin"
