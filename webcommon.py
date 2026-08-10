"""Mini app API route'lari uchun umumiy yordamchilar."""
import os

from aiohttp import web

import db
import webauth

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


def money(n):
    return f"{round(n):,}".replace(",", " ")


def ok(data=None, **extra):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return web.json_response(payload)


def err(message, status=400):
    return web.json_response({"ok": False, "error": message}, status=status)


def telegram_user(request: web.Request):
    """So'rovdagi (header) Telegram initData'ni tekshiradi, foydalanuvchi dict'ini qaytaradi.
    Noto'g'ri/yo'q bo'lsa None."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return webauth.verify_init_data(init_data, BOT_TOKEN)


def require_user(request: web.Request):
    """Telegram foydalanuvchisini talab qiladi. Bo'lmasa HTTPUnauthorized ko'taradi."""
    user = telegram_user(request)
    if not user:
        raise web.HTTPUnauthorized(
            text='{"ok": false, "error": "Telegram orqali tasdiqlanmadi. Mini appni Telegram ichida oching."}',
            content_type="application/json",
        )
    return user


def require_admin(request: web.Request):
    """Admin parolini header orqali tekshiradi (X-Admin-Password)."""
    password = request.headers.get("X-Admin-Password", "")
    if not password or password != db.get_setting("admin_password"):
        raise web.HTTPForbidden(
            text='{"ok": false, "error": "Admin paroli noto\'g\'ri."}',
            content_type="application/json",
        )


def require_dispatcher(request: web.Request):
    """Dispetcher parolini header orqali tekshiradi (X-Dispatcher-Password)."""
    password = request.headers.get("X-Dispatcher-Password", "")
    if not password or password != db.get_setting("dispatcher_password"):
        raise web.HTTPForbidden(
            text='{"ok": false, "error": "Dispetcher paroli noto\'g\'ri."}',
            content_type="application/json",
        )


def order_public(order: dict) -> dict:
    """Buyurtma dict'ini frontendga yuborishga qulay shaklga keltiradi."""
    if not order:
        return None
    region = db.get_region(order["region_id"])
    tariff = db.get_tariff(order["tariff_id"])
    driver = db.get_driver(order["driver_id"]) if order.get("driver_id") else None
    return {
        "id": order["id"],
        "status": order["status"],
        "region": region["name"] if region else None,
        "region_id": order["region_id"],
        "tariff": tariff["name"] if tariff else order["tariff_id"],
        "tariff_id": order["tariff_id"],
        "payment_method": order["payment_method"],
        "pickup_text": order["pickup_text"],
        "pickup_lat": order["pickup_lat"],
        "pickup_lng": order["pickup_lng"],
        "dest_text": order["dest_text"],
        "dest_lat": order["dest_lat"],
        "dest_lng": order["dest_lng"],
        "est_km": order["est_km"],
        "actual_km": order["actual_km"],
        "wait_price": order["wait_price"],
        "price": order["price"],
        "rating": order["rating"],
        "created_at": order["created_at"],
        "driver": (
            {
                "id": driver["id"],
                "name": driver["name"],
                "phone": driver["phone"],
                "rating": round(driver["rating"], 1),
                "lat": driver["lat"],
                "lng": driver["lng"],
                "loc_updated_at": driver["loc_updated_at"],
            }
            if driver
            else None
        ),
    }
