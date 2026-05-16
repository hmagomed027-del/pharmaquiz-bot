import os
import time
import logging
import aiohttp
from bot.config import config

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 7
_session: aiohttp.ClientSession | None = None

WIKI_APIS = [
    "https://ru.wikipedia.org/w/api.php",
    "https://en.wikipedia.org/w/api.php",
]


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            headers={"User-Agent": "PharmacologyBot/1.0 (educational project)"},
            timeout=aiohttp.ClientTimeout(total=10),
        )
    return _session


def _cache_path(drug_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in drug_name)
    safe = safe.strip().replace(" ", "_").lower()
    os.makedirs(config.images_dir, exist_ok=True)
    return os.path.join(config.images_dir, f"{safe}.jpg")


def _is_cache_valid(path: str) -> bool:
    if not os.path.exists(path):
        return False
    age = (time.time() - os.path.getmtime(path)) / 86400
    return age < CACHE_TTL_DAYS


async def get_drug_image(drug_name: str | None) -> bytes | None:
    if not drug_name:
        return None

    path = _cache_path(drug_name)
    if _is_cache_valid(path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError:
            pass

    image_url = await _find_image_url(drug_name)
    if not image_url:
        return None

    try:
        session = _get_session()
        async with session.get(image_url) as resp:
            if resp.status == 200:
                data = await resp.read()
                with open(path, "wb") as f:
                    f.write(data)
                return data
    except Exception as e:
        logger.warning("Failed to download image for %s: %s", drug_name, e)
    return None


async def _find_image_url(drug_name: str) -> str | None:
    session = _get_session()
    params = {
        "action": "query",
        "titles": drug_name,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": 400,
        "redirects": 1,
    }
    for api_url in WIKI_APIS:
        try:
            async with session.get(api_url, params=params) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    url = page.get("thumbnail", {}).get("source")
                    if url:
                        return url
        except Exception as e:
            logger.debug("Wikipedia API error (%s) for %s: %s", api_url, drug_name, e)
    return None


async def close_session() -> None:
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
