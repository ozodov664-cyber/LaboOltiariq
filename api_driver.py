"""Mini app — haydovchi tomoni API'lari (onlayn, joylashuv, safar boshqaruvi)."""
import time

from aiohttp import web

import db
import pricing
from webcommon import ok, err, require_user, order_public

routes = web.RouteTableDef()


def _require_driver(request: web.Request):
    user = require_user(request)
    driver = db.get_driver(user["id"])
    if not driver:
        raise web.HTTPForbidden(
            text='{"ok": false, "error": "Siz haydovchi sifatida ro\'yxatdan o\'tmagansiz. Admin bilan bog\'laning."}',
            content_type="application/json",
        )
    if driver["blocked"]:
        raise web.HTTPForbidden(
            text='{"ok": false, "error": "Hisobingiz bloklangan."}', content_type="application/json"
        )
    return driver


def _driver_public(d):
    tariff = db.get_tariff(d["tariff"])
    sub_active = db.driver_subscription_active(d)
    return {
        "id": d["id"],
        "name": d["name"],
        "phone": d["phone"],
        "tariff_id": d["tariff"],
        "tariff_name": tariff["name"] if tariff else d["tariff"],
        "rating": round(d["rating"], 1),
        "rating_count": d["rating_count"],
        "status": d["status"],
        "sub_until": d["sub_until"],
        "sub_active": sub_active,
    }


@routes.get("/api/driver/me")
async def me(request: web.Request):
    driver = _require_driver(request)
    return ok(_driver_public(driver))


@routes.post("/api/driver/online")
async def set_online(request: web.Request):
    driver = _require_driver(request)
    if not db.driver_subscription_active(driver):
        return err("Obuna muddati tugagan. Onlayn bo'lish uchun admin orqali to'lovni tasdiqlatib oling.", status=402)
    body = await request.json()
    online = bool(body.get("online"))
    active = db.get_active_order_for_driver(driver["id"])
    if not online and active:
        return err("Joriy buyurtmani yakunlamasdan oflayn bo'la olmaysiz.", status=409)
    db.set_driver_status(driver["id"], "available" if online else "offline")
    return ok({"status": "available" if online else "offline"})


#: Ikki joylashuv so'rovi orasidagi masofa shu chegaradan kichik bo'lsa — hisobga
#: olinmaydi (GPS "titrashi": mashina to'xtab tursa ham koordinata bir necha metrga
#: siljib turishi mumkin, shu sabab actual_km sekin-asta o'zidan ko'payib ketmasin).
_MIN_GPS_DELTA_KM = 0.02  # 20 metr

#: Ikki so'rov orasida bundan katta "sakrash" bo'lsa — bu haqiqiy harakat emas,
#: balki GPS signali vaqtincha yo'qolib (tonnel, yer osti to'xtash joyi va h.k.),
#: keyin butunlay boshqa nuqtada qayta topilgani, shuning uchun tashlab yuboriladi.
_MAX_GPS_JUMP_KM = 2.0


@routes.post("/api/driver/location")
async def set_location(request: web.Request):
    driver = _require_driver(request)
    body = await request.json()
    try:
        lat, lng = float(body["lat"]), float(body["lng"])
    except (KeyError, ValueError):
        return err("lat va lng kerak.")

    # MUHIM: mijozga buyurtma berishda ko'rsatilgan narx — FINAL narx. Safar davomida
    # haydovchi qancha yursa ham (uzoqroq yo'ldan yursa ham, tirbandlikda tursa ham) narx
    # O'ZGARMAYDI — faqat "kutish" (wait_price) alohida hisoblanadi, u masofaga bog'liq emas.
    # Shu sabab bu yerda GPS nuqtalari orqali actual_km/price hisoblanmaydi — faqat
    # haydovchining joriy joylashuvi (xaritada ko'rsatish/dispetcherlik uchun) saqlanadi.
    db.set_driver_location(driver["id"], lat, lng)
    return ok({"updated": True})


@routes.get("/api/driver/order/active")
async def active_order(request: web.Request):
    driver = _require_driver(request)
    order = db.get_active_order_for_driver(driver["id"])
    return ok(order_public(order) if order else None)


@routes.post("/api/driver/order/{order_id}/start")
async def start_trip(request: web.Request):
    driver = _require_driver(request)
    order_id = int(request.match_info["order_id"])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != driver["id"] or order["status"] != "accepted":
        return err("Bu safarni boshlab bo'lmaydi.", status=409)
    db.start_trip(order_id)
    return ok(order_public(db.get_order(order_id)))


@routes.post("/api/driver/order/{order_id}/wait_on")
async def wait_on(request: web.Request):
    driver = _require_driver(request)
    order_id = int(request.match_info["order_id"])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != driver["id"] or order["status"] != "in_progress":
        return err("Xatolik.", status=409)
    db.start_waiting(order_id)
    return ok(order_public(db.get_order(order_id)))


@routes.post("/api/driver/order/{order_id}/wait_off")
async def wait_off(request: web.Request):
    driver = _require_driver(request)
    order_id = int(request.match_info["order_id"])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != driver["id"] or order["status"] != "waiting":
        return err("Xatolik.", status=409)
    region = db.get_region(order["region_id"])
    tariff = db.get_tariff(order["tariff_id"])
    started = order["wait_started_at"] or int(time.time())
    seconds = max(0, int(time.time()) - started)
    added_price = pricing.wait_charge(seconds, region["wait_per_min"])
    base_price = pricing.fare(region, tariff, order["actual_km"])
    new_total = base_price + order["wait_price"] + added_price
    db.stop_waiting(order_id, seconds, added_price, new_total)
    return ok(order_public(db.get_order(order_id)))


@routes.post("/api/driver/order/{order_id}/finish")
async def finish_trip(request: web.Request):
    driver = _require_driver(request)
    order_id = int(request.match_info["order_id"])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != driver["id"] or order["status"] not in ("in_progress", "waiting"):
        return err("Xatolik.", status=409)
    db.finish_order(order_id)
    db.set_driver_status(driver["id"], "available")
    return ok(order_public(db.get_order(order_id)))


@routes.post("/api/driver/street_pickup")
async def street_pickup(request: web.Request):
    driver = _require_driver(request)
    if not db.driver_subscription_active(driver):
        return err("Obuna muddati tugagan.", status=402)
    active = db.get_active_order_for_driver(driver["id"])
    if active:
        return err("Avval joriy safarni yakunlang.", status=409)
    body = await request.json()
    try:
        region_id = int(body["region_id"])
    except (KeyError, ValueError):
        return err("region_id kerak.")
    region = db.get_region(region_id)
    tariff = db.get_tariff(driver["tariff"])
    if not region or not tariff:
        return err("Hudud topilmadi.", status=404)
    price = pricing.fare(region, tariff, 0)
    order_id = db.create_order(
        client_id=driver["id"], region_id=region_id, tariff_id=driver["tariff"], payment_method="naqd",
        pickup_text="Yo'lda (bordyurdan)", pickup_lat=None, pickup_lng=None,
        dest_text=None, dest_lat=None, dest_lng=None, est_km=0, price=price, order_type="street",
    )
    db.accept_order(order_id, driver["id"])
    db.start_trip(order_id)
    db.set_driver_status(driver["id"], "busy")
    return ok(order_public(db.get_order(order_id)))


@routes.get("/api/driver/stats")
async def stats(request: web.Request):
    driver = _require_driver(request)
    return ok(db.driver_trip_stats(driver["id"]))
