from fastapi import APIRouter
from bot.services.wikipedia_service import _find_image_url

router = APIRouter()


@router.get("/image")
async def get_image(drug: str):
    try:
        url = await _find_image_url(drug)
        return {"url": url}
    except Exception:
        return {"url": None}
