import json
import time
import aiosqlite
from typing import Optional


async def upsert_user(db: aiosqlite.Connection, telegram_id: int, username: str,
                      first_name: str, last_name: str) -> None:
    await db.execute("""
        INSERT INTO users (telegram_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            last_active_at = datetime('now')
    """, (telegram_id, username, first_name, last_name))
    await db.commit()


async def get_user(db: aiosqlite.Connection, telegram_id: int) -> Optional[aiosqlite.Row]:
    async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
        return await cur.fetchone()


async def get_all_topics(db: aiosqlite.Connection) -> list[str]:
    async with db.execute("SELECT DISTINCT topic FROM questions ORDER BY topic") as cur:
        rows = await cur.fetchall()
    return [r["topic"] for r in rows]


async def get_random_questions(db: aiosqlite.Connection, topic: str, count: int,
                               exclude_ids: list[str] | None = None) -> list[aiosqlite.Row]:
    if not exclude_ids:
        async with db.execute(
            "SELECT * FROM questions WHERE topic = ? ORDER BY RANDOM() LIMIT ?",
            (topic, count)
        ) as cur:
            return await cur.fetchall()
    placeholders = ",".join("?" * len(exclude_ids))
    async with db.execute(
        f"SELECT * FROM questions WHERE topic = ? AND id NOT IN ({placeholders}) "
        f"ORDER BY RANDOM() LIMIT ?",
        [topic, *exclude_ids, count]
    ) as cur:
        rows = await cur.fetchall()
    if len(rows) < count:
        needed = count - len(rows)
        existing_ids = [r["id"] for r in rows]
        async with db.execute(
            "SELECT * FROM questions WHERE topic = ? ORDER BY RANDOM() LIMIT ?",
            (topic, needed)
        ) as cur:
            extra = await cur.fetchall()
        rows = list(rows) + [r for r in extra if r["id"] not in existing_ids]
    return rows


async def get_question_by_id(db: aiosqlite.Connection, question_id: str) -> Optional[aiosqlite.Row]:
    async with db.execute("SELECT * FROM questions WHERE id = ?", (question_id,)) as cur:
        return await cur.fetchone()


async def get_recent_training_question_ids(db: aiosqlite.Connection, user_id: int,
                                           topic: str, limit: int = 50) -> list[str]:
    async with db.execute("""
        SELECT ta.question_id FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        WHERE ta.user_id = ? AND q.topic = ?
        ORDER BY ta.answered_at DESC LIMIT ?
    """, (user_id, topic, limit)) as cur:
        rows = await cur.fetchall()
    return [r["question_id"] for r in rows]


async def save_training_answer(db: aiosqlite.Connection, user_id: int,
                               question_id: str, chosen: str, is_correct: bool) -> None:
    await db.execute(
        "INSERT INTO training_answers (user_id, question_id, chosen_answer, is_correct) VALUES (?,?,?,?)",
        (user_id, question_id, chosen, int(is_correct))
    )
    await db.commit()


async def get_user_stats(db: aiosqlite.Connection, user_id: int) -> dict:
    async with db.execute("""
        SELECT q.topic,
               COUNT(*) as total,
               SUM(ta.is_correct) as correct
        FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        WHERE ta.user_id = ?
        GROUP BY q.topic
        ORDER BY q.topic
    """, (user_id,)) as cur:
        rows = await cur.fetchall()
    topics = [{"topic": r["topic"], "total": r["total"], "correct": r["correct"]} for r in rows]
    total = sum(t["total"] for t in topics)
    correct = sum(t["correct"] for t in topics)
    async with db.execute("""
        SELECT COUNT(*) as cnt FROM exam_sessions
        WHERE user_id = ? AND status = 'completed'
    """, (user_id,)) as cur:
        row = await cur.fetchone()
    exams = row["cnt"] if row else 0
    return {"topics": topics, "total": total, "correct": correct, "exams_completed": exams}


async def get_today_training_stats(db: aiosqlite.Connection, user_id: int) -> dict:
    async with db.execute("""
        SELECT COUNT(*) as total, SUM(is_correct) as correct
        FROM training_answers
        WHERE user_id = ? AND date(answered_at) = date('now')
    """, (user_id,)) as cur:
        row = await cur.fetchone()
    total = row["total"] or 0
    correct = row["correct"] or 0
    return {"total": total, "correct": correct}


async def create_exam_session(db: aiosqlite.Connection, user_id: int, topic: str,
                              total_questions: int, time_limit_seconds: Optional[int],
                              time_limit_choice: Optional[str]) -> int:
    async with db.execute("""
        INSERT INTO exam_sessions (user_id, topic, total_questions, time_limit_seconds, time_limit_choice)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, topic, total_questions, time_limit_seconds, time_limit_choice)) as cur:
        session_id = cur.lastrowid
    await db.commit()
    return session_id


async def save_exam_answer(db: aiosqlite.Connection, session_id: int, question_id: str,
                           chosen: Optional[str], is_correct: bool, is_skipped: bool,
                           order: int) -> None:
    await db.execute("""
        INSERT INTO exam_answers (session_id, question_id, chosen_answer, is_correct, is_skipped, question_order)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, question_id, chosen, int(is_correct), int(is_skipped), order))
    await db.commit()


async def finish_exam_session(db: aiosqlite.Connection, session_id: int,
                              correct_count: int, status: str, elapsed_seconds: int) -> None:
    await db.execute("""
        UPDATE exam_sessions
        SET correct_count = ?, status = ?, finished_at = datetime('now'), elapsed_seconds = ?
        WHERE id = ?
    """, (correct_count, status, elapsed_seconds, session_id))
    await db.commit()


async def get_exam_session(db: aiosqlite.Connection, session_id: int) -> Optional[aiosqlite.Row]:
    async with db.execute("SELECT * FROM exam_sessions WHERE id = ?", (session_id,)) as cur:
        return await cur.fetchone()


async def get_exam_answers(db: aiosqlite.Connection, session_id: int) -> list[aiosqlite.Row]:
    async with db.execute("""
        SELECT ea.*, q.question, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_answer, q.topic, q.subtopic, q.drug_name, q.id as qid
        FROM exam_answers ea
        JOIN questions q ON q.id = ea.question_id
        WHERE ea.session_id = ?
        ORDER BY ea.question_order
    """, (session_id,)) as cur:
        return await cur.fetchall()


async def get_cached_explanation(db: aiosqlite.Connection, question_id: str) -> Optional[str]:
    async with db.execute("SELECT explanation FROM explanation_cache WHERE question_id = ?", (question_id,)) as cur:
        row = await cur.fetchone()
    return row["explanation"] if row else None


async def cache_explanation(db: aiosqlite.Connection, question_id: str, explanation: str) -> None:
    await db.execute("""
        INSERT INTO explanation_cache (question_id, explanation)
        VALUES (?, ?)
        ON CONFLICT(question_id) DO UPDATE SET explanation = excluded.explanation,
            generated_at = datetime('now')
    """, (question_id, explanation))
    await db.commit()


async def question_exists(db: aiosqlite.Connection, question_id: str) -> bool:
    async with db.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)) as cur:
        return await cur.fetchone() is not None


async def insert_question(db: aiosqlite.Connection, q: dict) -> None:
    tags = json.dumps(q.get("tags", []), ensure_ascii=False)
    await db.execute("""
        INSERT INTO questions (id, topic, subtopic, question, option_a, option_b, option_c, option_d,
                               correct_answer, drug_name, difficulty, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        q["id"], q["topic"], q.get("subtopic"), q["question"],
        q["options"]["A"], q["options"]["B"], q["options"]["C"], q["options"]["D"],
        q["correct_answer"], q.get("drug_name"), q.get("difficulty", 1), tags
    ))


async def count_questions_by_topic(db: aiosqlite.Connection) -> dict:
    async with db.execute("SELECT topic, COUNT(*) as cnt FROM questions GROUP BY topic") as cur:
        rows = await cur.fetchall()
    return {r["topic"]: r["cnt"] for r in rows}


async def get_admin_overview(db: aiosqlite.Connection) -> dict:
    async with db.execute("SELECT COUNT(*) as cnt FROM users") as cur:
        total_users = (await cur.fetchone())["cnt"]
    async with db.execute("""
        SELECT COUNT(DISTINCT user_id) as cnt FROM (
            SELECT user_id FROM training_answers WHERE date(answered_at) = date('now')
            UNION
            SELECT user_id FROM exam_sessions
              WHERE date(started_at) = date('now') AND status = 'completed'
        )
    """) as cur:
        active_today = (await cur.fetchone())["cnt"]
    async with db.execute("""
        SELECT COUNT(DISTINCT user_id) as cnt FROM (
            SELECT user_id FROM training_answers
              WHERE answered_at >= datetime('now', '-7 days')
            UNION
            SELECT user_id FROM exam_sessions
              WHERE started_at >= datetime('now', '-7 days') AND status = 'completed'
        )
    """) as cur:
        active_week = (await cur.fetchone())["cnt"]
    async with db.execute("SELECT COUNT(*) as cnt FROM training_answers") as cur:
        total_training = (await cur.fetchone())["cnt"]
    async with db.execute(
        "SELECT COUNT(*) as cnt FROM exam_sessions WHERE status = 'completed'"
    ) as cur:
        total_exams = (await cur.fetchone())["cnt"]
    return {
        "total_users": total_users,
        "active_today": active_today,
        "active_week": active_week,
        "total_training": total_training,
        "total_exams": total_exams,
    }


async def get_training_difficulty_by_topic(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute("""
        SELECT q.topic,
               COUNT(*) as total,
               SUM(ta.is_correct) as correct,
               ROUND(100.0 * SUM(ta.is_correct) / COUNT(*), 1) as pct
        FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        GROUP BY q.topic
        HAVING COUNT(*) >= 5
        ORDER BY pct ASC
    """) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_exam_stats_by_topic(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute("""
        SELECT topic,
               COUNT(*) as sessions,
               ROUND(AVG(100.0 * correct_count / total_questions), 1) as avg_pct,
               MIN(ROUND(100.0 * correct_count / total_questions, 1)) as min_pct,
               MAX(ROUND(100.0 * correct_count / total_questions, 1)) as max_pct
        FROM exam_sessions
        WHERE status = 'completed' AND total_questions > 0
        GROUP BY topic
        ORDER BY avg_pct ASC
    """) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_hardest_questions(db: aiosqlite.Connection, limit: int = 8) -> list[dict]:
    async with db.execute("""
        SELECT q.id, q.question, q.topic, q.subtopic,
               COUNT(*) as total,
               SUM(ta.is_correct) as correct,
               ROUND(100.0 * SUM(ta.is_correct) / COUNT(*), 1) as pct
        FROM training_answers ta
        JOIN questions q ON q.id = ta.question_id
        GROUP BY ta.question_id
        HAVING COUNT(*) >= 3
        ORDER BY pct ASC, total DESC
        LIMIT ?
    """, (limit,)) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_all_users(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    async with db.execute("SELECT telegram_id FROM users") as cur:
        return await cur.fetchall()


async def set_reminder_time(db: aiosqlite.Connection, telegram_id: int, time_str: Optional[str]) -> None:
    await db.execute(
        "UPDATE users SET reminder_time = ? WHERE telegram_id = ?",
        (time_str, telegram_id)
    )
    await db.commit()


async def get_users_for_reminder(db: aiosqlite.Connection, time_str: str) -> list[aiosqlite.Row]:
    """Возвращает пользователей у которых reminder_time совпадает и нет активности 23+ часов.

    Активность = последний ответ в тренировке ИЛИ последний завершённый экзамен.
    Если хоть одно из них было < 23ч назад — напоминание не отправляем.
    """
    async with db.execute("""
        SELECT u.telegram_id, u.first_name
        FROM users u
        WHERE u.reminder_time = ?
          AND (
            (
              SELECT MAX(ts)
              FROM (
                SELECT MAX(answered_at) AS ts FROM training_answers WHERE user_id = u.telegram_id
                UNION ALL
                SELECT MAX(finished_at) AS ts FROM exam_sessions
                  WHERE user_id = u.telegram_id AND finished_at IS NOT NULL
              )
            ) IS NULL
            OR (
              julianday('now') - julianday((
                SELECT MAX(ts)
                FROM (
                  SELECT MAX(answered_at) AS ts FROM training_answers WHERE user_id = u.telegram_id
                  UNION ALL
                  SELECT MAX(finished_at) AS ts FROM exam_sessions
                    WHERE user_id = u.telegram_id AND finished_at IS NOT NULL
                )
              ))
            ) * 24 >= 23
          )
    """, (time_str,)) as cur:
        return await cur.fetchall()
