# Security

The assistant reads my mail, calendar and repositories, and anyone can send email to me. So the design
assumes some of what it reads is hostile.

| Threat | How it is handled |
|---|---|
| Someone fakes Meta's webhook to inject messages | Every call must carry a valid `X-Hub-Signature-256` made with the app secret; others get 401 (`cos/whatsapp.py: verify_signature`) |
| Someone else messages the bot's number | Only `OWNER_WHATSAPP_NUMBER` is processed; everything else is dropped before the AI sees it (checked twice: webhook and worker) |
| Prompt injection in an email, calendar invite or pull request ("ignore your instructions and…") | Outside data is wrapped as `<untrusted_data>` and the system prompt says it is never instructions. More importantly, the assistant has **no tool that sends, deletes or changes anything outside its own task list**, so a successful injection can at worst add a junk task or say something wrong |
| Data leaking out through the bot | It only ever messages one number: mine. There is no tool that sends to anyone else |
| Stolen secrets | All secrets in Key Vault; the Function App reads them with its managed identity (Key Vault Secrets User only); deployment uses GitHub OIDC, so no Azure password exists; `local.settings.json` is git-ignored |
| Over-broad tokens | GitHub: fine-grained, read-only, chosen repos, expires. Outlook: delegated `Calendars.Read` and `Mail.Read` only. Anthropic: a dedicated key with a spending limit |
| Runaway cost | At most 8 tool steps and 1,200 output tokens per message; queue retries capped at 2; Anthropic account spending limit |
| Duplicate actions from Meta resending a message | Each message ID is recorded and handled once |
| Too much stored | Conversation memory keeps the last 20 turns only; `/reset` clears it |

## Boundaries I keep

- No employer systems (work mailbox, Teams, internal tools) are connected, and no employer data goes in.
- New integrations start read-only. Any tool that would act outside the task list (send a mail, accept a
  meeting) needs an explicit confirm step on WhatsApp first, and a separate decision to add it.

## Reporting

This is a personal project. If you spot a problem, open an issue without secrets or personal data in it.
