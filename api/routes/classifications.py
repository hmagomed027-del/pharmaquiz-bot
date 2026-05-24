import glob
import json
import random
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# ── Load all classification JSON files at import time ──────────────────────
_CLASSIFICATIONS: list[dict] = []
_TOPICS_META: dict[str, dict] = {}

_TOPIC_ICONS: dict[str, str] = {
    "β-адреноблокаторы":      "💊",
    "α-адреноблокаторы":      "⚡",
    "Адреномиметики":          "💉",
    "Холиноблокаторы":         "🧪",
    "Холиномиметики":          "🔬",
    "Цефалоспорины":           "💉",
    "Пенициллины":             "🧫",
    "Фторхинолоны":            "⚗️",
    "Макролиды":               "🔵",
    "Аминогликозиды":          "🟡",
    "Тетрациклины":            "🟠",
    "Антибиотики — классификация": "📋",
    "Антиаритмики":            "❤️",
    "Антагонисты кальция":     "🫀",
    "Ингибиторы АПФ":          "💧",
    "Блокаторы рецепторов ангиотензина II": "🩺",
    "Сердечные гликозиды":     "🌿",
    "Нитраты":                 "💨",
    "Антипсихотики":           "🧠",
    "Антидепрессанты":         "💙",
    "Анксиолитики и снотворные": "😴",
    "Противоэпилептические":   "⚡",
    "Противопаркинсонические": "🤲",
    "Анальгетики — опиоиды":   "💊",
    "Местные анестетики":      "🪥",
    "НПВС":                    "🔥",
    "Диуретики":               "💧",
    "Гормоны — инсулины":      "🧬",
    "Гормоны — тиреоидные":    "🦋",
    "Антикоагулянты":          "🩸",
    "Витамины":                "🍊",
    "Глюкокортикостероиды":    "⚕️",
}

_TOPIC_COLORS: dict[str, str] = {
    "β-адреноблокаторы":      "#4A90D9",
    "α-адреноблокаторы":      "#5B6EAE",
    "Адреномиметики":          "#2E86AB",
    "Холиноблокаторы":         "#6B4226",
    "Холиномиметики":          "#8B5E3C",
    "Цефалоспорины":           "#1ABC9C",
    "Пенициллины":             "#27AE60",
    "Фторхинолоны":            "#16A085",
    "Макролиды":               "#2980B9",
    "Аминогликозиды":          "#8E44AD",
    "Тетрациклины":            "#D35400",
    "Антибиотики — классификация": "#2C3E50",
    "Антиаритмики":            "#E74C3C",
    "Антагонисты кальция":     "#C0392B",
    "Ингибиторы АПФ":          "#3498DB",
    "Блокаторы рецепторов ангиотензина II": "#2471A3",
    "Сердечные гликозиды":     "#1E8449",
    "Нитраты":                 "#F39C12",
    "Антипсихотики":           "#9B59B6",
    "Антидепрессанты":         "#8E44AD",
    "Анксиолитики и снотворные": "#6C3483",
    "Противоэпилептические":   "#2ECC71",
    "Противопаркинсонические": "#A9CCE3",
    "Анальгетики — опиоиды":   "#922B21",
    "Местные анестетики":      "#1F618D",
    "НПВС":                    "#E67E22",
    "Диуретики":               "#5DADE2",
    "Гормоны — инсулины":      "#52BE80",
    "Гормоны — тиреоидные":    "#A8D8A8",
    "Антикоагулянты":          "#C0392B",
    "Витамины":                "#F1C40F",
    "Глюкокортикостероиды":    "#EB984E",
}


def _load():
    cls_dir = Path(__file__).parent.parent.parent / "data" / "classifications"
    seen_ids: set[str] = set()
    for path in sorted(cls_dir.glob("*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
            for item in items:
                if item.get("id") in seen_ids:
                    continue
                seen_ids.add(item["id"])
                _CLASSIFICATIONS.append(item)
        except Exception:
            pass

    # Build topics index
    for item in _CLASSIFICATIONS:
        topic = item.get("topic", "")
        if topic not in _TOPICS_META:
            _TOPICS_META[topic] = {"mcq": 0, "sorting": 0}
        t = item.get("type", "mcq")
        if t == "sorting":
            _TOPICS_META[topic]["sorting"] += 1
        else:
            _TOPICS_META[topic]["mcq"] += 1


_load()


@router.get("/cls/topics")
async def cls_topics():
    result = []
    for topic, counts in _TOPICS_META.items():
        result.append({
            "topic": topic,
            "mcq_count": counts["mcq"],
            "sort_count": counts["sorting"],
            "icon": _TOPIC_ICONS.get(topic, "📋"),
            "color": _TOPIC_COLORS.get(topic, "#95A5A6"),
        })
    return result


@router.get("/cls/question")
async def cls_question(
    topic: str = Query(...),
    type: str = Query("mcq"),
    exclude: str = Query(""),
):
    exclude_ids = {x for x in exclude.split(",") if x}
    pool = [
        q for q in _CLASSIFICATIONS
        if q.get("topic") == topic
        and q.get("type") == type
        and q.get("id") not in exclude_ids
    ]
    if not pool:
        # If all seen, reset
        pool = [q for q in _CLASSIFICATIONS if q.get("topic") == topic and q.get("type") == type]
    if not pool:
        return JSONResponse(content=None)

    item = random.choice(pool)

    # For sorting exercises, shuffle the items list
    if item.get("type") == "sorting":
        result = dict(item)
        result["items"] = random.sample(item["items"], len(item["items"]))
        return result

    return item
