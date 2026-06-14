import aiosqlite
import logging

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id              TEXT PRIMARY KEY,
    topic           TEXT NOT NULL,
    subtopic        TEXT,
    question        TEXT NOT NULL,
    option_a        TEXT NOT NULL,
    option_b        TEXT NOT NULL,
    option_c        TEXT NOT NULL,
    option_d        TEXT NOT NULL,
    correct_answer  TEXT NOT NULL,
    drug_name       TEXT,
    difficulty      INTEGER NOT NULL DEFAULT 1 CHECK(difficulty IN (1,2,3)),
    tags            TEXT,
    explanation     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    telegram_id     INTEGER PRIMARY KEY,
    username        TEXT,
    first_name      TEXT,
    last_name       TEXT,
    is_admin        INTEGER NOT NULL DEFAULT 0,
    reminder_time   TEXT,
    registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    last_active_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS training_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(telegram_id),
    question_id     TEXT NOT NULL REFERENCES questions(id),
    chosen_answer   TEXT NOT NULL,
    is_correct      INTEGER NOT NULL CHECK(is_correct IN (0,1)),
    answered_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exam_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(telegram_id),
    topic               TEXT NOT NULL,
    total_questions     INTEGER NOT NULL,
    correct_count       INTEGER NOT NULL DEFAULT 0,
    time_limit_seconds  INTEGER,
    time_limit_choice   TEXT,
    started_at          TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at         TEXT,
    elapsed_seconds     INTEGER,
    status              TEXT NOT NULL DEFAULT 'in_progress'
        CHECK(status IN ('in_progress','completed','abandoned','timeout'))
);

CREATE TABLE IF NOT EXISTS exam_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES exam_sessions(id),
    question_id     TEXT NOT NULL REFERENCES questions(id),
    chosen_answer   TEXT,
    is_correct      INTEGER NOT NULL DEFAULT 0 CHECK(is_correct IN (0,1)),
    is_skipped      INTEGER NOT NULL DEFAULT 0 CHECK(is_skipped IN (0,1)),
    question_order  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS explanation_cache (
    question_id     TEXT PRIMARY KEY REFERENCES questions(id),
    explanation     TEXT NOT NULL,
    generated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_training_user ON training_answers(user_id);
CREATE INDEX IF NOT EXISTS idx_training_question ON training_answers(question_id);
CREATE INDEX IF NOT EXISTS idx_exam_sessions_user ON exam_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_exam_answers_session ON exam_answers(session_id);
"""


async def init_db(path: str) -> None:
    global _db
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()
    # migrations for existing databases
    for table, col, definition in [
        ("users",     "reminder_time", "TEXT"),
        ("questions", "explanation",   "TEXT"),
    ]:
        try:
            await _db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            await _db.commit()
            logger.info("Migration: added column %s.%s", table, col)
        except Exception:
            pass  # column already exists
    logger.info("Database initialised at %s", path)


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    return _db


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None
