#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pregenerate explanations for all questions in data/questions/*.json.

Run this script once (or multiple times — it skips questions that already
have an explanation). Results are saved back into the JSON files so they
are committed to the repo and served from there at runtime.

Free-tier limits: 15 RPM / 1500 RPD for gemini-2.5-flash-lite.
At 1399 questions this needs ~2 days of runs (resume with the same command).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import os
import re
import time
import glob
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY", "")
MODEL     = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
DATA_DIR  = Path("data/questions")

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent?key={API_KEY}"
)

SYSTEM_PROMPT = (
    "Ты — опытный преподаватель фармакологии в медицинском университете. "
    "Помогаешь студентам готовиться к экзаменам. "
    "Пиши на русском языке. Используй точную медицинскую терминологию, "
    "но объясняй сложные понятия доступно. "
    "Не используй Markdown — только обычный текст с эмодзи."
)


# ── Gemini ──────────────────────────────────────────────────────────────────

def call_gemini(prompt: str, retries: int = 8) -> str:
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    for attempt in range(retries):
        try:
            r = requests.post(GEMINI_URL, json=body, timeout=60)
            if r.status_code == 429:
                # Short initial wait so RPM window resets, then grow slowly
                wait = 15 * (2 ** attempt)   # 15, 30, 60, 120, 240, 480 ...
                wait = min(wait, 300)          # cap at 5 min
                print(f"  [429] rate limit — wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"  [err {attempt+1}/{retries}] {e} — wait {wait}s", flush=True)
            time.sleep(wait)
    return ""


def build_prompt(q: dict) -> str:
    opts = {
        "A": q["options"]["A"],
        "B": q["options"]["B"],
        "C": q["options"]["C"],
        "D": q["options"]["D"],
    }
    correct = q.get("correct_answer", "")
    correct_letters = [l.strip() for l in correct.split(",")]
    correct_texts   = [f"{l}) {opts[l]}" for l in correct_letters if l in opts]
    correct_str     = ", ".join(correct_texts)
    wrong_lines     = "\n".join(
        f"{l}) {opts[l]}" for l in ("A", "B", "C", "D") if l not in correct_letters
    )
    multi = " (несколько правильных ответов)" if len(correct_letters) > 1 else ""

    return (
        f"Вопрос по фармакологии:\n"
        f"Тема: {q.get('topic', '')} — {q.get('subtopic', '')}\n"
        f"Вопрос: {q['question']}{multi}\n\n"
        f"Варианты: A) {opts['A']}  B) {opts['B']}  C) {opts['C']}  D) {opts['D']}\n"
        f"Правильный ответ: {correct_str}\n\n"
        f"Дай объяснение строго в таком формате (только текст, без Markdown):\n\n"
        f"✅ ПРАВИЛЬНЫЙ ОТВЕТ: {correct_str}\n"
        f"[2-3 предложения: механизм действия, фармакокинетика, применение]\n\n"
        f"❌ НЕПРАВИЛЬНЫЕ ОТВЕТЫ:\n"
        f"{wrong_lines}\n"
        f"[По 1 предложению — почему каждый из них неверен]\n\n"
        f"💡 ЗАПОМНИ: [мнемоника или клиническая жемчужина]"
    )


# ── File helpers ─────────────────────────────────────────────────────────────

def load_file(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def save_file(path: Path, data: list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not API_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env", flush=True)
        return

    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        print(f"No JSON files found in {DATA_DIR}", flush=True)
        return

    # Count work
    total_q = total_done = total_need = 0
    for f in files:
        data = load_file(f)
        need = sum(1 for q in data if isinstance(q, dict) and not q.get("explanation"))
        have = len(data) - need
        total_q    += len(data)
        total_done += have
        total_need += need

    print(f"Всего вопросов: {total_q}", flush=True)
    print(f"Уже есть объяснение: {total_done}", flush=True)
    print(f"Нужно сгенерировать: {total_need}", flush=True)
    print(f"Лимит free tier: ~1500/день → займёт ~{total_need // 1500 + 1} дней\n", flush=True)

    generated = skipped = errors = 0

    for f in files:
        data = load_file(f)
        changed = False

        for i, q in enumerate(data):
            if not isinstance(q, dict):
                continue
            if q.get("explanation"):
                skipped += 1
                continue

            qid = q.get("id", f"?/{i}")
            print(f"[{generated+errors+skipped+1}/{total_q}] {qid} — генерирую...", flush=True)

            prompt = build_prompt(q)
            explanation = call_gemini(prompt)

            if not explanation:
                print(f"  SKIP: пустой ответ от API", flush=True)
                errors += 1
                continue

            q["explanation"] = explanation
            changed = True
            generated += 1
            print(f"  OK ({len(explanation)} символов)", flush=True)

            # Save after every question — safe to interrupt
            save_file(f, data)

            # Stay safely under 15 RPM: 6s gap ≈ 10 RPM
            time.sleep(6)

        if changed:
            print(f"Сохранён {f.name}\n", flush=True)

    print("=" * 60, flush=True)
    print(f"Готово: сгенерировано={generated} пропущено={skipped} ошибок={errors}", flush=True)
    print(f"Осталось без объяснения: {total_need - generated}", flush=True)
    if generated > 0:
        print("Не забудьте сделать git add + git commit!", flush=True)


if __name__ == "__main__":
    main()
