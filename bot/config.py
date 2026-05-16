import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    gemini_api_key: str
    admin_ids: list[int]
    database_path: str
    images_dir: str
    gemini_model: str
    max_exam_questions: int
    throttle_rate: float
    webapp_url: str


def _parse_admin_ids(raw: Optional[str]) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN is not set in environment")
    return Settings(
        bot_token=token,
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
        database_path=os.getenv("DATABASE_PATH", "bot.db"),
        images_dir=os.getenv("IMAGES_DIR", "data/images"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        max_exam_questions=int(os.getenv("MAX_EXAM_QUESTIONS", "30")),
        throttle_rate=float(os.getenv("THROTTLE_RATE", "0.5")),
        webapp_url=os.getenv("WEBAPP_URL", ""),
    )


config = load_settings()
