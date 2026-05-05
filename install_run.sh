#!/bin/bash
set -e

echo "==> Installing dependencies..."
pip3 install aiogram aiosqlite pytz

echo "==> Starting GoodHabit bot..."
python3 main.py
