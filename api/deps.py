from fastapi import Header, HTTPException

from api.auth import validate_init_data, is_debug_mode
from bot.config import config
from bot.database.db import get_db
from bot.database import queries


async def get_user_id(x_init_data: str = Header(default="", alias="x-init-data")) -> int:
    if not x_init_data:
        if is_debug_mode():
            uid = config.admin_ids[0] if config.admin_ids else 999999
            db = await get_db()
            await queries.upsert_user(db, uid, "debug", "Debug", "User")
            return uid
        raise HTTPException(status_code=401, detail="Missing X-Init-Data header")

    user = validate_init_data(x_init_data, config.bot_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid initData")

    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No user ID in initData")

    db = await get_db()
    await queries.upsert_user(
        db,
        telegram_id=user_id,
        username=user.get("username") or "",
        first_name=user.get("first_name") or "",
        last_name=user.get("last_name") or "",
    )
    return user_id
