from aiogram.fsm.state import State, StatesGroup


class TrainingStates(StatesGroup):
    choosing_topic = State()
    answering = State()


class ExamStates(StatesGroup):
    choosing_topic = State()
    choosing_count = State()
    choosing_time = State()
    answering = State()
    reviewing = State()


class AdminStates(StatesGroup):
    broadcast_message = State()
