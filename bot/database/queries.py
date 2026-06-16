import json
import asyncpg
from typing import Optional


async def upsert_user(pool: asyncpg.Pool, telegram_id: int, username: str,
                      first_name: str, last_name: str) -> None:
    await pool.execute("""
        INSERT INTO users (telegram_id, username, first_name, last_name)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username       = EXCLUDED.username,
            first_name     = EXCLUDED.first_name,
            last_name      = EXCLUDED.last_name,
            last_active_at = NOW()
    """, telegram_id, username, first_name, last_name)


async def get_user(pool: asyncpg.Pool, telegram_id: int) -> Optional[asyncpg.Record]:
    return await pool.fetchrow(
        "SELECT * FROM users WHERE telegram_id = $1", telegram_id
    )


async def get_all_topics(pool: asyncpg.Pool) -> list[str]:
    rows = await pool.fetch("SELECT DISTINCT topic FROM questions ORDER BY topic")
    return [r["topic"] for r in rows]


async def get_random_questions(pool: asyncpg.Pool, topic: str, count: int,
                               exclude_ids: list[str] | None = None) -> list[asyncpg.Record]:
    if not exclude_ids:
        return await pool.fetch(
            "SELECT * FROM questions WHERE topic = $1 ORDER BY RANDOM() LIMIT $2",
            topic, count,
        )
    placeholders = ",".join(f"${i + 3}" for i in range(len(exclude_ids)))
    rows = await pool.fetch(
        f"SELECT * FROM questions WHERE topic = $1 AND id NOT IN ({placeholders})"
        f" ORDER BY RANDOM() LIMIT $2",
        topic, count, *exclude_ids,
    )
    if len(rows) < count:
        needed = count - len(rows)
        existing_ids = {r["id"] for r in rows}
        extra = await pool.fetch(
            "SELECT * FROM questions WHERE topic = $1 ORDER BY RANDOM() LIMIT $2",
            topic, needed,
        )
        rows = list(rows) + [r for r in extra if r["id"] not in existing_ids]
    return rows


async def get_question_by_id(pool: asyncpg.Pool, question_id: str) -> Optional[asyncpg.Record]:
    return await pool.fetchrow("SELECT * FROM questions WHERE id = $1", question_id)


async def get_recent_training_question_ids(pool: asyncpg.Pool, user_id: int,
                                           topic: str, limit: int = 50) -> list[str]:
    rows = await pool.fetch("""
        SELECT ta.question_id FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        WHERE ta.user_id = $1 AND q.topic = $2
        ORDER BY ta.answered_at DESC LIMIT $3
    """, user_id, topic, limit)
    return [r["question_id"] for r in rows]


async def save_training_answer(pool: asyncpg.Pool, user_id: int,
                               question_id: str, chosen: str, is_correct: bool) -> None:
    await pool.execute(
        "INSERT INTO training_answers (user_id, question_id, chosen_answer, is_correct)"
        " VALUES ($1, $2, $3, $4)",
        user_id, question_id, chosen, int(is_correct),
    )


async def get_user_stats(pool: asyncpg.Pool, user_id: int) -> dict:
    rows = await pool.fetch("""
        SELECT q.topic,
               COUNT(*)           AS total,
               COALESCE(SUM(ta.is_correct), 0) AS correct
        FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        WHERE ta.user_id = $1
        GROUP BY q.topic
        ORDER BY q.topic
    """, user_id)
    topics = [{"topic": r["topic"], "total": r["total"], "correct": r["correct"]} for r in rows]
    total   = sum(t["total"]   for t in topics)
    correct = sum(t["correct"] for t in topics)
    row = await pool.fetchrow("""
        SELECT COUNT(*) AS cnt FROM exam_sessions
        WHERE user_id = $1 AND status = 'completed'
    """, user_id)
    exams = row["cnt"] if row else 0
    return {"topics": topics, "total": total, "correct": correct, "exams_completed": exams}


async def get_today_training_stats(pool: asyncpg.Pool, user_id: int) -> dict:
    row = await pool.fetchrow("""
        SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct
        FROM training_answers
        WHERE user_id = $1 AND answered_at::date = CURRENT_DATE
    """, user_id)
    return {"total": row["total"] or 0, "correct": row["correct"] or 0}


async def create_exam_session(pool: asyncpg.Pool, user_id: int, topic: str,
                              total_questions: int, time_limit_seconds: Optional[int],
                              time_limit_choice: Optional[str]) -> int:
    session_id = await pool.fetchval("""
        INSERT INTO exam_sessions
            (user_id, topic, total_questions, time_limit_seconds, time_limit_choice)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
    """, user_id, topic, total_questions, time_limit_seconds, time_limit_choice)
    return session_id


async def save_exam_answer(pool: asyncpg.Pool, session_id: int, question_id: str,
                           chosen: Optional[str], is_correct: bool, is_skipped: bool,
                           order: int) -> None:
    await pool.execute("""
        INSERT INTO exam_answers
            (session_id, question_id, chosen_answer, is_correct, is_skipped, question_order)
        VALUES ($1, $2, $3, $4, $5, $6)
    """, session_id, question_id, chosen, int(is_correct), int(is_skipped), order)


async def finish_exam_session(pool: asyncpg.Pool, session_id: int,
                              correct_count: int, status: str, elapsed_seconds: int) -> None:
    await pool.execute("""
        UPDATE exam_sessions
        SET correct_count = $1, status = $2, finished_at = NOW(), elapsed_seconds = $3
        WHERE id = $4
    """, correct_count, status, elapsed_seconds, session_id)


async def get_exam_session(pool: asyncpg.Pool, session_id: int) -> Optional[asyncpg.Record]:
    return await pool.fetchrow("SELECT * FROM exam_sessions WHERE id = $1", session_id)


async def get_exam_answers(pool: asyncpg.Pool, session_id: int) -> list[asyncpg.Record]:
    return await pool.fetch("""
        SELECT ea.*, q.question, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_answer, q.topic, q.subtopic, q.drug_name, q.id AS qid
        FROM exam_answers ea
        JOIN questions q ON q.id = ea.question_id
        WHERE ea.session_id = $1
        ORDER BY ea.question_order
    """, session_id)


async def get_cached_explanation(pool: asyncpg.Pool, question_id: str) -> Optional[str]:
    row = await pool.fetchrow(
        "SELECT explanation FROM explanation_cache WHERE question_id = $1", question_id
    )
    return row["explanation"] if row else None


async def cache_explanation(pool: asyncpg.Pool, question_id: str, explanation: str) -> None:
    await pool.execute("""
        INSERT INTO explanation_cache (question_id, explanation)
        VALUES ($1, $2)
        ON CONFLICT(question_id) DO UPDATE SET
            explanation  = EXCLUDED.explanation,
            generated_at = NOW()
    """, question_id, explanation)


async def question_exists(pool: asyncpg.Pool, question_id: str) -> bool:
    row = await pool.fetchrow("SELECT 1 FROM questions WHERE id = $1", question_id)
    return row is not None


async def insert_question(pool: asyncpg.Pool, q: dict) -> None:
    tags = json.dumps(q.get("tags", []), ensure_ascii=False)
    await pool.execute("""
        INSERT INTO questions
            (id, topic, subtopic, question,
             option_a, option_b, option_c, option_d,
             correct_answer, drug_name, difficulty, tags, explanation)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT(id) DO UPDATE SET
            explanation = COALESCE(EXCLUDED.explanation, questions.explanation)
    """,
        q["id"], q["topic"], q.get("subtopic"), q["question"],
        q["options"]["A"], q["options"]["B"], q["options"]["C"], q["options"]["D"],
        q["correct_answer"], q.get("drug_name"), q.get("difficulty", 1), tags,
        q.get("explanation"),
    )


async def count_questions_by_topic(pool: asyncpg.Pool) -> dict:
    rows = await pool.fetch("SELECT topic, COUNT(*) AS cnt FROM questions GROUP BY topic")
    return {r["topic"]: r["cnt"] for r in rows}


async def get_admin_overview(pool: asyncpg.Pool) -> dict:
    row = await pool.fetchrow("SELECT COUNT(*) AS cnt FROM users")
    total_users = row["cnt"]

    row = await pool.fetchrow("""
        SELECT COUNT(DISTINCT user_id) AS cnt FROM (
            SELECT user_id FROM training_answers WHERE answered_at::date = CURRENT_DATE
            UNION
            SELECT user_id FROM exam_sessions
            WHERE started_at::date = CURRENT_DATE AND status = 'completed'
        ) t
    """)
    active_today = row["cnt"]

    row = await pool.fetchrow("""
        SELECT COUNT(DISTINCT user_id) AS cnt FROM (
            SELECT user_id FROM training_answers
            WHERE answered_at >= NOW() - INTERVAL '7 days'
            UNION
            SELECT user_id FROM exam_sessions
            WHERE started_at >= NOW() - INTERVAL '7 days' AND status = 'completed'
        ) t
    """)
    active_week = row["cnt"]

    row = await pool.fetchrow("SELECT COUNT(*) AS cnt FROM training_answers")
    total_training = row["cnt"]

    row = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM exam_sessions WHERE status = 'completed'"
    )
    total_exams = row["cnt"]

    return {
        "total_users":    total_users,
        "active_today":   active_today,
        "active_week":    active_week,
        "total_training": total_training,
        "total_exams":    total_exams,
    }


async def get_training_difficulty_by_topic(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch("""
        SELECT q.topic,
               COUNT(*) AS total,
               COALESCE(SUM(ta.is_correct), 0) AS correct,
               ROUND((100.0 * COALESCE(SUM(ta.is_correct), 0) / COUNT(*))::numeric, 1) AS pct
        FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        GROUP BY q.topic
        HAVING COUNT(*) >= 5
        ORDER BY pct ASC
    """)
    return [dict(r) for r in rows]


async def get_exam_stats_by_topic(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch("""
        SELECT topic,
               COUNT(*) AS sessions,
               ROUND(AVG(100.0 * correct_count / total_questions)::numeric, 1) AS avg_pct,
               MIN(ROUND((100.0 * correct_count / total_questions)::numeric, 1)) AS min_pct,
               MAX(ROUND((100.0 * correct_count / total_questions)::numeric, 1)) AS max_pct
        FROM exam_sessions
        WHERE status = 'completed' AND total_questions > 0
        GROUP BY topic
        ORDER BY avg_pct ASC
    """)
    return [dict(r) for r in rows]


async def get_hardest_questions(pool: asyncpg.Pool, limit: int = 8) -> list[dict]:
    rows = await pool.fetch("""
        SELECT q.id, q.question, q.topic, q.subtopic,
               COUNT(*) AS total,
               COALESCE(SUM(ta.is_correct), 0) AS correct,
               ROUND((100.0 * COALESCE(SUM(ta.is_correct), 0) / COUNT(*))::numeric, 1) AS pct
        FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        GROUP BY q.id, q.question, q.topic, q.subtopic
        HAVING COUNT(*) >= 3
        ORDER BY pct ASC, total DESC
        LIMIT $1
    """, limit)
    return [dict(r) for r in rows]


async def get_all_users(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch("SELECT telegram_id FROM users")


async def set_reminder_time(pool: asyncpg.Pool, telegram_id: int,
                            time_str: Optional[str]) -> None:
    await pool.execute(
        "UPDATE users SET reminder_time = $1 WHERE telegram_id = $2",
        time_str, telegram_id,
    )


async def get_users_for_reminder(pool: asyncpg.Pool, time_str: str) -> list[asyncpg.Record]:
    return await pool.fetch(
        "SELECT telegram_id, first_name FROM users WHERE reminder_time = $1",
        time_str,
    )
