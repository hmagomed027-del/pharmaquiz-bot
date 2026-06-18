#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix biased MCQ options: if the correct answer is ≥2× longer than the
longest wrong answer, strip the parenthetical / mechanism chain that
gives it away, making all options roughly the same length.

Runs in-place over data/questions/*.json and data/classifications/*.json.
Safe to re-run (idempotent — already-fixed questions are skipped).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import re
import glob
import os
from pathlib import Path

# ── Heuristic fixes ──────────────────────────────────────────────────────────

def _strip_parenthetical(text: str) -> str:
    """'Drug X (long explanation)' → 'Drug X'"""
    m = re.match(r'^(.+?)\s*\((.{8,})\)\s*$', text)
    if m:
        return m.group(1).strip()
    return text


def _strip_mechanism_chain(text: str) -> str:
    """'Step A → step B → step C' → 'Step A'"""
    if ' → ' in text or ' -> ' in text:
        return re.split(r'\s*[-–—>→]+\s*', text)[0].strip()
    return text


def _strip_trailing_clause(text: str) -> str:
    """'X, что приводит к Y' → 'X'; 'X за счёт Y' → 'X'"""
    for pattern in (
        r',\s+что\s+', r',\s+вследствие\s+', r',\s+поэтому\s+',
        r'\s+за счёт\s+', r'\s+путём\s+', r'\s+посредством\s+',
        r'\s+при этом\s+',
    ):
        text = re.split(pattern, text, maxsplit=1)[0].strip()
    return text


def _shorten(text: str, target_len: int) -> str:
    """Apply semantic fixes only — no hard truncation to avoid broken sentences.

    Returns the original text unchanged if none of the heuristics fire.
    This means some legitimately-long correct answers remain untouched;
    only answers that embed an explanation (parenthetical / chain) are fixed.
    """
    t = text
    for fix in (_strip_parenthetical, _strip_mechanism_chain, _strip_trailing_clause):
        if len(t) <= target_len:
            break
        t = fix(t)
    return t.rstrip(" ,;:")


# ── Per-file processor ───────────────────────────────────────────────────────

def fix_file(path: Path) -> tuple[int, int]:
    """Returns (questions_checked, questions_fixed)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    checked = fixed = 0

    for q in data:
        if not isinstance(q, dict):
            continue
        opts = q.get("options") or {}
        if not isinstance(opts, dict):
            continue

        correct_raw = q.get("correct_answer") or q.get("correct_answers") or ""
        if isinstance(correct_raw, list):
            correct_letters = correct_raw
        else:
            correct_letters = [x.strip() for x in str(correct_raw).split(",") if x.strip()]

        # Only fix single-answer questions; multi-answer bias is rarer
        if len(correct_letters) != 1:
            continue
        c = correct_letters[0]
        if c not in opts:
            continue

        correct_text = str(opts[c])
        other_lens = [len(str(opts.get(l, ""))) for l in ("A", "B", "C", "D") if l != c and l in opts]
        if not other_lens:
            continue

        max_other = max(other_lens)
        checked += 1

        # Only fix if correct answer is ≥2× longer AND absolutely long (>30 chars)
        if len(correct_text) < 2 * max_other or len(correct_text) <= 30:
            continue

        # Target: at most 1.4× the longest wrong answer (leave a little room)
        target = max(max_other, 20) * 14 // 10
        new_text = _shorten(correct_text, target)

        if new_text == correct_text or not new_text:
            continue  # no improvement

        opts[c] = new_text
        fixed += 1

    if fixed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return checked, fixed


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    files = sorted(
        glob.glob("data/questions/*.json") +
        glob.glob("data/classifications/*.json")
    )
    if not files:
        print("No JSON files found.")
        return

    total_checked = total_fixed = 0
    for fp in files:
        path = Path(fp)
        checked, fixed = fix_file(path)
        total_checked += checked
        total_fixed += fixed
        if fixed:
            print(f"  {path.name}: fixed {fixed}/{checked} questions")

    print(f"\nTotal: checked {total_checked} single-answer questions, "
          f"fixed {total_fixed} biased options.")
    if total_fixed:
        print("Run: git add data/ && git commit -m 'Fix biased MCQ options'")


if __name__ == "__main__":
    main()
