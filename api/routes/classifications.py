import json
import random
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# ── Load all classification JSON files at import time ──────────────────────
_CLASSIFICATIONS: list[dict] = []
_TOPICS_META: dict[str, dict] = {}
_TOPIC_SECTIONS: dict[str, set] = {}   # topic → set of sections
_SECTIONS_META: dict[str, dict] = {}

_SECTION_ICONS: dict[str, str] = {
    "ПНС":                    "⚡",
    "ЦНС":                    "🧠",
    "Противовоспалительные":  "🔥",
    "Противоаллергические":   "🛡️",
    "Дыхательная система":    "🫁",
    "Пищеварительная система":"🫃",
    "ССС":                    "❤️",
    "Диуретики":              "💧",
    "Миометрий":              "🤰",
    "Кровь":                  "🩸",
    "Гормоны":                "🧬",
    "Витамины":               "🍊",
    "Химиопрепараты":         "🧫",
}

_SECTION_COLORS: dict[str, str] = {
    "ПНС":                    "#2E86AB",
    "ЦНС":                    "#9B59B6",
    "Противовоспалительные":  "#E74C3C",
    "Противоаллергические":   "#F39C12",
    "Дыхательная система":    "#27AE60",
    "Пищеварительная система":"#E67E22",
    "ССС":                    "#C0392B",
    "Диуретики":              "#5DADE2",
    "Миометрий":              "#E91E8C",
    "Кровь":                  "#922B21",
    "Гормоны":                "#52BE80",
    "Витамины":               "#F1C40F",
    "Химиопрепараты":         "#1ABC9C",
}

_TOPIC_ICONS: dict[str, str] = {
    # ПНС
    "Адреноблокаторы":                              "🚫",
    "Адреномиметики":                               "💉",
    "Холиноблокаторы":                              "🧪",
    "Холиномиметики":                               "🔬",
    "Местные анестетики":                           "🪥",
    # ЦНС
    "Анальгетики":                                  "💊",
    "Средства для наркоза":                         "😷",
    "Спирт этиловый":                               "🍶",
    "Снотворные средства":                          "😴",
    "Противоэпилептические":                        "⚡",
    "Противопаркинсонические":                      "🤲",
    "Антипсихотики":                                "🧠",
    "Транквилизаторы":                              "🌿",
    "Антидепрессанты":                              "💙",
    "Средства для лечения маний":                   "⚖️",
    "Седативные средства":                          "🍃",
    "Ноотропы":                                     "💡",
    "Средства, вызывающие лекарственную зависимость": "⚠️",
    # Противовоспалительные
    "НПВС":                                         "🔥",
    "Глюкокортикостероиды":                         "⚕️",
    # Противоаллергические
    "Антигистаминные H1":                           "🛡️",
    "Стабилизаторы тучных клеток":                  "🔵",
    # Дыхательная система
    # (uses generic icon fallback)
    # ССС
    "Антиаритмики":                                 "❤️",
    "Антагонисты кальция":                          "🫀",
    "Ингибиторы АПФ":                               "💧",
    "Блокаторы рецепторов ангиотензина II":         "🩺",
    "Сердечные гликозиды":                          "🌿",
    "Нитраты":                                      "💨",
    # Диуретики
    "Диуретики":                                    "💧",
    # Миометрий
    "Утеротонические средства":                     "🤰",
    "Токолитики":                                   "🛑",
    # Кровь
    "Антикоагулянты":                               "🩸",
    # Гормоны
    "Гормоны — инсулины":                           "🧬",
    "Гормоны — тиреоидные":                         "🦋",
    "Половые гормоны":                              "⚧️",
    # Витамины
    "Жирорастворимые витамины":                     "☀️",
    "Водорастворимые витамины":                     "💧",
    "Витамины":                                     "🍊",
    # Химиопрепараты
    "Цефалоспорины":                                "💉",
    "Пенициллины":                                  "🧫",
    "Фторхинолоны":                                 "⚗️",
    "Макролиды":                                    "🔵",
    "Аминогликозиды":                               "🟡",
    "Тетрациклины":                                 "🟠",
    "Антибиотики — классификация":                  "📋",
}

_TOPIC_COLORS: dict[str, str] = {
    # ПНС
    "Адреноблокаторы":                              "#5B6EAE",
    "Адреномиметики":                               "#2E86AB",
    "Холиноблокаторы":                              "#6B4226",
    "Холиномиметики":                               "#8B5E3C",
    "Местные анестетики":                           "#1F618D",
    # ЦНС
    "Анальгетики":                                  "#922B21",
    "Средства для наркоза":                         "#7D3C98",
    "Спирт этиловый":                               "#784212",
    "Снотворные средства":                          "#6C3483",
    "Противоэпилептические":                        "#2ECC71",
    "Противопаркинсонические":                      "#A9CCE3",
    "Антипсихотики":                                "#9B59B6",
    "Транквилизаторы":                              "#8E44AD",
    "Антидепрессанты":                              "#7D6608",
    "Средства для лечения маний":                   "#1A5276",
    "Седативные средства":                          "#117A65",
    "Ноотропы":                                     "#1E8449",
    "Средства, вызывающие лекарственную зависимость": "#7B241C",
    # Противовоспалительные
    "НПВС":                                         "#E67E22",
    "Глюкокортикостероиды":                         "#EB984E",
    # Противоаллергические
    "Антигистаминные H1":                           "#F39C12",
    "Стабилизаторы тучных клеток":                  "#2980B9",
    # ССС
    "Антиаритмики":                                 "#E74C3C",
    "Антагонисты кальция":                          "#C0392B",
    "Ингибиторы АПФ":                               "#3498DB",
    "Блокаторы рецепторов ангиотензина II":         "#2471A3",
    "Сердечные гликозиды":                          "#1E8449",
    "Нитраты":                                      "#F39C12",
    # Диуретики
    "Диуретики":                                    "#5DADE2",
    # Миометрий
    "Утеротонические средства":                     "#E91E8C",
    "Токолитики":                                   "#C2185B",
    # Кровь
    "Антикоагулянты":                               "#C0392B",
    # Гормоны
    "Гормоны — инсулины":                           "#52BE80",
    "Гормоны — тиреоидные":                         "#A8D8A8",
    "Половые гормоны":                              "#F06292",
    # Витамины
    "Жирорастворимые витамины":                     "#F9A825",
    "Водорастворимые витамины":                     "#42A5F5",
    "Витамины":                                     "#F1C40F",
    # Химиопрепараты
    "Цефалоспорины":                                "#1ABC9C",
    "Пенициллины":                                  "#27AE60",
    "Фторхинолоны":                                 "#16A085",
    "Макролиды":                                    "#2980B9",
    "Аминогликозиды":                               "#8E44AD",
    "Тетрациклины":                                 "#D35400",
    "Антибиотики — классификация":                  "#2C3E50",
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

    for item in _CLASSIFICATIONS:
        topic = item.get("topic", "")
        section = item.get("section", "")
        kind = item.get("type", "mcq")

        if topic not in _TOPICS_META:
            _TOPICS_META[topic] = {"mcq": 0, "sorting": 0}
        if kind == "sorting":
            _TOPICS_META[topic]["sorting"] += 1
        else:
            _TOPICS_META[topic]["mcq"] += 1

        if topic and section:
            _TOPIC_SECTIONS.setdefault(topic, set()).add(section)

        if section:
            if section not in _SECTIONS_META:
                _SECTIONS_META[section] = {"mcq": 0, "sorting": 0, "topics": set()}
            if kind == "sorting":
                _SECTIONS_META[section]["sorting"] += 1
            else:
                _SECTIONS_META[section]["mcq"] += 1
            _SECTIONS_META[section]["topics"].add(topic)


_load()

_SECTION_ORDER = [
    "ПНС",
    "ЦНС",
    "Противовоспалительные",
    "Противоаллергические",
    "Дыхательная система",
    "Пищеварительная система",
    "ССС",
    "Диуретики",
    "Миометрий",
    "Кровь",
    "Гормоны",
    "Витамины",
    "Химиопрепараты",
]

_TOPIC_ORDER: dict[str, list[str]] = {
    "ПНС": ["Местные анестетики", "Холиномиметики", "Холиноблокаторы", "Адреномиметики", "Адреноблокаторы"],
    "ЦНС": [
        "Анальгетики", "Средства для наркоза", "Спирт этиловый", "Снотворные средства",
        "Противоэпилептические", "Противопаркинсонические", "Антипсихотики", "Транквилизаторы",
        "Антидепрессанты", "Средства для лечения маний", "Седативные средства", "Ноотропы",
        "Средства, вызывающие лекарственную зависимость",
    ],
    "Химиопрепараты": [
        "Антибиотики — классификация", "Пенициллины", "Цефалоспорины",
        "Макролиды", "Аминогликозиды", "Тетрациклины", "Фторхинолоны",
    ],
    "Гормоны": ["Гормоны — инсулины", "Гормоны — тиреоидные", "Глюкокортикостероиды", "Половые гормоны"],
    "Витамины": ["Жирорастворимые витамины", "Водорастворимые витамины", "Витамины"],
}


@router.get("/cls/sections")
async def cls_sections():
    result = []
    for section, counts in _SECTIONS_META.items():
        result.append({
            "section": section,
            "mcq_count": counts["mcq"],
            "sort_count": counts["sorting"],
            "topic_count": len(counts["topics"]),
            "icon": _SECTION_ICONS.get(section, "📋"),
            "color": _SECTION_COLORS.get(section, "#95A5A6"),
        })
    result.sort(key=lambda x: _SECTION_ORDER.index(x["section"]) if x["section"] in _SECTION_ORDER else len(_SECTION_ORDER))
    return result


@router.get("/cls/topics")
async def cls_topics(section: str = Query("")):
    result = []
    for topic, counts in _TOPICS_META.items():
        if section and section not in _TOPIC_SECTIONS.get(topic, set()):
            continue
        result.append({
            "topic": topic,
            "mcq_count": counts["mcq"],
            "sort_count": counts["sorting"],
            "icon": _TOPIC_ICONS.get(topic, "📋"),
            "color": _TOPIC_COLORS.get(topic, "#95A5A6"),
        })
    order = _TOPIC_ORDER.get(section, [])
    result.sort(key=lambda x: order.index(x["topic"]) if x["topic"] in order else len(order))
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
        return JSONResponse(content=None)  # all seen — frontend shows "done"

    item = random.choice(pool)

    # For sorting exercises, shuffle the items list
    if item.get("type") == "sorting":
        result = dict(item)
        result["items"] = random.sample(item["items"], len(item["items"]))
        return result

    return item
