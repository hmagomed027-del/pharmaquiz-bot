from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.deps import get_user_id
from bot.database.db import get_db
from bot.database import queries

router = APIRouter()

TOPIC_META = {
    "ПНС":                       {"icon": "⚡", "color": "#4A90D9"},
    "ЦНС":                       {"icon": "🧠", "color": "#9B59B6"},
    "ССС":                       {"icon": "❤️", "color": "#E74C3C"},
    "Дыхательная система":       {"icon": "🫁", "color": "#2ECC71"},
    "Пищеварительная система":   {"icon": "🫙", "color": "#F39C12"},
    "Химиотерапия":              {"icon": "⚗️", "color": "#1ABC9C"},
    "Рецептура":                 {"icon": "✍️", "color": "#E67E22"},
    "Противоаллергические":      {"icon": "🤧", "color": "#3498DB"},
    "Противовоспалительные":     {"icon": "🔥", "color": "#E67E22"},
    "Анальгетики":               {"icon": "💊", "color": "#8E44AD"},
    "Средства для наркоза":      {"icon": "😴", "color": "#2C3E50"},
    "Диуретики":                 {"icon": "💧", "color": "#5DADE2"},
    "Средства крови":            {"icon": "🩸", "color": "#C0392B"},
    "Гормоны":                   {"icon": "🧬", "color": "#27AE60"},
    "Витамины":                  {"icon": "🍊", "color": "#F1C40F"},
}


@router.get("/topics")
async def get_topics(user_id: int = Depends(get_user_id)):
    db = await get_db()
    counts = await queries.count_questions_by_topic(db)
    return [
        {"topic": topic, "count": count, **TOPIC_META.get(topic, {"icon": "📚", "color": "#95A5A6"})}
        for topic, count in counts.items()
    ]


@router.get("/question")
async def get_question(
    topic: str,
    exclude: str = "",
    user_id: int = Depends(get_user_id),
):
    db = await get_db()
    exclude_ids = [x for x in exclude.split(",") if x] if exclude else []
    rows = await queries.get_random_questions(db, topic, 1, exclude_ids)
    if not rows:
        return JSONResponse(content=None)
    q = rows[0]
    return {
        "id": q["id"],
        "topic": q["topic"],
        "subtopic": q["subtopic"],
        "question": q["question"],
        "options": {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]},
        "correct_answer": q["correct_answer"],
        "drug_name": q["drug_name"],
    }


@router.get("/explanation/{question_id}")
async def get_explanation(question_id: str, user_id: int = Depends(get_user_id)):
    db = await get_db()
    q_row = await queries.get_question_by_id(db, question_id)
    if not q_row:
        return {"text": "Вопрос не найден."}

    q = {
        "id": q_row["id"],
        "topic": q_row["topic"],
        "subtopic": q_row["subtopic"],
        "question": q_row["question"],
        "option_a": q_row["option_a"],
        "option_b": q_row["option_b"],
        "option_c": q_row["option_c"],
        "option_d": q_row["option_d"],
        "correct_answer": q_row["correct_answer"],
    }

    from bot.services.claude_service import get_explanation as gen_explanation
    text = await gen_explanation(q)
    return {"text": text}
