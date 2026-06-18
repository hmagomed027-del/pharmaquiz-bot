# ФармаКвиз — контекст проекта

Telegram-бот для подготовки студентов-медиков к экзаменам по фармакологии.
Владелец: Патина. Задеплоен на **Render** (free tier).

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| Бот | Python 3.12, aiogram 3.x, webhook-режим |
| API / Mini App | FastAPI + uvicorn |
| БД | PostgreSQL (asyncpg) на Render |
| ИИ | Gemini API (gemini-2.5-flash-lite), только офлайн |
| Деплой | Render Web Service, авто-деплой из GitHub |

**requirements.txt**: `aiogram>=3.13`, `asyncpg>=0.30`, `google-genai>=1.10`, `python-dotenv>=1.0`, `fastapi>=0.115`, `uvicorn>=0.34`, `python-multipart>=0.0.20`, `aiohttp>=3.11`

---

## Переменные окружения (Render)

```
BOT_TOKEN           — токен Telegram-бота
DATABASE_URL        — PostgreSQL DSN (автоматически от Render Postgres)
GEMINI_API_KEY      — ключ Gemini API (только для офлайн-генерации)
ADMIN_IDS           — telegram_id администратора (через запятую)
RENDER_EXTERNAL_URL — автоматически задаётся Render (используется для вебхука)
GEMINI_MODEL        — gemini-2.5-flash-lite (по умолчанию)
```

---

## Структура файлов

```
run.py                        — точка входа (FastAPI + бот + планировщик)
bot/
  config.py                   — Settings dataclass, загрузка env
  main.py                     — (не используется как точка входа)
  database/
    db.py                     — asyncpg pool, init_db(), get_db(), SCHEMA
    queries.py                — все SQL-запросы (asyncpg, плейсхолдеры $1..$N)
  handlers/
    start.py                  — /start, главное меню
    training.py               — режим тренировки
    exam.py                   — режим экзамена
    stats.py                  — /stats
    admin.py                  — /adminstats, /reload, /broadcast
    reminder.py               — /reminder, callback reminder_set/off, /testreminder
  services/
    scheduler.py              — планировщик напоминаний (asyncio, каждые 60 сек)
    claude_service.py         — get_explanation() — только из БД/JSON, Gemini НЕ вызывается
    question_loader.py        — загрузка JSON → PostgreSQL при старте
    wikipedia_service.py      — картинки препаратов
  utils/
    formatters.py             — format_question, format_explanation, escape_md
  keyboards/
    inline.py, reply.py
  states/states.py
api/
  main.py                     — FastAPI lifespan (init_db, load_all_questions)
  deps.py                     — get_user_id (валидация Telegram initData)
  routes/                     — topics, training, exam, image, classifications
data/
  questions/                  — 1399 MCQ-вопросов (20 файлов JSON)
  classifications/            — 997 MCQ-вопросов по классификации (13 файлов JSON)
pregenerate_explanations.py   — офлайн-скрипт генерации объяснений (Gemini)
fix_biased_options.py         — исправление смещённых ответов (правильный ≥2× длиннее)
```

---

## База данных (PostgreSQL)

Таблицы создаются автоматически при старте (`db.py → _SCHEMA`):

| Таблица | Назначение |
|---------|-----------|
| `questions` | все MCQ-вопросы (id, topic, option_a..d, correct_answer, explanation) |
| `users` | пользователи (telegram_id, reminder_time, registered_at) |
| `training_answers` | история ответов в тренировке |
| `exam_sessions` | сессии экзамена |
| `exam_answers` | ответы в экзамене |
| `explanation_cache` | кеш объяснений (question_id → explanation text) |

**Важно**: при каждом новом деплое с пустой БД пользователи теряют `reminder_time` и должны заново установить напоминание через `/reminder`.

---

## Вопросы и объяснения

### data/questions/ — 1399 вопросов

| Файл | Вопросов | Объяснений |
|------|---------|-----------|
| analgesics.json | 50 | 40 ✅ |
| anesthetics.json | 50 | 0 |
| anti_inflammatory.json | 50 | 0 |
| antiallergic.json | 50 | 0 |
| blood.json | 69 | 0 |
| chemotherapy.json | 99 | 0 |
| chemotherapy_new.json | 50 | 0 |
| cns.json | 100 | 0 |
| cns_new.json | 50 | 0 |
| digestive.json | 100 | 0 |
| digestive2.json | 50 | 0 |
| diuretics.json | 50 | 0 |
| hormones.json | 50 | 0 |
| pns.json | 100 | 0 |
| pns_new.json | 50 | 0 |
| recepty.json | 150 | 0 |
| recepty_new.json | 50 | 0 |
| respiratory.json | 100 | 0 |
| sss.json | 81 | 0 |
| vitamins.json | 50 | 0 |
| **ИТОГО** | **1399** | **40** |

### data/classifications/ — 997 вопросов

| Файл | Вопросов |
|------|---------|
| antiallergic.json | 23 |
| antiinflammatory.json | 93 |
| blood.json | 13 |
| breathing.json | 58 |
| chemo.json | 33 |
| cns.json | 457 |
| digestive.json | 13 |
| diuretics.json | 7 |
| hormones.json | 11 |
| myometrium.json | 5 |
| pns.json | 249 |
| sss.json | 29 |
| vitamins.json | 6 |
| **ИТОГО** | **997** |

**Формат вопроса (JSON)**:
```json
{
  "id": "analg_001",
  "topic": "Анальгетики",
  "subtopic": "Опиоиды",
  "question": "Текст вопроса",
  "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
  "correct_answer": "A",
  "explanation": "Текст объяснения (plain text, без HTML/Markdown)",
  "difficulty": 1,
  "drug_name": "Морфин"
}
```

---

## Объяснения — как работает пайплайн

1. **Офлайн**: запустить `python pregenerate_explanations.py` — генерирует объяснения через Gemini и сохраняет в JSON-файлы.
2. **При старте бота**: `question_loader.py` загружает JSON → PostgreSQL, объяснения из поля `explanation` копируются в таблицу `explanation_cache`.
3. **В runtime**: `claude_service.get_explanation(question)` — читает только из `explanation_cache` или поля `explanation`. **Gemini API в runtime не вызывается.**
4. **Если объяснения нет**: показывается fallback (правильный ответ + перечисление неверных).

### Запуск pregenerate_explanations.py

```bash
python pregenerate_explanations.py
```

- Пропускает вопросы у которых уже есть `explanation`
- Сохраняет после каждого вопроса (безопасно прерывать)
- Лимит free tier Gemini: ~1500 RPD → 1 день на все 1399 вопросов
- **Лучшее время запуска**: 03:00 МСК (сброс суточного лимита в 00:00 UTC)
- После завершения: `git add data/questions/ && git commit`

---

## Напоминания (scheduler)

- `bot/services/scheduler.py` — asyncio-таск, тикает каждые 60 сек
- Хранит `_last_sent_key = "YYYY-MM-DD HH:MM"` (включает дату — иначе будет блокировать повтор на следующий день)
- Запрашивает из `users` всех с `reminder_time = HH:MM` (МСК)
- Логирует каждую минуту: `Scheduler tick MSK=21:00 — matched N user(s)`
- При старте логирует всех пользователей с установленным временем

**Если уведомления не приходят** → в логах Render ищи `No users have reminder_time set`. Если видишь — пользователь должен заново нажать `/reminder` и выбрать время (данные слетают при смене БД).

---

## Режим parse_mode

- **MarkdownV2**: вопросы, меню, статистика, кнопки (все `format_question`, `format_stats`, `format_exam_result`)
- **HTML**: объяснения (`format_explanation`), напоминания, reminder-меню
- **None (plain text)**: сообщения планировщика (`bot.send_message(..., parse_mode=None)`)
- `DefaultBotProperties(parse_mode=None)` — глобальный parse_mode отключён в `run.py`

---

## Деплой

- GitHub repo → Render Web Service, автодеплой при push в `main`
- `render.yaml` не используется — настройки через Render dashboard
- Start command: `python run.py`
- Render бесплатный PostgreSQL подключён через `DATABASE_URL`
- `_keep_alive()` в `run.py` пингует `/health` каждые 10 мин чтобы сервис не засыпал

---

## Важные решения и история

| Что | Решение |
|-----|---------|
| БД | Мигрировали SQLite → PostgreSQL (asyncpg). Коммит `ad794c1`. |
| Объяснения | Убрали Gemini из runtime, только офлайн-генерация. |
| 377 вопросов | Исправлены смещённые ответы (`fix_biased_options.py`). Правильный ответ был в ≥2× длиннее неправильных — давал подсказку. |
| parse_mode | Был глобальный MarkdownV2 → сломал объяснения. Исправлено на None + явный HTML там где нужно. |
| Reminder bug | `_last_sent_key` хранил только `HH:MM` → после первой отправки блокировал навсегда. Исправлено на `YYYY-MM-DD HH:MM`. |
| format_explanation | Показывал букву ответа (`A`) вместо текста. Исправлено — теперь `A) Текст варианта`. |

---

## Текущие задачи / незавершённое

- [ ] Сгенерировать объяснения для оставшихся 1359 вопросов (запустить после 03:00 МСК)
- [ ] Пользователь должен заново установить напоминание через `/reminder`
- [ ] Добавить вопросы в классификации по оставшимся темам (expand_cls.py)
