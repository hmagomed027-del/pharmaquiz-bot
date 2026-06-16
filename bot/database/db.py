import asyncpg
import logging

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# Each statement must be separate — asyncpg does not support multi-statement strings.
_SCHEMA = [
    """
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
        difficulty      SMALLINT NOT NULL DEFAULT 1 CHECK(difficulty IN (1,2,3)),
        tags            TEXT,
        explanation     TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        telegram_id     BIGINT PRIMARY KEY,
        username        TEXT,
        first_name      TEXT,
        last_name       TEXT,
        is_admin        SMALLINT NOT NULL DEFAULT 0,
        reminder_time   TEXT,
        registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_active_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_answers (
        id              BIGSERIAL PRIMARY KEY,
        user_id         BIGINT NOT NULL REFERENCES users(telegram_id),
        question_id     TEXT NOT NULL REFERENCES questions(id),
        chosen_answer   TEXT NOT NULL,
        is_correct      SMALLINT NOT NULL CHECK(is_correct IN (0,1)),
        answered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_sessions (
        id                  BIGSERIAL PRIMARY KEY,
        user_id             BIGINT NOT NULL REFERENCES users(telegram_id),
        topic               TEXT NOT NULL,
        total_questions     INTEGER NOT NULL,
        correct_count       INTEGER NOT NULL DEFAULT 0,
        time_limit_seconds  INTEGER,
        time_limit_choice   TEXT,
        started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        finished_at         TIMESTAMPTZ,
        elapsed_seconds     INTEGER,
        status              TEXT NOT NULL DEFAULT 'in_progress'
            CHECK(status IN ('in_progress','completed','abandoned','timeout'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_answers (
        id              BIGSERIAL PRIMARY KEY,
        session_id      BIGINT NOT NULL REFERENCES exam_sessions(id),
        question_id     TEXT NOT NULL REFERENCES questions(id),
        chosen_answer   TEXT,
        is_correct      SMALLINT NOT NULL DEFAULT 0 CHECK(is_correct IN (0,1)),
        is_skipped      SMALLINT NOT NULL DEFAULT 0 CHECK(is_skipped IN (0,1)),
        question_order  INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS explanation_cache (
        question_id     TEXT PRIMARY KEY REFERENCES questions(id),
        explanation     TEXT NOT NULL,
        generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_training_user     ON training_answers(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_training_question ON training_answers(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_sessions_user ON exam_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_answers_session ON exam_answers(session_id)",
]


async def init_db(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        for sql in _SCHEMA:
            await conn.execute(sql)
    logger.info("PostgreSQL pool initialised")


async def get_db() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    return _pool


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
