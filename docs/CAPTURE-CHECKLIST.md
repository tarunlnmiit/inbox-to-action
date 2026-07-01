# Screenshot capture checklist

Screenshots are captured by the maintainer, then the sensitive regions are blurred before committing. **Raw screenshots go in `docs/_raw/` (gitignored) — never commit them.** Only blurred PNGs land in `docs/images/`.

For each shot: capture the screen, drop it in `docs/_raw/<filename>`, and note what needs blurring. The blur pass gaussian-blurs those regions and writes the clean version to `docs/images/<filename>`.

| Target file (`docs/images/`) | Screen to capture | Blur these |
|------------------------------|-------------------|-----------|
| `02-openrouter-keys.png` | openrouter.ai → Keys → Create key | the key value |
| `02-nim-key.png` | build.nvidia.com → API key dialog | the key value |
| `02-openai-key.png` | platform.openai.com → API keys | the key value(s) |
| `03-new-project.png` | Google Cloud → New Project dialog | account email |
| `03-enable-gmail-api.png` | Gmail API library page → Enable | (usually none) |
| `03-consent-screen.png` | OAuth consent screen showing "Publishing status: Testing" | support/developer emails |
| `03-test-users.png` | OAuth consent → Test users list | the added email(s) |
| `03-create-client.png` | Create OAuth client (Desktop app) + download dialog | Client ID + Client secret |
| `05-botfather.png` | @BotFather chat after `/newbot` | the bot token |
| `05-chatid.png` | getUpdates JSON showing chat id | the token in the URL |
| `06-mcp-connected.png` | `claude mcp list` output | (usually none) |

## Blur workflow (maintainer)

1. Maintainer captures → drops raw PNGs in `docs/_raw/`.
2. Assistant reads each, gaussian-blurs the listed regions (Pillow), writes to `docs/images/`.
3. Assistant re-checks each committed image for remaining secrets before the PR.
4. The `> 📷 _Screenshot: …_` placeholders in the guides are swapped for `![alt](images/<file>)`.
