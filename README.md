# Chief of Staff

A personal assistant on WhatsApp, so nothing I commit to gets forgotten. I message it (text or a
voice note) and it captures tasks and follow-ups, reminds me on time, sends a brief every morning,
and tells me what is happening on my projects.

Personal, non-commercial project, built in my own time on my own accounts. No employer systems or
data are connected to it.

**Status:** v0.1, code complete and tested offline (14 tests). Not deployed yet: it needs the Meta
app, the Azure resources and the secrets set up (see [docs/SETUP.md](docs/SETUP.md)).

## What it does (v1)

| You send | It does |
|---|---|
| "Remind me to chase Anoop on the deck Thursday" | Saves a follow-up with Anoop, due Thursday, and pings you then |
| A voice note | Transcribes it (English or Hindi), shows what it heard, then acts on it |
| "What's pending on the AI SOC Lab?" | Lists open tasks for that project and the repo's latest runs and pull requests |
| "Any failed runs today?" | Checks the watched GitHub repos |
| "What's on my calendar tomorrow?" | Reads your personal Outlook calendar |
| "Did the PwC recruiter mail me?" | Searches your personal Outlook mail |
| "brief" | Today's meetings, overdue items, due today, this week, failed runs |
| "done with the CAB tracker" | Marks the task done and cancels its reminder |

Every day at 9 AM IST it sends the morning brief (or a "your brief is ready" button if WhatsApp's
24-hour window is closed; tap it and the brief follows).

It can **read** email, calendar and GitHub. It **cannot** send email, accept meetings or change
repositories. That is deliberate (see [SECURITY.md](SECURITY.md)).

## How it works, in one picture

```
You (WhatsApp) -> Meta WhatsApp Cloud API -> Azure Function (webhook) -> queue
   -> Azure Function (Claude + tools) -> reply on WhatsApp
Timers: every 5 min (reminders), 9 AM IST (brief)
Memory: Azure Table (tasks, reminders, last 20 messages)   Secrets: Azure Key Vault
```

Details in plain words: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository map

| Path | What is in it |
|---|---|
| `function_app.py` | The four Azure Functions (webhook, message worker, reminder timer, morning timer) |
| `cos/agent.py` | The Claude loop and the assistant's instructions |
| `cos/tools/` | What the assistant can do: tasks and reminders, GitHub, Outlook |
| `cos/jobs.py` | What each function does, without Azure code (so it can be tested) |
| `cos/whatsapp.py` | Meta's API: signature check, reading messages, sending replies |
| `cos/store.py` | Tasks, reminders, conversation memory (Azure Table) |
| `cos/brief.py` | The morning brief |
| `cos/speech.py` | Voice notes to text (Azure AI Speech) |
| `scripts/azure_setup.sh` | One-time Azure setup, run in Azure Cloud Shell |
| `scripts/outlook_login.py` | One-time Outlook sign-in |
| `docs/` | Setup, architecture, backlog |

## Run the tests

```
pip install -r requirements-dev.txt
pytest -q
```

## Documents

- [docs/SETUP.md](docs/SETUP.md): step-by-step setup (Meta, Azure, secrets, deploy)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how it works and why
- [SECURITY.md](SECURITY.md): threats and how each is handled
- [docs/BACKLOG.md](docs/BACKLOG.md): what is next, and what is waiting on me
- [CHANGELOG.md](CHANGELOG.md)
