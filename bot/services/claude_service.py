import logging
from google import genai
from google.genai import types
from bot.config import config
from bot.database import queries
from bot.database.db import get_db

logger = logging.getLogger(__name__)

_client: genai.Client | None = None

SYSTEM_PROMPT = (
    "Ты — опытный преподаватель фармакологии в медицинском университете. "
    "Помогаешь студентам готовиться к экзаменам. "
    "Пиши на русском языке. Используй точную медицинскую терминологию, "
    "но объясняй сложные понятия доступно. "
    "Не используй Markdown — только обычный текст с эмодзи."
)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.gemini_api_key)
    return _client


def _build_prompt(q) -> str:
    opts = {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]}
    correct_letters = [l.strip() for l in q["correct_answer"].split(",")]
    correct_texts = [f"{l}) {opts[l]}" for l in correct_letters if l in opts]
    correct_str = ", ".join(correct_texts)
    wrong_lines = "\n".join(
        f"{letter}) {text}"
        for letter, text in opts.items()
        if letter not in correct_letters
    )
    multi_note = " (несколько правильных ответов)" if len(correct_letters) > 1 else ""
    return f"""Вопрос по фармакологии:
Тема: {q['topic']} — {q.get('subtopic', '')}
Вопрос: {q['question']}{multi_note}

Варианты: A) {opts['A']}  B) {opts['B']}  C) {opts['C']}  D) {opts['D']}
Правильный ответ: {correct_str}

Дай объяснение строго в таком формате (только текст, без Markdown):

✅ ПРАВИЛЬНЫЙ ОТВЕТ: {correct_str}
[2-3 предложения: механизм действия, фармакокинетика, применение]

❌ НЕПРАВИЛЬНЫЕ ОТВЕТЫ:
{wrong_lines}
[По 1 предложению — почему каждый из них неверен]

💡 ЗАПОМНИ: [мнемоника или клиническая жемчужина]"""


async def get_explanation(question) -> str:
    db = await get_db()
    qid = question["id"]

    cached = await queries.get_cached_explanation(db, qid)
    if cached:
        return cached

    if not config.gemini_api_key:
        return _fallback(question)

    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=config.gemini_model,
            contents=_build_prompt(question),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                max_output_tokens=1024,
            ),
        )
        explanation = response.text.strip()
        await queries.cache_explanation(db, qid, explanation)
        return explanation
    except Exception as e:
        logger.error("Gemini API error for question %s: %s", qid, e)
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
