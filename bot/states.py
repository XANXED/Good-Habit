from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    selecting_group_h = State()
    selecting_group_d = State()
    waiting_for_habit = State()
    waiting_for_daily = State()
    waiting_for_note = State()
    waiting_for_sleep = State()
