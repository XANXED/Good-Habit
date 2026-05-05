# GoodHabit Bot

A Telegram bot for group habit, task, and sleep tracking.

Every morning the bot sends a daily plan, every evening - a summary report. One hour before the evening report, an intermediate snapshot is sent so everyone can see what's done and what's still pending.

## Features

- **Привычки** - recurring goals (no date), checked off each day
- **Задачи** - daily to-dos, cleared after the evening report
- **Заметки** - shown only in the evening report, also cleared afterwards
- **Сон** - log sleep duration, every 14 days the morning report includes a two-week average
- **Расписание** - morning and evening report times are configurable per group

## Getting Started

1. Install dependencies:
   ```bash
   pip install aiogram aiosqlite pytz
   ```

2. Add your bot token to `config.py`:
   ```python
   API_TOKEN = 'your_token_here'
   ```

3. Run:
   ```bash
   python3 main.py
   ```

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
main.py       - entry point, starts the bot
config.py     - token, timezone, DB path
handlers.py   - all message and button handlers
reports.py    - morning / evening / pre-evening report generation
scheduler.py  - timer loop: sends reports on schedule
database.py   - DB initialization and core queries
keyboards.py  - reply and inline keyboards
states.py     - FSM states (habit input, task input, etc.)
utils.py      - helper functions
```

## Stack

- [aiogram 3](https://docs.aiogram.dev/) - Telegram Bot API
- [aiosqlite](https://aiosqlite.omnilib.dev/) - async SQLite
- [pytz](https://pythonhosted.org/pytz/) - timezone handling
