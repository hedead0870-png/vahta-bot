# vahta-bot

A Telegram bot built with Python and pyTelegramBotAPI.

## How to run

1. Set the `TOKEN` secret to your Telegram bot token (from @BotFather).
2. Start the **"Start application"** workflow — it runs `python main.py`.

## Stack

- Python 3.12
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)

## Configuration

- `TOKEN` — Telegram bot API token (stored as a Replit Secret, from @BotFather)
- `ADMIN_ID` — Numeric Telegram user ID of the bot admin (stored as a Replit Secret)
- `config.py` reads both from the environment via `os.getenv(...)`

## Database

- SQLite (`vahta.db`) — created automatically on first run via `database.py`

## User preferences

- Use `TOKEN` and `ADMIN_ID` environment variables — never hardcode them.
- Install dependencies from `requirements.txt`.
- Start the bot with `python main.py`.
