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


def _resolve_webapp_url() -> str:
    explicit = os.getenv("WEBAPP_URL", "").strip()
    if explicit:
        return explicit
    # Render автоматически задаёт RENDER_EXTERNAL_URL
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if render_url:
        return render_url
    # Railway автоматически задаёт RAILWAY_PUBLIC_DOMAIN
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway_domain:
        return f"https://{railway_domain}"
    return ""


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
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        max_exam_questions=int(os.getenv("MAX_EXAM_QUESTIONS", "30")),
        throttle_rate=float(os.getenv("THROTTLE_RATE", "0.5")),
        webapp_url=_resolve_webapp_url(),
    )


config = load_settings()
