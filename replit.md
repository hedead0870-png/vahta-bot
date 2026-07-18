# vahta-bot

A Telegram bot built with Python and pyTelegramBotAPI.

## How to run

1. Set the `TOKEN` secret to your Telegram bot token (from @BotFather).
2. Start the **"Start application"** workflow — it runs `python main.py`.

## Stack

- Python 3.12
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)

## Configuration

- `TOKEN` — Telegram bot API token (stored as a Replit Secret, never hardcoded)
- `config.py` reads `TOKEN` from the environment via `os.getenv("TOKEN")`

## User preferences

- Use `TOKEN` environment variable for the Telegram bot token — never hardcode it.
- Install dependencies from `requirements.txt`.
- Start the bot with `python main.py`.
