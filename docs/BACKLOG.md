# Backlog

## Waiting on me (to go live)

| # | Action | Where | Notes |
|---|---|---|---|
| A1 | Create the Meta app, add my number as a test recipient, permanent token | SETUP step 1 | Needs my Facebook login |
| A2 | Submit the two templates | SETUP step 2 | Approval can take up to a day |
| A3 | Run `scripts/azure_setup.sh` in Cloud Shell | SETUP step 3 | |
| A4 | Put the secrets into Key Vault (new Anthropic key) | SETUP step 4 | |
| A5 | GitHub OIDC identity and `production` environment, then run deploy | SETUP step 5 | |
| A6 | Register the webhook in Meta | SETUP step 6 | |
| A7 | GitHub read-only token | SETUP step 7 | Optional |
| A8 | Outlook app registration and sign-in | SETUP step 8 | Optional |

## Next (v0.2)

- **Gmail and Google Calendar**, read-only. Note: a Google OAuth app left in "Testing" issues refresh
  tokens that expire after 7 days, so the app has to be published (personal use, unverified warning
  screen) for the connection to last.
- **Azure status**: cost so far this month and any failed resources in my subscription (Reader role
  only).
- **Industrial Cyber Brief check**: did today's 10 AM run succeed (already partly covered by
  `github_recent_failures`).
- **Snooze** from a reminder ("snooze 1h", "tomorrow").
- **Weekly review** on Sunday evening: what got done, what slipped, what is coming.
- **Recurring tasks** ("every Monday, check the CAB tracker").

## Later

- Notes and decisions log ("note: Anoop agreed to the Q1 pilot") searchable by project.
- Drafting emails for me to send myself (draft only, never sent by the bot).
- Moving the chat layer to Telegram if Meta's policy ever blocks the bot (only `cos/whatsapp.py` changes).
- The base for more agents (the "company of agents" idea): this assistant as the coordinator.

## Decisions

| Date | Decision |
|---|---|
| 2 Nov 2026 | Build our own rather than run OpenClaw |
| 2 Nov 2026 | WhatsApp through Meta's official Cloud API, scoped as a task and follow-up assistant |
| 2 Nov 2026 | Azure Functions + Table Storage + Key Vault; Claude Sonnet as the model |
| 2 Nov 2026 | Integrations read-only to start: personal Outlook, GitHub; Gmail next |
