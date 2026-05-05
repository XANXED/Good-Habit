import asyncio
import logging
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot

from .config import DB_PATH
from .reports import send_report_to_chat
from .utils import get_now_msk


async def send_startup_notifications(bot: Bot):
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall('''
            SELECT DISTINCT user_id FROM (
                SELECT user_id FROM user_groups
                UNION SELECT user_id FROM habits
                UNION SELECT user_id FROM dailies
                UNION SELECT user_id FROM notes
                UNION SELECT user_id FROM sleep_logs
            )
        ''')

    for (user_id,) in rows:
        try:
            await bot.send_message(
                user_id,
                "✨ У тебя всё получится!\n\n"
                "Напиши /start, вдруг в боте появился новый функционал :)",
            )
        except Exception as e:
            logging.warning("Не удалось отправить стартовое уведомление user_id=%s: %s", user_id, e)


async def _reset_old_completions(today: str):
    """Удаляет записи о выполнении задач за прошлые дни."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM completions WHERE date < ?', (today,))
        await db.commit()
    logging.info("Сброс старых отметок выполнен.")


async def check_time_loop(bot: Bot):
    last_sent: dict[str, str] = {}

    while True:
        try:
            now = get_now_msk()
            t_now = now.strftime("%H:%M")
            d_now = now.strftime("%Y-%m-%d")

            # Сброс отметок о выполнении привычек в 23:59
            if t_now == "23:59" and last_sent.get("reset") != d_now:
                await _reset_old_completions(d_now)
                last_sent["reset"] = d_now

            async with aiosqlite.connect(DB_PATH) as db:
                groups = await db.execute_fetchall(
                    'SELECT chat_id, morning_time, evening_time FROM groups'
                )

            for cid, mt, et in groups:
                mt_obj = datetime.strptime(mt, "%H:%M")
                et_obj = datetime.strptime(et, "%H:%M")
                warn_mt = (mt_obj - timedelta(hours=1)).strftime("%H:%M")
                warn_et = (et_obj - timedelta(hours=1)).strftime("%H:%M")

                key_warn_m = f"{cid}_warn_m"
                key_warn_e = f"{cid}_warn_e"
                key_m      = f"{cid}_m"
                key_e      = f"{cid}_e"

                # Предупреждение за час до утреннего плана
                if t_now == warn_mt and last_sent.get(key_warn_m) != d_now:
                    await bot.send_message(
                        cid,
                        "⏳ **Напоминание:** Утренний план будет сформирован через 1 час! "
                        "Не забудьте добавить задачи и записать сон.",
                        parse_mode="Markdown",
                    )
                    last_sent[key_warn_m] = d_now

                # Предупреждение + список задач за час до вечернего отчёта
                if t_now == warn_et and last_sent.get(key_warn_e) != d_now:
                    await send_report_to_chat(bot, cid, 'pre_evening')
                    last_sent[key_warn_e] = d_now

                # Утренний план
                if t_now == mt and last_sent.get(key_m) != d_now:
                    await send_report_to_chat(bot, cid, 'morning')
                    last_sent[key_m] = d_now

                # Вечерний отчёт
                if t_now == et and last_sent.get(key_e) != d_now:
                    await send_report_to_chat(bot, cid, 'evening')
                    last_sent[key_e] = d_now

        except Exception as e:
            logging.error("Ошибка в check_time_loop: %s", e)

        await asyncio.sleep(20)
