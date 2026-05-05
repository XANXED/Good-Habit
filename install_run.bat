@echo off
python -m venv .venv
.venv\Scripts\pip install aiogram aiosqlite pytz

echo =^> Starting GoodHabit bot...
.venv\Scripts\python main.py
pause
