from datetime import datetime

from .config import MOSCOW_TZ


def get_now_msk() -> datetime:
    return datetime.now(MOSCOW_TZ)


def escape_markdown(text: str) -> str:
    special = {'\\', '`', '*', '_', '[', ']'}
    return ''.join(f'\\{c}' if c in special else c for c in str(text))
