"""Builds everything from settings. Optional parts (voice, GitHub, Outlook) switch on
only when their settings exist."""
from __future__ import annotations

import os
from functools import lru_cache

from .agent import Agent
from .brief import build_brief
from .clock import now_utc
from .config import Settings
from .jobs import Deps
from .store import TableStore
from .tools import ToolBox
from .tools.tasks import task_tools
from .whatsapp import WhatsAppClient


@lru_cache(maxsize=1)
def deps() -> Deps:
    import anthropic

    s = Settings.from_env()
    store = TableStore(os.environ["AzureWebJobsStorage"])
    wa = WhatsAppClient(s.wa_token, s.wa_phone_number_id, s.graph_version)
    box = ToolBox().add(*task_tools(store, now_utc, s.timezone))

    github = outlook = None
    if s.github_token:
        from .tools.github import GitHub, github_tools

        github = GitHub(s.github_token, s.github_owner)
        box.add(*github_tools(github, s.watch_repos, now_utc))
    if s.ms_client_id:
        from .tools.outlook import Outlook, outlook_tools

        outlook = Outlook(s.ms_client_id, store, s.ms_refresh_token)
        box.add(*outlook_tools(outlook, s.timezone))

    transcribe = None
    if s.speech_key and s.speech_region:
        from .speech import transcribe as _t

        transcribe = lambda audio, mime: _t(audio, mime, s.speech_key, s.speech_region)  # noqa: E731

    agent = Agent(anthropic.Anthropic(api_key=s.anthropic_key, max_retries=2), s.model, box, store,
                  s.owner_name, s.timezone, now_utc)
    return Deps(store=store, wa=wa, owner_number=s.owner_number,
                reminder_template=s.reminder_template, checkin_template=s.checkin_template,
                template_lang=s.template_lang, now=now_utc, tz=s.timezone, agent=agent,
                brief=lambda: build_brief(store, now_utc(), s.timezone, s.owner_name, outlook, github,
                                          s.watch_repos),
                transcribe=transcribe)


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings.from_env()
