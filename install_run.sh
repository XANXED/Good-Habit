#!/bin/bash
set -e

python3 -m venv .venv
.venv/bin/pip install aiogram aiosqlite pytz

echo "==> Starting GoodHabit bot..."
.venv/bin/python main.py
