"""All settings come from environment variables (Azure app settings in the cloud,
local.settings.json on a laptop). Secrets are never written in code or in the repo."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


def _get(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is not None:
        value = value.strip()
    return value or default


def _need(name: str) -> str:
    value = _get(name)
    if not value:
        raise RuntimeError(f"Missing required setting {name}")
    return value


def digits(number: str) -> str:
    """WhatsApp sends numbers as digits only (country code first, no +)."""
    return re.sub(r"\D", "", number or "")


@dataclass(frozen=True)
class Settings:
    owner_name: str
    owner_number: str
    wa_token: str
    wa_phone_number_id: str
    wa_app_secret: str
    wa_verify_token: str
    graph_version: str
    anthropic_key: str
    model: str
    timezone: str
    reminder_template: str
    checkin_template: str
    template_lang: str
    speech_key: str | None = None
    speech_region: str | None = None
    github_token: str | None = None
    github_owner: str | None = None
    watch_repos: tuple[str, ...] = ()
    ms_client_id: str | None = None
    ms_refresh_token: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        repos = tuple(r.strip() for r in (_get("WATCH_REPOS", "") or "").split(",") if r.strip())
        return cls(
            owner_name=_get("OWNER_NAME", "Abhinav"),
            owner_number=digits(_need("OWNER_WHATSAPP_NUMBER")),
            wa_token=_need("WHATSAPP_TOKEN"),
            wa_phone_number_id=_need("WHATSAPP_PHONE_NUMBER_ID"),
            wa_app_secret=_need("WHATSAPP_APP_SECRET"),
            wa_verify_token=_need("WHATSAPP_VERIFY_TOKEN"),
            graph_version=_get("WHATSAPP_GRAPH_VERSION", "v23.0"),
            anthropic_key=_need("ANTHROPIC_API_KEY"),
            model=_get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            timezone=_get("OWNER_TIMEZONE", "Asia/Kolkata"),
            reminder_template=_get("WHATSAPP_REMINDER_TEMPLATE", "cos_reminder"),
            checkin_template=_get("WHATSAPP_CHECKIN_TEMPLATE", "cos_checkin"),
            template_lang=_get("WHATSAPP_TEMPLATE_LANG", "en"),
            speech_key=_get("SPEECH_KEY"),
            speech_region=_get("SPEECH_REGION"),
            github_token=_get("GITHUB_TOKEN"),
            github_owner=_get("GITHUB_OWNER"),
            watch_repos=repos,
            ms_client_id=_get("MS_CLIENT_ID"),
            ms_refresh_token=_get("MS_REFRESH_TOKEN"),
        )
