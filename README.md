# GoodHabit Bot

A Telegram bot for group habit, task, and sleep tracking.

Every morning the bot sends a daily plan, every evening — a summary report. One hour before the evening report, an intermediate snapshot is sent so everyone can see what's done and what's still pending.

## Getting Started

First, add your bot token to `bot/config.py`:
```python
API_TOKEN = 'your_token_here'
```

Then pick your platform:

**Linux / macOS**
```bash
bash install_run.sh
```

**Windows**
```
install_run.bat
```

Both scripts install the required dependencies and start the bot automatically.

### Manual setup (any platform)

```bash
pip install aiogram aiosqlite pytz
python3 main.py
```

## Features

- **Habits** — recurring goals (no date), checked off each day
- **Tasks** — daily to-dos, cleared after the evening report
- **Notes** — shown only in the evening report, also cleared afterwards
- **Sleep** — log sleep duration; every 14 days the morning report includes a two-week average
- **Schedule** — morning and evening report times are configurable per group

## Commands

| Command | Where | Description |
|---|---|---|
| `/start` | group | Activate the bot in a group |
| `/status` | group | Current task snapshot |
| `/morn HH:MM` | group | Change morning report time |
| `/evn HH:MM` | group | Change evening report time |
| `/start` | private | Open the menu |

Everything else is managed via buttons in the bot's private chat.

## File Structure

```
main.py            — entry point, starts the bot
install_run.sh     — Linux/macOS: install deps and run
install_run.bat    — Windows: install deps and run
bot/
  config.py        — token, timezone, DB path
  handlers.py      — all message and button handlers
  reports.py       — morning / evening / pre-evening report generation
  scheduler.py     — timer loop: sends reports on schedule
  database.py      — DB initialization and core queries
  keyboards.py     — reply and inline keyboards
  states.py        — FSM states (habit input, task input, etc.)
  utils.py         — helper functions
```

## Stack

- [aiogram 3](https://docs.aiogram.dev/) — Telegram Bot API
- [aiosqlite](https://aiosqlite.omnilib.dev/) — async SQLite
- [pytz](https://pythonhosted.org/pytz/) — timezone handling
