from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_user_id
from bot.database.db import get_db
from bot.database import queries

router = APIRouter()


class TrainingAnswerRequest(BaseModel):
    question_id: str
    chosen_answer: str  # single letter or comma-separated "A,C" for multi-answer


def _answers_match(chosen: str, correct: str) -> bool:
    return set(chosen.split(",")) == set(correct.split(","))


@router.post("/training/answer")
async def save_training_answer(
    body: TrainingAnswerRequest,
    user_id: int = Depends(get_user_id),
):
    db = await get_db()
    q_row = await queries.get_question_by_id(db, body.question_id)
    if not q_row:
        return {"error": "Question not found"}

    is_correct = _answers_match(body.chosen_answer, q_row["correct_answer"])
    await queries.save_training_answer(db, user_id, body.question_id, body.chosen_answer, is_correct)
    today = await queries.get_today_training_stats(db, user_id)
    return {"is_correct": is_correct, "correct_answer": q_row["correct_answer"], "today": today}


@router.get("/stats")
async def get_stats(user_id: int = Depends(get_user_id)):
    db = await get_db()
    stats = await queries.get_user_stats(db, user_id)
    today = await queries.get_today_training_stats(db, user_id)
    return {**stats, "today": today}
