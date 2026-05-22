from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_user_id
from bot.database.db import get_db
from bot.database import queries

router = APIRouter()


class ExamStartRequest(BaseModel):
    topic: str
    count: int
    time_limit_seconds: Optional[int] = None


class ExamAnswer(BaseModel):
    question_id: str
    chosen_answer: Optional[str] = None
    is_skipped: bool = False


class ExamFinishRequest(BaseModel):
    session_id: int
    answers: list[ExamAnswer]
    elapsed_seconds: int


@router.post("/exam/start")
async def start_exam(body: ExamStartRequest, user_id: int = Depends(get_user_id)):
    if body.count not in (10, 20, 30):
        raise HTTPException(status_code=400, detail="count must be 10, 20, or 30")

    db = await get_db()
    time_choice = None
    if body.time_limit_seconds:
        mins = body.time_limit_seconds // 60
        time_choice = f"{mins} мин"

    session_id = await queries.create_exam_session(
        db, user_id, body.topic, body.count,
        body.time_limit_seconds, time_choice,
    )

    rows = await queries.get_random_questions(db, body.topic, body.count)
    questions = [
        {
            "id": q["id"],
            "topic": q["topic"],
            "subtopic": q["subtopic"],
            "question": q["question"],
            "options": {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]},
            "correct_answer": q["correct_answer"],
            "drug_name": q["drug_name"],
        }
        for q in rows
    ]

    return {"session_id": session_id, "questions": questions}


def _answers_match(chosen: Optional[str], correct: str) -> bool:
    if not chosen:
        return False
    return set(chosen.split(",")) == set(correct.split(","))


@router.post("/exam/finish")
async def finish_exam(body: ExamFinishRequest, user_id: int = Depends(get_user_id)):
    db = await get_db()
    session = await queries.get_exam_session(db, body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your session")

    correct_count = 0
    details = []

    for order, ans in enumerate(body.answers):
        q_row = await queries.get_question_by_id(db, ans.question_id)
        if not q_row:
            continue

        is_correct = not ans.is_skipped and _answers_match(ans.chosen_answer, q_row["correct_answer"])
        if is_correct:
            correct_count += 1

        await queries.save_exam_answer(
            db, body.session_id, ans.question_id,
            ans.chosen_answer, is_correct, ans.is_skipped, order,
        )

        details.append({
            "question_id": ans.question_id,
            "question": q_row["question"],
            "options": {
                "A": q_row["option_a"], "B": q_row["option_b"],
                "C": q_row["option_c"], "D": q_row["option_d"],
            },
            "correct_answer": q_row["correct_answer"],
            "chosen_answer": ans.chosen_answer,
            "is_correct": is_correct,
            "is_skipped": ans.is_skipped,
            "drug_name": q_row["drug_name"],
        })

    await queries.finish_exam_session(
        db, body.session_id, correct_count, "completed", body.elapsed_seconds,
    )

    total = len(body.answers)
    pct = round(correct_count / total * 100) if total > 0 else 0

    return {
        "session_id": body.session_id,
        "correct": correct_count,
        "total": total,
        "percent": pct,
        "elapsed_seconds": body.elapsed_seconds,
        "details": details,
    }
