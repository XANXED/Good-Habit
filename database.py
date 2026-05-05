import aiosqlite

from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                chat_id      INTEGER PRIMARY KEY,
                title        TEXT,
                morning_time TEXT DEFAULT "08:00",
                evening_time TEXT DEFAULT "21:00",
                created_at   TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_groups (
                user_id     INTEGER,
                chat_id     INTEGER,
                group_title TEXT,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS habits (
                id      INTEGER PRIMARY KEY,
                user_id INTEGER,
                chat_id INTEGER,
                title   TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS dailies (
                id      INTEGER PRIMARY KEY,
                user_id INTEGER,
                chat_id INTEGER,
                title   TEXT,
                date    TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id      INTEGER PRIMARY KEY,
                user_id INTEGER,
                chat_id INTEGER,
                text    TEXT,
                date    TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS completions (
                user_id   INTEGER,
                chat_id   INTEGER,
                task_id   INTEGER,
                task_type TEXT,
                date      TEXT,
                UNIQUE (user_id, chat_id, task_id, task_type, date)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sleep_logs (
                user_id          INTEGER,
                date             TEXT,
                duration_minutes INTEGER,
                UNIQUE (user_id, date)
            )
        ''')
        await db.commit()


async def get_tasks(user_id: int, chat_id: int, today: str):
    habits, dailies = [], []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT id, title FROM habits WHERE user_id=? AND chat_id=?',
            (user_id, chat_id),
        ) as cur:
            async for h_id, title in cur:
                async with db.execute(
                    'SELECT 1 FROM completions'
                    ' WHERE user_id=? AND chat_id=? AND task_id=? AND task_type="habit" AND date=?',
                    (user_id, chat_id, h_id, today),
                ) as chk:
                    habits.append({'id': h_id, 'title': title, 'type': 'habit', 'done': bool(await chk.fetchone())})

        async with db.execute(
            'SELECT id, title FROM dailies WHERE user_id=? AND chat_id=? AND date=?',
            (user_id, chat_id, today),
        ) as cur:
            async for d_id, title in cur:
                async with db.execute(
                    'SELECT 1 FROM completions'
                    ' WHERE user_id=? AND chat_id=? AND task_id=? AND task_type="daily" AND date=?',
                    (user_id, chat_id, d_id, today),
                ) as chk:
                    dailies.append({'id': d_id, 'title': title, 'type': 'daily', 'done': bool(await chk.fetchone())})

    return habits, dailies


async def get_notes(user_id: int, chat_id: int, today: str):
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            'SELECT id, text FROM notes WHERE user_id=? AND chat_id=? AND date=? ORDER BY id',
            (user_id, chat_id, today),
        )
    return [{'id': note_id, 'text': text} for note_id, text in rows]
