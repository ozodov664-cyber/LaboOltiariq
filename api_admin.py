"""Mini app — admin tomoni API'lari (hududlar, mashina narxlari, haydovchilar, obuna, statistika)."""
from aiohttp import web

import db
from webcommon import ok, err, require_user, require_admin

routes = web.RouteTableDef()


@routes.post("/api/admin/login")
async def login(request: web.Request):
    user = require_user(request)
    body = await request.json()
    password = body.get("password", "")
    if password != db.get_setting("admin_password"):
        return err("Parol noto'g'ri.", status=403)
    db.add_admin_id(user["id"], "admin")
    return ok({"logged_in": True})


@routes.get("/api/admin/stats")
async def stats(request: web.Request):
    require_admin(request)
    s = db.revenue_stats()
    drivers = db.list_drivers()
    online = sum(1 for d in drivers if d["status"] == "available")
    return ok({
        "trips": s["trips"], "revenue": s["revenue"],
        "drivers_total": len(drivers), "drivers_online": online,
    })


# ---------------- hududlar ----------------
@routes.get("/api/admin/regions")
async def list_regions(request: web.Request):
    require_admin(request)
    return ok(db.list_regions())


@routes.post("/api/admin/regions")
async def add_region(request: web.Request):
    require_admin(request)
    body = await request.json()
    try:
        name = body["name"].strip()
        minimalka = int(body["minimalka"])
        km_price = int(body.get("km_price", 0))
        wait_per_min = int(body["wait_per_min"])
    except (KeyError, ValueError, AttributeError):
        return err("name, minimalka, wait_per_min kerak.")
    if not name:
        return err("Hudud nomi bo'sh bo'lmasin.")
    db.add_region(name, minimalka, km_price, wait_per_min)
    return ok({"added": True})


@routes.delete("/api/admin/regions/{region_id}")
async def delete_region(request: web.Request):
    require_admin(request)
    db.delete_region(int(request.match_info["region_id"]))
    return ok({"deleted": True})


# ---------------- mashina narxlari ----------------
@routes.get("/api/admin/tariffs")
async def list_tariffs(request: web.Request):
    require_admin(request)
    return ok(db.list_tariffs())


@routes.put("/api/admin/tariffs/{tariff_id}")
async def update_tariff(request: web.Request):
    require_admin(request)
    body = await request.json()
    try:
        km_price = int(body["km_price"])
    except (KeyError, ValueError):
        return err("km_price kerak.")
    tariff_id = request.match_info["tariff_id"]
    if not db.get_tariff(tariff_id):
        return err("Topilmadi.", status=404)
    db.set_tariff_price(tariff_id, km_price)
    return ok(db.get_tariff(tariff_id))


# ---------------- haydovchilar ----------------
@routes.get("/api/admin/drivers")
async def list_drivers(request: web.Request):
    require_admin(request)
    drivers = db.list_drivers()
    result = []
    for d in drivers:
        tariff = db.get_tariff(d["tariff"])
        result.append({
            "id": d["id"], "name": d["name"], "phone": d["phone"],
            "tariff_id": d["tariff"], "tariff_name": tariff["name"] if tariff else d["tariff"],
            "rating": round(d["rating"], 1), "rating_count": d["rating_count"],
            "blocked": bool(d["blocked"]), "status": d["status"],
            "sub_until": d["sub_until"], "sub_active": db.driver_subscription_active(d),
            "password": d["pass"],
        })
    return ok(result)


@routes.post("/api/admin/drivers")
async def add_driver(request: web.Request):
    require_admin(request)
    body = await request.json()
    try:
        telegram_id = int(body["telegram_id"])
        tariff_id = body["tariff_id"]
        name = body["name"].strip()
        phone = body.get("phone", "").strip()
    except (KeyError, ValueError, AttributeError):
        return err("telegram_id, tariff_id, name kerak.")
    if not db.get_tariff(tariff_id):
        return err("Mashina turi topilmadi.", status=404)
    password = db.gen_driver_password()
    db.create_driver(telegram_id, tariff_id, password, name=name, phone=phone)
    return ok({"id": telegram_id, "password": password})


@routes.post("/api/admin/drivers/{driver_id}/toggle_block")
async def toggle_block(request: web.Request):
    require_admin(request)
    driver_id = int(request.match_info["driver_id"])
    d = db.get_driver(driver_id)
    if not d:
        return err("Topilmadi.", status=404)
    db.set_driver_blocked(driver_id, not d["blocked"])
    return ok({"blocked": not d["blocked"]})


@routes.post("/api/admin/drivers/{driver_id}/reset_password")
async def reset_password(request: web.Request):
    require_admin(request)
    driver_id = int(request.match_info["driver_id"])
    if not db.get_driver(driver_id):
        return err("Topilmadi.", status=404)
    new_pass = db.gen_driver_password()
    db.set_driver_password(driver_id, new_pass)
    return ok({"password": new_pass})


@routes.post("/api/admin/drivers/{driver_id}/extend_subscription")
async def extend_subscription(request: web.Request):
    require_admin(request)
    driver_id = int(request.match_info["driver_id"])
    body = await request.json()
    try:
        days = int(body["days"])
    except (KeyError, ValueError):
        return err("days kerak.")
    if not db.get_driver(driver_id):
        return err("Topilmadi.", status=404)
    new_until = db.extend_driver_subscription(driver_id, days)
    return ok({"sub_until": new_until})


@routes.get("/api/admin/drivers_locations")
async def drivers_locations(request: web.Request):
    require_admin(request)
    drivers = db.list_drivers_with_location()
    result = []
    for d in drivers:
        tariff = db.get_tariff(d["tariff"])
        result.append({
            "id": d["id"], "name": d["name"], "lat": d["lat"], "lng": d["lng"],
            "status": d["status"], "tariff_name": tariff["name"] if tariff else d["tariff"],
            "loc_updated_at": d["loc_updated_at"],
        })
    return ok(result)


# ---------------- obuna narxlari ----------------
@routes.get("/api/admin/subscription_prices")
async def sub_prices(request: web.Request):
    require_admin(request)
    return ok({
        "week": int(db.get_setting("sub_price_week") or "0"),
        "month": int(db.get_setting("sub_price_month") or "0"),
    })


@routes.put("/api/admin/subscription_prices")
async def set_sub_prices(request: web.Request):
    require_admin(request)
    body = await request.json()
    try:
        week = int(body["week"])
        month = int(body["month"])
    except (KeyError, ValueError):
        return err("week va month kerak.")
    db.set_setting("sub_price_week", str(week))
    db.set_setting("sub_price_month", str(month))
    return ok({"week": week, "month": month})


# ---------------- parollar ----------------
@routes.put("/api/admin/passwords")
async def set_passwords(request: web.Request):
    require_admin(request)
    body = await request.json()
    if body.get("admin_password"):
        db.set_setting("admin_password", body["admin_password"].strip())
    if body.get("dispatcher_password"):
        db.set_setting("dispatcher_password", body["dispatcher_password"].strip())
    return ok({"updated": True})


# ---------------- xabar yuborish ----------------
@routes.post("/api/admin/broadcast")
async def broadcast(request: web.Request):
    require_admin(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return err("Xabar matni bo'sh bo'lmasin.")
    bot = request.app["bot"]
    drivers = db.list_drivers()
    sent = 0
    for d in drivers:
        try:
            await bot.send_message(d["id"], f"📢 {text}")
            sent += 1
        except Exception:
            continue
    return ok({"sent": sent, "total": len(drivers)})
