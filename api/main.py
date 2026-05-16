import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bot.config import config
from bot.database.db import close_db, get_db, init_db
from bot.services.question_loader import load_all_questions
from bot.services.wikipedia_service import close_session

from api.routes import exam, image, topics, training

logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).parent.parent / "webapp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_dir)
    os.makedirs(config.images_dir, exist_ok=True)
    await init_db(config.database_path)
    db = await get_db()
    count = await load_all_questions(db)
    logger.info("Questions loaded: %d new", count)
    yield
    await close_session()
    await close_db()


app = FastAPI(title="ФармаКвиз API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(topics.router, prefix="/api")
app.include_router(training.router, prefix="/api")
app.include_router(exam.router, prefix="/api")
app.include_router(image.router, prefix="/api")

if WEBAPP_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(WEBAPP_DIR / "index.html"))


@app.get("/{path:path}", include_in_schema=False)
async def spa_fallback(path: str):
    return FileResponse(str(WEBAPP_DIR / "index.html"))
