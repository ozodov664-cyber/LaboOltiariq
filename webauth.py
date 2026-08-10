"""Telegram Mini App (Web App) initData'ni tekshirish.

Mini app browserdan/WebView'dan API'ga so'rov yuborganda, Telegram unga `initData` degan
imzolangan satr beradi (foydalanuvchi id, ism va h.k.). Bu funksiya shu satrni bot tokeni
bilan tasdiqlaydi — soxta so'rovlar (masalan boshqa odamning Telegram ID'sini o'zini
qilib ko'rsatish) imkonsiz bo'ladi.

Rasmiy hujjat: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400):
    """To'g'ri bo'lsa Telegram foydalanuvchi ma'lumotini (dict, 'id' bilan) qaytaradi,
    aks holda None."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        return None
    auth_date = int(pairs.get("auth_date", "0") or "0")
    if max_age_seconds and auth_date and (time.time() - auth_date) > max_age_seconds:
        return None
    user_raw = pairs.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not user or "id" not in user:
        return None
    return user
