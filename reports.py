import logging
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot

from config import DB_PATH, MOSCOW_TZ
from database import get_notes, get_tasks
from utils import escape_markdown, get_now_msk

_HEADERS = {
    'morning':    "🌅 **УТРЕННИЙ ПЛАН**",
    'evening':    "🌌 **ВЕЧЕРНИЙ ОТЧЕТ**",
    'status':     "📋 **ТЕКУЩИЕ ПЛАНЫ**",
    'pre_evening': "⏳ **ЧАС ДО ВЕЧЕРНЕГО ОТЧЕТА**",
}


async def send_report_to_chat(bot: Bot, chat_id: int, report_type: str):
    now = get_now_msk()
    today = now.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT title, created_at FROM groups WHERE chat_id=?', (chat_id,)
        ) as cur:
            group_data = await cur.fetchone()

        if not group_data:
            return

        start_date = datetime.strptime(group_data[1], "%Y-%m-%d").replace(tzinfo=MOSCOW_TZ)
        days_count = (now - start_date).days + 1

        u_h = await db.execute_fetchall(
            "SELECT DISTINCT user_id FROM habits WHERE chat_id=?", (chat_id,)
        )
        u_d = await db.execute_fetchall(
            "SELECT DISTINCT user_id FROM dailies WHERE chat_id=? AND date=?", (chat_id, today)
        )
        u_n = []
        if report_type == 'evening':
            u_n = await db.execute_fetchall(
                "SELECT DISTINCT user_id FROM notes WHERE chat_id=? AND date=?", (chat_id, today)
            )

        all_users = set(u[0] for u in u_h) | set(u[0] for u in u_d) | set(u[0] for u in u_n)

        if not all_users:
            if report_type == 'status':
                await bot.send_message(chat_id, "📭 **Планов на сегодня пока нет.**", parse_mode="Markdown")
            elif report_type == 'pre_evening':
                await bot.send_message(
                    chat_id,
                    "⏳ **Напоминание:** Через 1 час — вечерний отчёт!\nСегодня планов не добавлено.",
                    parse_mode="Markdown",
                )
            return

        header = _HEADERS.get(report_type, _HEADERS['status'])
        text = f"{header}\n`📅 {now.strftime('%d.%m.%Y')} | День {days_count}`\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

        is_biweekly = (days_count % 14 == 0) and report_type == 'morning'
        biweekly_lines = []

        show_sleep    = report_type in ('morning', 'status')
        show_notes    = report_type == 'evening'
        show_progress = report_type in ('evening', 'status', 'pre_evening')

        for uid in all_users:
            try:
                member = await bot.get_chat_member(chat_id, uid)
                name = member.user.first_name
            except Exception:
                name = f"User {uid}"

            safe_name = escape_markdown(name)
            habits, dailies = await get_tasks(uid, chat_id, today)
            notes = await get_notes(uid, chat_id, today) if show_notes else []

            async with db.execute(
                'SELECT duration_minutes FROM sleep_logs WHERE user_id=? AND date=?', (uid, today)
            ) as cur:
                s_row = await cur.fetchone()

            if is_biweekly:
                two_weeks_ago = (now - timedelta(days=14)).strftime("%Y-%m-%d")
                async with db.execute(
                    'SELECT AVG(duration_minutes) FROM sleep_logs WHERE user_id=? AND date > ?',
                    (uid, two_weeks_ago),
                ) as cur:
                    avg_row = await cur.fetchone()
                    avg_val = avg_row[0] if avg_row and avg_row[0] else 0
                    biweekly_lines.append(
                        f"• {safe_name}: `{int(avg_val // 60)}ч {int(avg_val % 60)}м` в среднем"
                    )

            text += f"👤 **{safe_name}**\n"

            if show_sleep:
                sleep_str = f"{s_row[0] // 60}ч {s_row[0] % 60}м" if s_row else "нет данных"
                text += f"╰ 💤 Сон: `{sleep_str}`\n"

            if habits:
                text += "   *Привычки:*\n"
                for h in habits:
                    icon = "✅" if h['done'] else "🔹"
                    text += f"      {icon} {escape_markdown(h['title'])}\n"

            if dailies:
                text += "   *Задачи:*\n"
                for d in dailies:
                    icon = "✅" if d['done'] else "🔸"
                    text += f"      {icon} {escape_markdown(d['title'])}\n"

            if show_notes and notes:
                text += "   🗒️ *Заметки:*\n"
                for number, note in enumerate(notes, 1):
                    note_text = escape_markdown(note['text']).replace('\n', '\n         ')
                    text += f"      {number}. {note_text}\n"

            if show_progress:
                total = len(habits) + len(dailies)
                done = sum(1 for x in habits + dailies if x['done'])
                if total > 0:
                    text += f"   📊 Прогресс: `{done}/{total}`\n"

            text += "\n"

        if is_biweekly:
            text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n📊 **ИТОГИ ЗА 14 ДНЕЙ (СРЕДНИЙ СОН):**\n"
            text += "\n".join(biweekly_lines)

        if report_type == 'pre_evening':
            text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n⏳ Остался 1 час до вечернего отчёта! Отметьте выполненные задачи и оставьте заметки."

        await bot.send_message(chat_id, text, parse_mode="Markdown")

        if report_type == 'evening':
            await db.execute('DELETE FROM dailies WHERE chat_id=? AND date=?', (chat_id, today))
            await db.execute('DELETE FROM notes WHERE chat_id=? AND date=?', (chat_id, today))
            await db.commit()
