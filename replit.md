# vahta-bot

A Telegram bot for shift workers (вахтовый метод). Matches job seekers with employers, handles vacancy postings, subscriptions, reviews, and an admin panel.

## How to run

1. Add the required secrets (see Configuration below).
2. Start the **"Start application"** workflow — it runs `python main.py`.

The bot connects to Telegram via long-polling and logs all activity to stdout.

## Stack

- Python 3.12
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)
- SQLite (`vahta.db`) via `database.py` — created automatically on first run
- `scheduler.py` — background thread that scrapes official job sites every 6 hours

## Configuration

Set these as Replit Secrets (never hardcode them):

| Secret | Description |
|--------|-------------|
| `TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | Your numeric Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot)) |

`config.py` reads both via `os.getenv(...)`.

## Dependencies

Install with:
```
pip install -r requirements.txt
```

Requirements: `pyTelegramBotAPI`, `requests`, `beautifulsoup4`

## User preferences

- Use `TOKEN` and `ADMIN_ID` environment variables — never hardcode them.
- Install dependencies from `requirements.txt`.
- Start the bot with `python main.py`.
