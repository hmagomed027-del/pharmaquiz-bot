import html as html_module
import re
import time
from typing import Optional


_MD_SPECIAL = r"\_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    return re.sub(r"([_*\[\]()~`>#\+\-=|{}.!\\])", r"\\\1", str(text))


def format_question(question, index: int, total: int,
                    started_at: Optional[float] = None,
                    time_limit: Optional[int] = None) -> str:
    opts = {
        "A": question["option_a"],
        "B": question["option_b"],
        "C": question["option_c"],
        "D": question["option_d"],
    }
    timer_line = ""
    if started_at is not None:
        elapsed = int(time.time() - started_at)
        if time_limit:
            remaining = max(0, time_limit - elapsed)
            m, s = divmod(remaining, 60)
            timer_line = f"\n⏱ Осталось: {m:02d}:{s:02d}"
        else:
            m, s = divmod(elapsed, 60)
            timer_line = f"\n⏱ {m:02d}:{s:02d}"

    lines = [
        f"📋 *Вопрос {index}/{total}*{escape_md(timer_line)}",
        f"🏷 _{escape_md(question['topic'])}",
    ]
    if question.get("subtopic"):
        lines[-1] += f" — {escape_md(question['subtopic'])}_"
    else:
        lines[-1] += "_"

    lines.append("")
    lines.append(escape_md(question["question"]))
    lines.append("")
    for letter, text in opts.items():
        lines.append(f"*{letter}\\)* {escape_md(text)}")
    return "\n".join(lines)


def format_explanation(explanation: str, is_correct: bool, chosen: str, correct: str) -> str:
    if is_correct:
        header = "✅ <b>Верно!</b>"
    else:
        header = f"❌ <b>Неверно</b> — правильный ответ: <b>{html_module.escape(correct)}</b>"
    return f"{header}\n\n{html_module.escape(explanation)}"


def format_stats(stats: dict, first_name: str) -> str:
    lines = [
        f"📊 *Статистика — {escape_md(first_name)}*",
        "",
    ]
    total = stats["total"]
    correct = stats["correct"]
    pct = round(correct / total * 100) if total > 0 else 0
    lines.append(f"Всего ответов: *{total}*   Правильных: *{correct}* \\({pct}%\\)")
    lines.append(f"Экзаменов завершено: *{stats['exams_completed']}*")
    if stats["topics"]:
        lines.append("")
        lines.append("*По темам:*")
        for t in stats["topics"]:
            p = round(t["correct"] / t["total"] * 100) if t["total"] > 0 else 0
            bar = _progress_bar(p)
            lines.append(f"{escape_md(t['topic'])}: {bar} {p}% \\({t['correct']}/{t['total']}\\)")
    return "\n".join(lines)


def format_exam_result(session, answers: list) -> str:
    total = session["total_questions"]
    correct = session["correct_count"]
    pct = round(correct / total * 100) if total > 0 else 0
    elapsed = session["elapsed_seconds"] or 0
    em, es = divmod(elapsed, 60)

    emoji = "🏆" if pct >= 90 else "✅" if pct >= 70 else "⚠️" if pct >= 50 else "❌"

    lines = [
        f"{emoji} *Результат экзамена*",
        "",
        f"Тема: *{escape_md(session['topic'])}*",
        f"Правильных: *{correct}/{total}* — *{pct}%*",
        f"⏱ Время: {em:02d}:{es:02d}",
    ]
    if session["time_limit_seconds"]:
        lm, ls = divmod(session["time_limit_seconds"], 60)
        lines[-1] += f" из {lm:02d}:{ls:02d}"

    wrong = [a for a in answers if not a["is_correct"] and not a["is_skipped"]]
    skipped = [a for a in answers if a["is_skipped"]]
    if skipped:
        lines.append(f"Пропущено: *{len(skipped)}*")

    if wrong:
        lines.append("")
        lines.append(f"Ошибок: *{len(wrong)}*")

    lines.append("")
    lines.append(_verdict(pct))
    return "\n".join(lines)


def format_today_progress(stats: dict) -> str:
    total = stats["total"]
    correct = stats["correct"]
    if total == 0:
        return ""
    pct = round(correct / total * 100)
    return f"📈 Сегодня: {total} ✅ | Правильно: {correct} \\({pct}%\\)"


def _progress_bar(pct: int, length: int = 8) -> str:
    filled = round(pct / 100 * length)
    return "█" * filled + "░" * (length - filled)


def _verdict(pct: int) -> str:
    if pct >= 90:
        return "🏆 Отлично\\! Вы готовы к экзамену\\!"
    if pct >= 70:
        return "✅ Хороший результат\\! Повторите слабые темы\\."
    if pct >= 50:
        return "⚠️ Нужно больше практики\\."
    return "❌ Рекомендуем повторить материал и попробовать снова\\."
