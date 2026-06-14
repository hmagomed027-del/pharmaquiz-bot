import logging
from bot.database import queries
from bot.database.db import get_db

logger = logging.getLogger(__name__)


async def get_explanation(question) -> str:
    """Return pre-stored explanation from DB cache or question's built-in field.

    Gemini API is NOT called at runtime. All explanations must be pre-generated
    via pregenerate_explanations.py and committed to the repo.
    """
    db = await get_db()
    qid = question["id"]

    # 1. Fastest path: explanation already cached in DB
    cached = await queries.get_cached_explanation(db, qid)
    if cached:
        return cached

    # 2. Built-in explanation stored in questions.explanation column
    try:
        builtin = question["explanation"]
    except (KeyError, IndexError, TypeError):
        builtin = None
    if builtin:
        await queries.cache_explanation(db, qid, builtin)
        return builtin

    # 3. No explanation available — show structured fallback from question data
    return _fallback(question)


def _fallback(question) -> str:
    opts = {"A": question["option_a"], "B": question["option_b"],
            "C": question["option_c"], "D": question["option_d"]}
    correct_letters = [l.strip() for l in question["correct_answer"].split(",")]
    correct_str = ", ".join(f"{l}) {opts[l]}" for l in correct_letters if l in opts)

    # Use built-in explanation if the question has one stored in the DB
    try:
        builtin = question["explanation"]
    except (KeyError, IndexError):
        builtin = None
    if builtin:
        return f"✅ ПРАВИЛЬНЫЙ ОТВЕТ: {correct_str}\n\n{builtin}"

    # Construct a useful message from the question data itself
    wrong = [(l, opts[l]) for l in ("A", "B", "C", "D") if l not in correct_letters]
    lines = [
        f"✅ ПРАВИЛЬНЫЙ ОТВЕТ:",
        f"{correct_str}",
        "",
        "❌ Неверные варианты:",
    ]
    for l, text in wrong:
        lines.append(f"{l}) {text}")
    lines += ["", "💡 ЗАПОМНИ: Повторите эту тему по учебнику — ИИ-объяснение временно недоступно."]
    return "\n".join(lines)
