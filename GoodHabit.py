import asyncio
import logging
import aiosqlite
import pytz
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

API_TOKEN = '8560867802:AAEDWntsC-Tqk2cZPKvz9QR0XuYVBt90FCQ'
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    selecting_group_h = State()
    selecting_group_d = State()
    waiting_for_habit = State()
    waiting_for_daily = State()
    waiting_for_sleep = State()

# БД

async def init_db():
    async with aiosqlite.connect('tracker.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS groups 
                            (chat_id INTEGER PRIMARY KEY, title TEXT, 
                             morning_time TEXT DEFAULT "08:00", evening_time TEXT DEFAULT "21:00",
                             created_at TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS user_groups 
                            (user_id INTEGER, chat_id INTEGER, group_title TEXT, 
                             PRIMARY KEY(user_id, chat_id))''')
        await db.execute('CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY, user_id INTEGER, chat_id INTEGER, title TEXT)')
        await db.execute('CREATE TABLE IF NOT EXISTS dailies (id INTEGER PRIMARY KEY, user_id INTEGER, chat_id INTEGER, title TEXT, date TEXT)')
        await db.execute('''CREATE TABLE IF NOT EXISTS completions 
                            (user_id INTEGER, chat_id INTEGER, task_id INTEGER, task_type TEXT, date TEXT, 
                            UNIQUE(user_id, chat_id, task_id, task_type, date))''')
        await db.execute('''CREATE TABLE IF NOT EXISTS sleep_logs 
                            (user_id INTEGER, date TEXT, duration_minutes INTEGER, UNIQUE(user_id, date))''')
        await db.commit()

# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

def get_now_msk():
    return datetime.now(MOSCOW_TZ)

async def get_user_groups_kb(user_id, prefix):
    async with aiosqlite.connect('tracker.db') as db:
        async with db.execute('SELECT chat_id, group_title FROM user_groups WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            if not rows: return None
            buttons = [[InlineKeyboardButton(text=f"🏢 {r[1]}", callback_data=f"{prefix}:{r[0]}")] for r in rows]
            return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_tasks(user_id, chat_id, today):
    habits, dailies = [], []
    async with aiosqlite.connect('tracker.db') as db:
        async with db.execute('SELECT id, title FROM habits WHERE user_id=? AND chat_id=?', (user_id, chat_id)) as cur:
            async for h_id, title in cur:
                async with db.execute('SELECT 1 FROM completions WHERE user_id=? AND chat_id=? AND task_id=? AND task_type="habit" AND date=?', (user_id, chat_id, h_id, today)) as chk:
                    habits.append({'id': h_id, 'title': title, 'type': 'habit', 'done': bool(await chk.fetchone())})
        async with db.execute('SELECT id, title FROM dailies WHERE user_id=? AND chat_id=? AND date=?', (user_id, chat_id, today)) as cur:
            async for d_id, title in cur:
                async with db.execute('SELECT 1 FROM completions WHERE user_id=? AND chat_id=? AND task_id=? AND task_type="daily" AND date=?', (user_id, chat_id, d_id, today)) as chk:
                    dailies.append({'id': d_id, 'title': title, 'type': 'daily', 'done': bool(await chk.fetchone())})
    return habits, dailies

# ЛОГИКА ОТЧЕТОВ

async def send_report_to_chat(chat_id, report_type):
    now = get_now_msk()
    today_str = now.strftime("%Y-%m-%d")
    
    async with aiosqlite.connect('tracker.db') as db:
        async with db.execute('SELECT title, created_at FROM groups WHERE chat_id=?', (chat_id,)) as cur:
            group_data = await cur.fetchone()
        
        if not group_data: return
        
        start_date = datetime.strptime(group_data[1], "%Y-%m-%d").replace(tzinfo=MOSCOW_TZ)
        days_count = (now - start_date).days + 1
        
        u_h = await db.execute_fetchall("SELECT DISTINCT user_id FROM habits WHERE chat_id=?", (chat_id,))
        u_d = await db.execute_fetchall("SELECT DISTINCT user_id FROM dailies WHERE chat_id=? AND date=?", (chat_id, today_str))
        all_users = set([u[0] for u in u_h] + [u[0] for u in u_d])
        if not all_users: return

        header = "🌅 **УТРЕННИЙ ПЛАН**" if report_type == 'morning' else "🌌 **ВЕЧЕРНИЙ ОТЧЕТ**"
        text = f"{header}\n`📅 {now.strftime('%d.%m.%Y')} | День {days_count}`\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        is_biweekly = (days_count % 14 == 0) and report_type == 'morning'
        biweekly_summary = "📊 **ИТОГИ ЗА 14 ДНЕЙ (СРЕДНИЙ СОН):**\n" if is_biweekly else ""

        for uid in all_users:
            try:
                member = await bot.get_chat_member(chat_id, uid)
                name = member.user.first_name
            except: name = f"User {uid}"
            
            habits, dailies = await get_tasks(uid, chat_id, today_str)
            
            async with db.execute('SELECT duration_minutes FROM sleep_logs WHERE user_id=? AND date=?', (uid, today_str)) as cur:
                s_row = await cur.fetchone()
            
            if is_biweekly:
                two_weeks_ago = (now - timedelta(days=14)).strftime("%Y-%m-%d")
                async with db.execute('SELECT AVG(duration_minutes) FROM sleep_logs WHERE user_id=? AND date > ?', (uid, two_weeks_ago)) as cur:
                    avg_row = await cur.fetchone()
                    avg_val = avg_row[0] if avg_row[0] else 0
                    biweekly_summary += f"• {name}: `{int(avg_val//60)}ч {int(avg_val%60)}м` в среднем\n"

            text += f"👤 **{name}**\n"
            if report_type == 'morning':
                text += f"╰ 💤 Сегодня: `{f'{s_row[0]//60}ч {s_row[0]%60}м' if s_row else 'нет данных'}`\n"
            
            # РАЗДЕЛЕНИЕ: ПРИВЫЧКИ
            if habits:
                text += "   *Привычки:*\n"
                for h in habits: 
                    text += f"      {'🔹' if not h['done'] else '✅'} {h['title']}\n"
            
            # РАЗДЕЛЕНИЕ: ЗАДАЧИ
            if dailies:
                text += "   *Задачи:*\n"
                for d in dailies: 
                    text += f"      {'🔸' if not d['done'] else '✅'} {d['title']}\n"
            
            if report_type == 'evening':
                total = len(habits) + len(dailies)
                done = sum(1 for x in habits if x['done']) + sum(1 for x in dailies if x['done'])
                if total > 0: text += f"   📊 Прогресс: `{done}/{total}`\n"
            text += "\n"

        if is_biweekly:
            text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n" + biweekly_summary

        await bot.send_message(chat_id, text, parse_mode="Markdown")
        if report_type == 'evening':
            await db.execute('DELETE FROM dailies WHERE chat_id=? AND date=?', (chat_id, today_str))
            await db.commit()

def get_private_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💎 Добавить привычку"), KeyboardButton(text="📝 Добавить задачу")],
        [KeyboardButton(text="😴 Записать сон"), KeyboardButton(text="⚙️ Управление задачами")]
    ], resize_keyboard=True)

@dp.message(F.chat.type == "private", F.text == "⚙️ Управление задачами")
async def list_groups(m: types.Message):
    kb = await get_user_groups_kb(m.from_user.id, "view_list")
    if kb: await m.answer("📋 **Выберите группу для управления:**", reply_markup=kb, parse_mode="Markdown")
    else: await m.answer("Вы еще не привязаны к группам. Напишите /start в группе.")

@dp.callback_query(F.data.startswith("view_list:"))
async def view_list_callback(c: types.CallbackQuery):
    cid = int(c.data.split(":")[1])
    await show_list_private(c, cid)

async def show_list_private(c: types.CallbackQuery, cid: int):
    today = get_now_msk().strftime("%Y-%m-%d")
    h, d = await get_tasks(c.from_user.id, cid, today)
    kb_buttons = []
    
    def add_rows(task_list, t_type):
        for x in task_list:
            status = "✅" if x['done'] else "❌"
            kb_buttons.append([
                InlineKeyboardButton(text=f"{status} {x['title']}", callback_data=f"tgl:{t_type}:{x['id']}:{cid}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"del:{t_type}:{x['id']}:{cid}")
            ])

    if h:
        kb_buttons.append([InlineKeyboardButton(text="─── ПРИВЫЧКИ ───", callback_data="none")])
        add_rows(h, "habit")
    
    if d:
        kb_buttons.append([InlineKeyboardButton(text="─── ЗАДАЧИ ───", callback_data="none")])
        add_rows(d, "daily")
            
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_groups")])
    
    try:
        await c.message.edit_text(
            f"⚙️ **Управление задачами** (ID: {cid})\nНажмите на название, чтобы отметить, или на 🗑️, чтобы удалить:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
            parse_mode="Markdown"
        )
    except: pass

@dp.callback_query(F.data.startswith("tgl:"))
async def toggle_task(c: types.CallbackQuery):
    parts = c.data.split(":")
    t_type, tid, cid = parts[1], int(parts[2]), int(parts[3])
    today = get_now_msk().strftime("%Y-%m-%d")
    
    async with aiosqlite.connect('tracker.db') as db:
        cur = await db.execute('SELECT 1 FROM completions WHERE user_id=? AND chat_id=? AND task_id=? AND task_type=? AND date=?', (c.from_user.id, cid, tid, t_type, today))
        if await cur.fetchone():
            await db.execute('DELETE FROM completions WHERE user_id=? AND chat_id=? AND task_id=? AND task_type=? AND date=?', (c.from_user.id, cid, tid, t_type, today))
        else:
            await db.execute('INSERT INTO completions (user_id, chat_id, task_id, task_type, date) VALUES (?, ?, ?, ?, ?)', (c.from_user.id, cid, tid, t_type, today))
        await db.commit()
    await show_list_private(c, cid)

@dp.callback_query(F.data.startswith("del:"))
async def delete_task(c: types.CallbackQuery):
    parts = c.data.split(":")
    t_type, tid, cid = parts[1], int(parts[2]), int(parts[3])
    table = "habits" if t_type == "habit" else "dailies"
    
    async with aiosqlite.connect('tracker.db') as db:
        await db.execute(f'DELETE FROM {table} WHERE id=? AND user_id=?', (tid, c.from_user.id))
        await db.execute('DELETE FROM completions WHERE task_id=? AND task_type=?', (tid, t_type))
        await db.commit()
    
    await c.answer("Удалено")
    await show_list_private(c, cid)

@dp.callback_query(F.data == "none")
async def ignore_click(c: types.CallbackQuery):
    await c.answer()

@dp.callback_query(F.data == "back_to_groups")
async def back_to_groups(c: types.CallbackQuery):
    kb = await get_user_groups_kb(c.from_user.id, "view_list")
    await c.message.edit_text("📋 **Выберите группу:**", reply_markup=kb, parse_mode="Markdown")

@dp.message(F.chat.type.in_(["group", "supergroup"]), Command("start"))
async def group_start(m: types.Message):
    today = get_now_msk().strftime("%Y-%m-%d")
    async with aiosqlite.connect('tracker.db') as db:
        await db.execute('INSERT OR IGNORE INTO groups (chat_id, title, created_at) VALUES (?, ?, ?)', (m.chat.id, m.chat.title, today))
        await db.execute('INSERT OR IGNORE INTO user_groups VALUES (?, ?, ?)', (m.from_user.id, m.chat.id, m.chat.title))
        await db.commit()
    await m.answer(f"🏁 **Группа активирована!**\nДата старта: `{today}`", parse_mode="Markdown")

@dp.message(F.chat.type.in_(["group", "supergroup"]), Command("morn", "evn"))
async def change_schedule(m: types.Message):
    is_morning = "morn" in m.text.lower()
    command_name = "morn" if is_morning else "evn"
    column = "morning_time" if is_morning else "evening_time"
    label = "утреннего" if is_morning else "вечернего"
    parts = m.text.split()
    if len(parts) < 2:
        return await m.answer(f"⚠️ **Ошибка!**\nУкажите время: `/{command_name} 09:30`", parse_mode="Markdown")
    time_input = parts[1]
    try:
        valid_time = datetime.strptime(time_input, "%H:%M").strftime("%H:%M")
    except ValueError:
        return await m.answer("❌ **Неверный формат!** (ЧЧ:ММ)", parse_mode="Markdown")
    async with aiosqlite.connect('tracker.db') as db:
        await db.execute(f'UPDATE groups SET {column}=? WHERE chat_id=?', (valid_time, m.chat.id))
        await db.commit()
    await m.answer(f"✅ Время {label} отчета изменено на **{valid_time}**.", parse_mode="Markdown")

@dp.message(F.chat.type == "private", F.text == "😴 Записать сон")
async def sleep_start(m: types.Message, state: FSMContext):
    await m.answer("Сколько вы спали? (Напр: `7:30`)", parse_mode="Markdown")
    await state.set_state(Form.waiting_for_sleep)

@dp.message(Form.waiting_for_sleep)
async def sleep_save(m: types.Message, state: FSMContext):
    try:
        h, mn = map(int, m.text.replace('.', ':').split(':'))
        today = get_now_msk().strftime("%Y-%m-%d")
        async with aiosqlite.connect('tracker.db') as db:
            await db.execute('INSERT OR REPLACE INTO sleep_logs VALUES (?, ?, ?)', (m.from_user.id, today, h*60+mn))
            await db.commit()
        await m.answer("✅ Сон сохранен!", reply_markup=get_private_kb())
        await state.clear()
    except: await m.answer("Формат ЧЧ:ММ (напр. 8:00)")

@dp.message(F.chat.type == "private", F.text.in_(["💎 Добавить привычку", "📝 Добавить задачу"]))
async def select_group_start(m: types.Message):
    prefix = "sel_h" if "привычку" in m.text.lower() else "sel_d"
    kb = await get_user_groups_kb(m.from_user.id, prefix)
    if not kb: return await m.answer("Сначала напиши /start в группе!")
    await m.answer("📍 **Выберите группу:**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("sel_"))
async def group_selected_for_add(c: types.CallbackQuery, state: FSMContext):
    pref, cid = c.data.split(":")
    await state.update_data(cid=int(cid))
    await c.message.edit_text("✍️ Введите название:")
    await state.set_state(Form.waiting_for_habit if pref == "sel_h" else Form.waiting_for_daily)

@dp.message(Form.waiting_for_habit)
async def save_habit(m: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect('tracker.db') as db:
        await db.execute('INSERT INTO habits (user_id, chat_id, title) VALUES (?, ?, ?)', (m.from_user.id, data['cid'], m.text))
        await db.commit()
    await m.answer(f"✅ Привычка добавлена!", reply_markup=get_private_kb()); await state.clear()

@dp.message(Form.waiting_for_daily)
async def save_daily(m: types.Message, state: FSMContext):
    data = await state.get_data()
    today = get_now_msk().strftime("%Y-%m-%d")
    async with aiosqlite.connect('tracker.db') as db:
        await db.execute('INSERT INTO dailies (user_id, chat_id, title, date) VALUES (?, ?, ?, ?)', (m.from_user.id, data['cid'], m.text, today))
        await db.commit()
    await m.answer(f"✅ Задача добавлена!", reply_markup=get_private_kb()); await state.clear()

async def check_time_loop():
    last_sent = {}
    while True:
        try:
            now = get_now_msk()
            t_now = now.strftime("%H:%M")
            d_now = now.strftime("%Y-%m-%d")
            async with aiosqlite.connect('tracker.db') as db:
                async with db.execute('SELECT chat_id, morning_time, evening_time FROM groups') as cur:
                    async for cid, mt, et in cur:
                        cid_m_key = f"{cid}_m"
                        cid_e_key = f"{cid}_e"
                        if t_now == mt and last_sent.get(cid_m_key) != d_now:
                            await send_report_to_chat(cid, 'morning')
                            last_sent[cid_m_key] = d_now
                        elif t_now == et and last_sent.get(cid_e_key) != d_now:
                            await send_report_to_chat(cid, 'evening')
                            last_sent[cid_e_key] = d_now
        except Exception as e: logging.error(f"Timer Error: {e}")
        await asyncio.sleep(20)

@dp.message(F.chat.type == "private", Command("start"))
async def start_p(m: types.Message):
    await m.answer("👋 Меню управления задачами:", reply_markup=get_private_kb())

async def main():
    await init_db()
    asyncio.create_task(check_time_loop())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())