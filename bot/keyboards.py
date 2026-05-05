import aiosqlite
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .config import DB_PATH


def get_private_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💎 Добавить привычку"), KeyboardButton(text="📝 Добавить задачу")],
            [KeyboardButton(text="🗒️ Оставить заметку"), KeyboardButton(text="😴 Записать сон")],
            [KeyboardButton(text="⚙️ Управление задачами")],
        ],
        resize_keyboard=True,
    )


async def get_user_groups_kb(user_id: int, prefix: str) -> InlineKeyboardMarkup | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT chat_id, group_title FROM user_groups WHERE user_id = ?',
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return None

    buttons = [
        [InlineKeyboardButton(text=f"🏢 {title}", callback_data=f"{prefix}:{cid}")]
        for cid, title in rows
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
