"""Read-only personal Outlook (outlook.com) calendar and mail through Microsoft Graph.
Signs in as the owner with a refresh token from a one-time login (scripts/outlook_login.py).
Microsoft rotates the refresh token; the newest one is kept in the store."""
from __future__ import annotations

import time
from datetime import datetime

import requests

from ..clock import parse_when, to_iso
from ..store import Store
from . import STR, Tool, obj

TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = "offline_access User.Read Calendars.Read Mail.Read"


class Outlook:
    def __init__(self, client_id: str, store: Store, initial_refresh_token: str | None,
                 tz_windows: str = "India Standard Time", session: requests.Session | None = None):
        self.client_id = client_id
        self.store = store
        self.initial = initial_refresh_token
        self.tz_windows = tz_windows
        self.http = session or requests.Session()
        self._token: tuple[str, float] | None = None

    def _access_token(self) -> str:
        if self._token and self._token[1] > time.time() + 60:
            return self._token[0]
        refresh = self.store.get_state("ms_refresh_token") or self.initial
        if not refresh:
            raise RuntimeError("Outlook is not signed in yet; run scripts/outlook_login.py")
        resp = self.http.post(TOKEN_URL, data={"client_id": self.client_id, "grant_type": "refresh_token",
                                               "refresh_token": refresh, "scope": SCOPES}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("refresh_token"):
            self.store.set_state("ms_refresh_token", data["refresh_token"])
        self._token = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
        return self._token[0]

    def _get(self, path: str, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._access_token()}",
                   "Prefer": f'outlook.timezone="{self.tz_windows}"'}
        resp = self.http.get(f"{GRAPH}{path}", headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def events(self, start: datetime, end: datetime) -> list[dict]:
        data = self._get("/me/calendarView", {
            "startDateTime": to_iso(start), "endDateTime": to_iso(end), "$top": "50",
            "$orderby": "start/dateTime", "$select": "subject,start,end,location,isAllDay,organizer"})
        return [{"subject": e.get("subject"), "start": e["start"]["dateTime"][:16],
                 "end": e["end"]["dateTime"][:16], "all_day": e.get("isAllDay"),
                 "location": (e.get("location") or {}).get("displayName", ""),
                 "organizer": ((e.get("organizer") or {}).get("emailAddress") or {}).get("name", "")}
                for e in data.get("value", [])]

    def mail(self, query: str = "", top: int = 10) -> list[dict]:
        params = {"$top": str(max(1, min(top, 25))), "$select": "subject,from,receivedDateTime,bodyPreview"}
        if query:
            params["$search"] = '"' + query.replace('"', "") + '"'
            path = "/me/messages"
        else:
            params["$orderby"] = "receivedDateTime desc"
            path = "/me/mailFolders/inbox/messages"
        data = self._get(path, params)
        return [{"subject": m.get("subject"), "from": ((m.get("from") or {}).get("emailAddress") or {}).get("name"),
                 "received": m.get("receivedDateTime"), "preview": (m.get("bodyPreview") or "")[:300]}
                for m in data.get("value", [])]


def outlook_tools(outlook: Outlook, tz: str) -> list[Tool]:
    def calendar(start: str, end: str) -> dict:
        return {"events": outlook.events(parse_when(start, tz), parse_when(end, tz))}

    def search_mail(query: str = "", top: int = 10) -> dict:
        return {"messages": outlook.mail(query, top)}

    return [
        Tool("outlook_calendar", "The owner's personal Outlook calendar between two times (read-only).",
             obj({"start": {**STR, "description": "ISO 8601, local time"},
                  "end": {**STR, "description": "ISO 8601, local time"}}, ["start", "end"]),
             calendar, untrusted=True),
        Tool("outlook_search_mail", "Search the owner's personal Outlook mail (read-only). "
             "Empty query returns the latest inbox messages.",
             obj({"query": STR, "top": {"type": "integer"}}), search_mail, untrusted=True),
    ]
