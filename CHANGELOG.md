# Changelog

## 0.1.1 (3 Nov 2026)

- Reply DONE or SNOOZE (SNOOZE 30m, SNOOZE 2h) to the last reminder; handled without an AI call.
- Template wording changed so Meta accepts them as Utility.

## 0.1.0 (2 Nov 2026)

First version, tested offline, not yet deployed.

- WhatsApp Cloud API webhook with signature check and owner-only filter, queued processing.
- Claude assistant with tools: tasks and follow-ups, reminders, GitHub project status and failed runs
  (read-only), personal Outlook calendar and mail (read-only).
- Voice notes transcribed with Azure AI Speech (English and Hindi).
- Reminders every 5 minutes; 9 AM IST morning brief; templates when the 24-hour window is closed.
- Azure setup script, Outlook sign-in script, CI and a manual deploy workflow (OIDC).
- Docs: setup, architecture, security, backlog.
