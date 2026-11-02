"""Voice notes to text with Azure AI Speech (fast transcription). Candidate languages
are English (India) and Hindi, so mixed speech is handled."""
from __future__ import annotations

import json

import requests

API_VERSION = "2024-11-15"


def transcribe(audio: bytes, mime: str, key: str, region: str,
               locales: tuple[str, ...] = ("en-IN", "hi-IN"),
               session: requests.Session | None = None) -> str:
    http = session or requests.Session()
    url = (f"https://{region}.api.cognitive.microsoft.com/speechtotext/"
           f"transcriptions:transcribe?api-version={API_VERSION}")
    files = {
        "audio": ("voice-note.ogg", audio, mime or "audio/ogg"),
        "definition": (None, json.dumps({"locales": list(locales)}), "application/json"),
    }
    resp = http.post(url, headers={"Ocp-Apim-Subscription-Key": key}, files=files, timeout=90)
    resp.raise_for_status()
    phrases = resp.json().get("combinedPhrases") or []
    return " ".join(p.get("text", "") for p in phrases).strip()
