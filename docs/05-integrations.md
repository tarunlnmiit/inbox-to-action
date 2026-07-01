# 05 · Integrations

Both are optional and off by default. Neither can send email.

---

## Telegram summary (`--telegram`)

Push a concise run summary to your phone: counts, action-needed subjects (draft-ready status), tasks, and a link to your Gmail Drafts.

### Setup

1. In Telegram, message **@BotFather** → send `/newbot` → follow prompts → copy the **bot token** (looks like `8024470769:AAFw…`).

   > 📷 _Screenshot: `images/05-botfather.png` — the BotFather chat after `/newbot`; the **bot token** blurred._

2. Message your new bot anything (say "hi") so it has a chat with you.
3. Get your **chat id**: open `https://api.telegram.org/bot<token>/getUpdates` in a browser and copy `"chat":{"id": …}` — or message **@userinfobot**.

   > 📷 _Screenshot: `images/05-chatid.png` — the getUpdates JSON with the chat id; token in the URL blurred._

4. Put both in `.env`:

   ```bash
   TELEGRAM_BOT_TOKEN=8024470769:AAFw…      # TELEGRAM_TOKEN is also accepted
   TELEGRAM_CHAT_ID=123456789
   ```

### Use

```bash
inbox-to-action run --since 24h --telegram
```

Sends on every run when the flag is on. A send failure never breaks the run (it just warns). If the token/chat id aren't set, it prints "Telegram not configured" and continues.

> **Privacy:** this sends email subjects + extracted tasks to Telegram's servers (into your own chat). Notification only — it never sends email.

---

## Todoist (`--todoist`)

Push extracted tasks to Todoist.

1. Get your API token: Todoist → **Settings → Integrations → Developer** → copy the API token. (<https://todoist.com/app/settings/integrations/developer>)
2. Add it to `.env`:

   ```bash
   TODOIST_API_TOKEN=…
   ```

### Use

```bash
inbox-to-action run --since 24h --todoist
```

Each extracted task becomes a Todoist task (with its deadline as the due date). If the token isn't set, the flag is a no-op.

Next: [MCP & Skill →](06-mcp-and-skill.md)
