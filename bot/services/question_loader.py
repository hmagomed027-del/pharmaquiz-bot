import json
import logging
import os
import glob
import aiosqlite
from bot.database import queries

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"id", "topic", "question", "options"}
REQUIRED_OPTIONS = {"A", "B", "C", "D"}


def _normalize_correct_answer(q: dict) -> str | None:
    """Return comma-joined correct answers string, e.g. 'A' or 'A,C'."""
    if "correct_answers" in q and isinstance(q["correct_answers"], list):
        letters = sorted(set(q["correct_answers"]))
        if all(l in REQUIRED_OPTIONS for l in letters) and letters:
            return ",".join(letters)
        return None
    val = q.get("correct_answer")
    if val in REQUIRED_OPTIONS:
        return val
    return None


def _validate(q: dict, filepath: str) -> bool:
    missing = REQUIRED_FIELDS - q.keys()
    if missing:
        logger.warning("Question in %s missing fields: %s — skipping", filepath, missing)
        return False
    if not isinstance(q.get("options"), dict) or set(q["options"].keys()) != REQUIRED_OPTIONS:
        logger.warning("Question %s in %s: options must have keys A,B,C,D — skipping", q.get("id"), filepath)
        return False
    if _normalize_correct_answer(q) is None:
        logger.warning("Question %s in %s: invalid correct_answer/correct_answers — skipping", q.get("id"), filepath)
        return False
    return True


async def load_questions_from_file(db: aiosqlite.Connection, filepath: str) -> int:
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Failed to read %s: %s", filepath, e)
        return 0

    if not isinstance(data, list):
        logger.error("%s: expected JSON array at root", filepath)
        return 0

    inserted = 0
    for q in data:
        if not _validate(q, filepath):
            continue
        if await queries.question_exists(db, q["id"]):
            continue
        try:
            q_normalized = dict(q)
            q_normalized["correct_answer"] = _normalize_correct_answer(q)
            await queries.insert_question(db, q_normalized)
            inserted += 1
        except Exception as e:
            logger.error("Failed to insert question %s: %s", q.get("id"), e)

    if inserted:
        await db.commit()
    return inserted


async def load_all_questions(db: aiosqlite.Connection, questions_dir: str = "data/questions") -> int:
    pattern = os.path.join(questions_dir, "*.json")
    files = glob.glob(pattern)
    if not files:
        logger.warning("No JSON files found in %s", questions_dir)
        return 0

    total = 0
    for fp in sorted(files):
        count = await load_questions_from_file(db, fp)
        logger.info("Loaded %d new questions from %s", count, fp)
        total += count
    logger.info("Total new questions loaded: %d", total)
    return total
