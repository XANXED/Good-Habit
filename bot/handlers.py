import aiosqlite
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import DB_PATH, OWNER_ID
from .database import get_tasks
from .keyboards import get_private_kb, get_user_groups_kb
from .reports import send_report_to_chat
from .states import Form
from .utils import get_now_msk

router = Router()


# ─── Группы ───────────────────────────────────────────────────────────────────

@router.message(F.chat.type.in_(["group", "supergroup"]), Command("start"))
async def group_start(m: types.Message):
    today = get_now_msk().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT OR IGNORE INTO groups (chat_id, title, created_at) VALUES (?, ?, ?)',
            (m.chat.id, m.chat.title, today),
        )
        await db.execute(
            'INSERT OR IGNORE INTO user_groups VALUES (?, ?, ?)',
            (m.from_user.id, m.chat.id, m.chat.title),
        )
        await db.commit()
    await m.answer(f"🏁 **Группа активирована!**\nДата старта: `{today}`", parse_mode="Markdown")


@router.message(F.chat.type.in_(["group", "supergroup"]), Command("morn", "evn"))
async def change_schedule(m: types.Message):
    # Извлекаем имя команды без слэша и без @BotName
    command = m.text.split()[0].lstrip('/').split('@')[0]
    is_morning = command == 'morn'
    column = "morning_time" if is_morning else "evening_time"
    label = "утреннего" if is_morning else "вечернего"

    parts = m.text.split()
    if len(parts) < 2:
        return await m.answer(
            f"⚠️ **Ошибка!**\nУкажите время: `/{command} 09:30`",
            parse_mode="Markdown",
        )

    try:
        from datetime import datetime as _dt
        valid_time = _dt.strptime(parts[1], "%H:%M").strftime("%H:%M")
    except ValueError:
        return await m.answer("❌ **Неверный формат!** (ЧЧ:ММ)", parse_mode="Markdown")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'UPDATE groups SET {column}=? WHERE chat_id=?', (valid_time, m.chat.id))
        await db.commit()

    await m.answer(f"✅ Время {label} отчёта изменено на **{valid_time}**.", parse_mode="Markdown")


@router.message(F.chat.type.in_(["group", "supergroup"]), Command("status"))
async def get_current_status(m: types.Message):
    await send_report_to_chat(m.bot, m.chat.id, 'status')


# ─── Личные сообщения ─────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", Command("start"))
async def start_private(m: types.Message):
    await m.answer("👋 Меню управления задачами:", reply_markup=get_private_kb())


@router.message(F.chat.type == "private", F.text == "⚙️ Управление задачами")
async def list_groups(m: types.Message):
    kb = await get_user_groups_kb(m.from_user.id, "view_list")
    if kb:
        await m.answer("📋 **Выберите группу для управления:**", reply_markup=kb, parse_mode="Markdown")
    else:
        await m.answer("Вы еще не привязаны к группам. Напишите /start в группе.")


@router.message(F.chat.type == "private", F.text == "😴 Записать сон")
async def sleep_start(m: types.Message, state: FSMContext):
    await m.answer("Сколько вы спали? (Напр: `7:30`)", parse_mode="Markdown")
    await state.set_state(Form.waiting_for_sleep)


@router.message(Form.waiting_for_sleep)
async def sleep_save(m: types.Message, state: FSMContext):
    try:
        parts = m.text.replace('.', ':').split(':')
        h, mn = int(parts[0]), int(parts[1])
        today = get_now_msk().strftime("%Y-%m-%d")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'INSERT OR REPLACE INTO sleep_logs VALUES (?, ?, ?)',
                (m.from_user.id, today, h * 60 + mn),
            )
            await db.commit()
        await m.answer("✅ Сон сохранен!", reply_markup=get_private_kb())
        await state.clear()
    except Exception:
        await m.answer("Формат ЧЧ:ММ (напр. 8:00)")


@router.message(F.chat.type == "private", F.text.in_(["💎 Добавить привычку", "📝 Добавить задачу", "🗒️ Оставить заметку"]))
async def select_group_start(m: types.Message):
    if "привычку" in m.text:
        prefix = "sel_h"
    elif "заметку" in m.text:
        prefix = "sel_n"
    else:
        prefix = "sel_d"

    kb = await get_user_groups_kb(m.from_user.id, prefix)
    if not kb:
        return await m.answer("Сначала напиши /start в группе!")
    await m.answer("📍 **Выберите группу:**", reply_markup=kb, parse_mode="Markdown")


@router.message(Form.waiting_for_habit)
async def save_habit(m: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO habits (user_id, chat_id, title) VALUES (?, ?, ?)',
            (m.from_user.id, data['cid'], m.text),
        )
        await db.commit()
    await m.answer("✅ Привычка добавлена!", reply_markup=get_private_kb())
    await state.clear()


@router.message(Form.waiting_for_daily)
async def save_daily(m: types.Message, state: FSMContext):
    data = await state.get_data()
    today = get_now_msk().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO dailies (user_id, chat_id, title, date) VALUES (?, ?, ?, ?)',
            (m.from_user.id, data['cid'], m.text, today),
        )
        await db.commit()
    await m.answer("✅ Задача добавлена!", reply_markup=get_private_kb())
    await state.clear()


@router.message(Form.waiting_for_note)
async def save_note(m: types.Message, state: FSMContext):
    note_text = (m.text or '').strip()
    if not note_text:
        return await m.answer("Заметка не может быть пустой. Напишите текст заметки.")

    data = await state.get_data()
    today = get_now_msk().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO notes (user_id, chat_id, text, date) VALUES (?, ?, ?, ?)',
            (m.from_user.id, data['cid'], note_text, today),
        )
        await db.commit()
    await m.answer("✅ Заметка сохранена! Она появится только в вечернем отчёте.", reply_markup=get_private_kb())
    await state.clear()


# ─── Callback-кнопки ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("view_list:"))
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
                InlineKeyboardButton(
                    text=f"{status} {x['title']}",
                    callback_data=f"tgl:{t_type}:{x['id']}:{cid}",
                ),
                InlineKeyboardButton(text="🗑️", callback_data=f"del:{t_type}:{x['id']}:{cid}"),
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
            f"⚙️ **Управление задачами** (ID: {cid})\n"
            "Нажмите на название, чтобы отметить, или на 🗑️, чтобы удалить:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
            parse_mode="Markdown",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("tgl:"))
async def toggle_task(c: types.CallbackQuery):
    _, t_type, tid, cid = c.data.split(":")
    tid, cid = int(tid), int(cid)
    today = get_now_msk().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT 1 FROM completions'
            ' WHERE user_id=? AND chat_id=? AND task_id=? AND task_type=? AND date=?',
            (c.from_user.id, cid, tid, t_type, today),
        ) as cur:
            exists = await cur.fetchone()

        if exists:
            await db.execute(
                'DELETE FROM completions'
                ' WHERE user_id=? AND chat_id=? AND task_id=? AND task_type=? AND date=?',
                (c.from_user.id, cid, tid, t_type, today),
            )
        else:
            await db.execute(
                'INSERT INTO completions (user_id, chat_id, task_id, task_type, date) VALUES (?, ?, ?, ?, ?)',
                (c.from_user.id, cid, tid, t_type, today),
            )
        await db.commit()

    await show_list_private(c, cid)


@router.callback_query(F.data.startswith("del:"))
async def delete_task(c: types.CallbackQuery):
    _, t_type, tid, cid = c.data.split(":")
    tid, cid = int(tid), int(cid)
    table = "habits" if t_type == "habit" else "dailies"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'DELETE FROM {table} WHERE id=? AND user_id=?', (tid, c.from_user.id))
        await db.execute('DELETE FROM completions WHERE task_id=? AND task_type=?', (tid, t_type))
        await db.commit()

    await c.answer("Удалено")
    await show_list_private(c, cid)


@router.callback_query(F.data.startswith("sel_"))
async def group_selected_for_add(c: types.CallbackQuery, state: FSMContext):
    pref, cid = c.data.split(":")
    await state.update_data(cid=int(cid))

    if pref == "sel_n":
        await c.message.edit_text("🗒️ **Введите заметку для вечернего отчёта:**", parse_mode="Markdown")
        await state.set_state(Form.waiting_for_note)
    elif pref == "sel_h":
        await c.message.edit_text("✍️ Введите название привычки:")
        await state.set_state(Form.waiting_for_habit)
    else:
        await c.message.edit_text("✍️ Введите название задачи:")
        await state.set_state(Form.waiting_for_daily)


@router.callback_query(F.data == "none")
async def ignore_click(c: types.CallbackQuery):
    await c.answer()


@router.callback_query(F.data == "back_to_groups")
async def back_to_groups(c: types.CallbackQuery):
    kb = await get_user_groups_kb(c.from_user.id, "view_list")
    await c.message.edit_text("📋 **Выберите группу:**", reply_markup=kb, parse_mode="Markdown")


# ─── Бэкап БД ─────────────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", Command("backup"))
async def send_backup(m: types.Message):
    import os
    from aiogram.types import FSInputFile

    if OWNER_ID is None:
        return await m.answer("⛔ Команда отключена. Задайте OWNER\\_ID в config.py.", parse_mode="Markdown")

    if m.from_user.id != OWNER_ID:
        return await m.answer("⛔ Недостаточно прав.")

    if not os.path.exists(DB_PATH):
        return await m.answer("❌ Файл базы данных не найден.")

    timestamp = get_now_msk().strftime("%Y-%m-%d_%H-%M")
    await m.answer_document(
        FSInputFile(DB_PATH, filename=f"goodhabit_backup_{timestamp}.db"),
        caption=f"💾 Резервная копия БД\n`{timestamp}`",
        parse_mode="Markdown",
    )
