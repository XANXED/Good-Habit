from pathlib import Path

import pytz

API_TOKEN = 'YOUR TOKEN'
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Абсолютный путь к БД — всегда рядом с main.py, независимо от CWD
DB_PATH = str(Path(__file__).parent.parent / 'tracker.db')

# Telegram user_id владельца бота — только он может запросить /backup.
# Узнать свой id можно у @userinfobot. Поставь None, чтобы отключить команду.
OWNER_ID: int | None = None
