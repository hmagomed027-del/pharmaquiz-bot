#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json, time, re, os, hashlib
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
CLS_DIR = Path("data/classifications")

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent?key={API_KEY}"
)

# ── helpers ────────────────────────────────────────────────────────────────
def gemini(prompt: str, retries=6) -> str:
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}}
    for attempt in range(retries):
        try:
            r = requests.post(GEMINI_URL, json=body, timeout=120)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            is_429 = "429" in str(e) or (hasattr(e, 'response') and getattr(e.response, 'status_code', 0) == 429)
            wait = (90 * (attempt + 1)) if is_429 else (10 * (attempt + 1))
            print(f"  [retry {attempt+1}/{retries}] {e} -> wait {wait}s")
            time.sleep(wait)
    return ""

def extract_json(text: str):
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    m = re.search(r"(\[.*\])", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    return []

def balance_ok(opts: dict) -> bool:
    lengths = [len(v) for v in opts.values()]
    if not lengths: return False
    return max(lengths) / max(min(lengths), 1) < 2.2

def validate_mcq(item: dict) -> bool:
    try:
        assert item.get("question")
        opts = item.get("options", {})
        assert set(opts.keys()) == {"A","B","C","D"}
        assert item.get("correct_answer") in {"A","B","C","D"}
        assert item.get("explanation")
        assert balance_ok(opts)
        return True
    except AssertionError:
        return False

def validate_sort(item: dict) -> bool:
    try:
        assert item.get("instruction")
        assert len(item.get("categories", [])) >= 2
        assert len(item.get("items", [])) >= 4
        for it in item["items"]:
            assert it["category"] in item["categories"]
        return True
    except AssertionError:
        return False

def load_file(fname: str) -> list:
    p = CLS_DIR / fname
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

def save_file(fname: str, data: list):
    (CLS_DIR / fname).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def existing_ids(data: list) -> set:
    return {x["id"] for x in data if x.get("id")}

def make_id(prefix: str, kind: str, idx: int, ex: set) -> str:
    base = f"{prefix}_{kind}_{idx:03d}"
    if base not in ex: return base
    for i in range(idx+1, idx+500):
        c = f"{prefix}_{kind}_{i:03d}"
        if c not in ex: return c
    return f"{prefix}_{kind}_{hashlib.md5(str(idx).encode()).hexdigest()[:6]}"

def count_topic(data, topic):
    mcq = sum(1 for x in data if x.get("topic")==topic and x.get("type")!="sorting")
    srt = sum(1 for x in data if x.get("topic")==topic and x.get("type")=="sorting")
    return mcq, srt

# ── topics ─────────────────────────────────────────────────────────────────
TOPICS = [
    ("ПНС","Холиномиметики","pns.json","chm"),
    ("ПНС","Холиноблокаторы","pns.json","chb"),
    ("ПНС","Адреномиметики","pns.json","adm"),
    ("ПНС","Адреноблокаторы","pns.json","adb"),
    ("ПНС","Местные анестетики","pns.json","mes"),
    ("ЦНС","Анальгетики","cns.json","anl"),
    ("ЦНС","Средства для наркоза","cns.json","nar"),
    ("ЦНС","Спирт этиловый","cns.json","eth"),
    ("ЦНС","Снотворные средства","cns.json","snv"),
    ("ЦНС","Транквилизаторы","cns.json","trn"),
    ("ЦНС","Антидепрессанты","cns.json","adr"),
    ("ЦНС","Антипсихотики","cns.json","apt"),
    ("ЦНС","Противоэпилептические","cns.json","epl"),
    ("ЦНС","Противопаркинсонические","cns.json","prk"),
    ("ЦНС","Средства для лечения маний","cns.json","man"),
    ("ЦНС","Седативные средства","cns.json","sed"),
    ("ЦНС","Ноотропы","cns.json","noo"),
    ("ЦНС","Средства, вызывающие лекарственную зависимость","cns.json","dep"),
    ("Противовоспалительные","НПВС","antiinflammatory.json","nps"),
    ("Противовоспалительные","Глюкокортикостероиды","antiinflammatory.json","gks"),
    ("Противоаллергические","Антигистаминные H1","antiallergic.json","agh"),
    ("Противоаллергические","Стабилизаторы тучных клеток","antiallergic.json","stb"),
    ("Дыхательная система","β2-адреномиметики","breathing.json","b2a"),
    ("Дыхательная система","М-холиноблокаторы бронхов","breathing.json","mhb"),
    ("Дыхательная система","Метилксантины","breathing.json","mtx"),
    ("Дыхательная система","Муколитики и отхаркивающие","breathing.json","muk"),
    ("Дыхательная система","Противокашлевые","breathing.json","pks"),
    ("Пищеварительная система","Ингибиторы протонной помпы","digestive.json","ipp"),
    ("Пищеварительная система","Н2-блокаторы гистамина","digestive.json","h2b"),
    ("Пищеварительная система","Антациды","digestive.json","ant"),
    ("Пищеварительная система","Прокинетики","digestive.json","prk2"),
    ("Пищеварительная система","Слабительные","digestive.json","slb"),
    ("ССС","Антиаритмики","sss.json","aar"),
    ("ССС","Антагонисты кальция","sss.json","ank"),
    ("ССС","Ингибиторы АПФ","sss.json","iap"),
    ("ССС","Блокаторы рецепторов ангиотензина II","sss.json","bra"),
    ("ССС","Нитраты","sss.json","nit"),
    ("ССС","Сердечные гликозиды","sss.json","gly"),
    ("Диуретики","Диуретики","diuretics.json","diu"),
    ("Миометрий","Утеротонические средства","myometrium.json","ute"),
    ("Миометрий","Токолитики","myometrium.json","tok"),
    ("Кровь","Антикоагулянты","blood.json","aco"),
    ("Кровь","Антиагреганты","blood.json","aag"),
    ("Кровь","Тромболитики","blood.json","trb"),
    ("Гормоны","Гормоны — инсулины","hormones.json","ins"),
    ("Гормоны","Гормоны — тиреоидные","hormones.json","thr"),
    ("Гормоны","Глюкокортикостероиды","hormones.json","gkh"),
    ("Гормоны","Половые гормоны","hormones.json","poh"),
    ("Витамины","Жирорастворимые витамины","vitamins.json","vif"),
    ("Витамины","Водорастворимые витамины","vitamins.json","viw"),
    ("Витамины","Витамины","vitamins.json","vit"),
    ("Химиопрепараты","Антибиотики — классификация","chemo.json","abc"),
    ("Химиопрепараты","Антибиотики — механизм действия","chemo.json","abm"),
    ("Химиопрепараты","Пенициллины","chemo.json","pen"),
    ("Химиопрепараты","Цефалоспорины","chemo.json","cef"),
    ("Химиопрепараты","Макролиды","chemo.json","mac"),
    ("Химиопрепараты","Аминогликозиды","chemo.json","amg"),
    ("Химиопрепараты","Тетрациклины","chemo.json","tet"),
    ("Химиопрепараты","Фторхинолоны","chemo.json","fkh"),
]

MCQ_PROMPT = """\
Ты преподаватель фармакологии. Сгенерируй ровно {n} вопросов MCQ для студентов-медиков по теме «{topic}» (раздел «{section}»).

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА (нарушение = вопрос выброшен):
1. Все 4 варианта A, B, C, D — длиной от 80 до 140 символов каждый
2. Неправильные варианты содержат реальные механизмы/препараты той же группы, звучат так же убедительно, как правильный
3. Никаких коротких ответов вроде «Нет эффекта» или «Только в/в» — только развёрнутые клинико-фармакологические формулировки
4. Не повторяй: {existing}

Верни ТОЛЬКО JSON-массив, без markdown и пояснений:
[
  {{
    "question": "...",
    "options": {{"A": "80-140 символов", "B": "80-140 символов", "C": "80-140 символов", "D": "80-140 символов"}},
    "correct_answer": "A",
    "category": "Категория",
    "explanation": "2-3 предложения с обоснованием."
  }}
]"""

SORT_PROMPT = """\
Ты преподаватель фармакологии. Сгенерируй {n} упражнений на сортировку по теме «{topic}» (раздел «{section}»).
Каждое: 2-5 категорий, 6-12 препаратов/понятий.
Не повторяй: {existing}

Верни ТОЛЬКО JSON-массив:
[
  {{
    "instruction": "Определите ... препарата",
    "category": "Название упражнения",
    "categories": ["Группа 1", "Группа 2"],
    "items": [{{"name": "Препарат", "category": "Группа 1"}}]
  }}
]"""

def gen_mcq(section, topic, prefix, n, all_data):
    ex = [x["question"][:55] for x in all_data
          if x.get("topic")==topic and x.get("type")!="sorting"][:12]
    prompt = MCQ_PROMPT.format(
        n=n, topic=topic, section=section,
        existing="; ".join(ex) if ex else "нет"
    )
    raw = gemini(prompt)
    items = extract_json(raw)
    ids = existing_ids(all_data)
    result = []
    idx = len([x for x in all_data if x.get("topic")==topic]) + 1
    for item in items:
        if not validate_mcq(item):
            print(f"    skip invalid mcq: {str(item.get('question',''))[:40]}")
            continue
        uid = make_id(prefix, "mcq", idx, ids)
        ids.add(uid)
        idx += 1
        result.append({
            "id": uid, "section": section, "topic": topic, "type": "mcq",
            "category": item.get("category","Общее"),
            "question": item["question"],
            "options": item["options"],
            "correct_answer": item["correct_answer"],
            "explanation": item["explanation"],
        })
    return result

def gen_sort(section, topic, prefix, n, all_data):
    ex = [x.get("category","")[:45] for x in all_data
          if x.get("topic")==topic and x.get("type")=="sorting"][:8]
    prompt = SORT_PROMPT.format(
        n=n, topic=topic, section=section,
        existing="; ".join(ex) if ex else "нет"
    )
    raw = gemini(prompt)
    items = extract_json(raw)
    ids = existing_ids(all_data)
    result = []
    idx = len([x for x in all_data if x.get("topic")==topic and x.get("type")=="sorting"]) + 1
    for item in items:
        if not validate_sort(item):
            print(f"    skip invalid sort: {str(item.get('instruction',''))[:40]}")
            continue
        uid = make_id(prefix, "sort", idx, ids)
        ids.add(uid)
        idx += 1
        result.append({
            "id": uid, "section": section, "topic": topic, "type": "sorting",
            "category": item.get("category","Сортировка"),
            "instruction": item["instruction"],
            "categories": item["categories"],
            "items": item["items"],
        })
    return result

def main():
    TARGET   = 50
    MCQ_PART = 0.84   # ~84% MCQ

    print(f"Target: {TARGET} per topic | {len(TOPICS)} topics\n")
    files_changed = set()

    for (section, topic, fname, prefix) in TOPICS:
        data = load_file(fname)
        mcq_now, srt_now = count_topic(data, topic)
        total_now = mcq_now + srt_now
        need = TARGET - total_now
        if need <= 0:
            print(f"✓ {topic}: {total_now} (skip)")
            continue

        need_mcq  = max(0, round(need * MCQ_PART))
        need_sort = need - need_mcq
        print(f"\n-> {topic} | have={total_now} need_mcq={need_mcq} need_sort={need_sort}")

        new_items = []

        # MCQ in batches of 12
        rem = need_mcq
        while rem > 0:
            batch = min(12, rem)
            got = gen_mcq(section, topic, prefix, batch, data + new_items)
            print(f"   mcq batch {batch} -> got {len(got)}")
            new_items.extend(got)
            rem -= batch
            time.sleep(8)

        # Sorting in batches of 3
        rem = need_sort
        while rem > 0:
            batch = min(3, rem)
            got = gen_sort(section, topic, prefix, batch, data + new_items)
            print(f"   sort batch {batch} -> got {len(got)}")
            new_items.extend(got)
            rem -= batch
            time.sleep(8)

        if new_items:
            data.extend(new_items)
            save_file(fname, data)
            files_changed.add(fname)
            added_m = sum(1 for x in new_items if x.get("type")!="sorting")
            added_s = len(new_items) - added_m
            print(f"   saved {len(new_items)} new (mcq={added_m} sort={added_s})")
        else:
            print(f"   nothing generated")

        time.sleep(15)

    print(f"\n=== Done. Files: {sorted(files_changed)} ===\n")
    print("Final counts:")
    for (section, topic, fname, prefix) in TOPICS:
        data = load_file(fname)
        m, s = count_topic(data, topic)
        t = m + s
        mark = "✓" if t >= TARGET else f"✗ need {TARGET-t} more"
        print(f"  {mark} {topic}: {t} (mcq={m} sort={s})")

if __name__ == "__main__":
    main()
