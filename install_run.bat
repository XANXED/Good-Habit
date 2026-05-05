@echo off
echo Installing dependencies...
pip install aiogram aiosqlite pytz

echo Starting GoodHabit bot...
python main.py
pause
