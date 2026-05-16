import hashlib
import hmac
import json
import os
import urllib.parse


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """Returns user dict if valid, None if invalid."""
    if not init_data:
        return None

    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    user_str = params.get("user")
    if user_str:
        try:
            return json.loads(user_str)
        except (json.JSONDecodeError, ValueError):
            return None
    return {"id": 0}


def is_debug_mode() -> bool:
    return os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
