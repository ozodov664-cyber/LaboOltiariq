"""Mini app — mijoz tomoni API'lari (buyurtma berish, kuzatish, tarix)."""
import asyncio

from aiohttp import web

import db
import pricing
import dispatch
from webcommon import ok, err, require_user, order_public

routes = web.RouteTableDef()


@routes.get("/api/client/meta")
async def meta(request: web.Request):
    require_user(request)
    regions = db.list_regions()
    tariffs = db.list_tariffs()
    return ok({
        "regions": [{"id": r["id"], "name": r["name"]} for r in regions],
        "tariffs": [
            {"id": t["id"], "name": t["name"], "car": t["car"], "body": t["body"], "km_price": t["km_price"]}
            for t in tariffs
        ],
    })


@routes.post("/api/client/register")
async def register(request: web.Request):
    user = require_user(request)
    body = await request.json()
    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not name or not phone:
        return err("Ism va telefon kerak.")
    db.upsert_user(user["id"], name=name, phone=phone, role="client")
    return ok({"id": user["id"], "name": name, "phone": phone})


@routes.get("/api/client/me")
async def me(request: web.Request):
    user = require_user(request)
    u = db.get_user(user["id"])
    return ok(u)


@routes.get("/api/client/price")
async def price(request: web.Request):
    require_user(request)
    try:
        region_id = int(request.query["region_id"])
        tariff_id = request.query["tariff_id"]
        km = float(request.query.get("km", "4"))
    except (KeyError, ValueError):
        return err("region_id, tariff_id va km kerak.")
    region = db.get_region(region_id)
    tariff = db.get_tariff(tariff_id)
    if not region or not tariff:
        return err("Hudud yoki mashina turi topilmadi.", status=404)
    return ok({"price": pricing.fare(region, tariff, km)})


@routes.post("/api/client/route_km")
async def route_km(request: web.Request):
    """Ikkala GPS nuqta berilganda haqiqiy yo'l masofasini (OSRM) hisoblaydi."""
    require_user(request)
    body = await request.json()
    try:
        km = await pricing.route_km(
            float(body["pickup_lat"]), float(body["pickup_lng"]),
            float(body["dest_lat"]), float(body["dest_lng"]),
        )
    except (KeyError, ValueError, TypeError):
        return err("pickup_lat/pickup_lng/dest_lat/dest_lng kerak.")
    return ok({"km": km})


@routes.post("/api/client/order")
async def create_order(request: web.Request):
    user = require_user(request)
    body = await request.json()
    try:
        region_id = int(body["region_id"])
        tariff_id = body["tariff_id"]
        payment_method = body.get("payment_method", "naqd")
        km = float(body.get("est_km", 4.0))
    except (KeyError, ValueError, TypeError):
        return err("region_id, tariff_id va est_km kerak.")
    region = db.get_region(region_id)
    tariff = db.get_tariff(tariff_id)
    if not region or not tariff:
        return err("Hudud yoki mashina turi topilmadi.", status=404)
    existing = db.get_active_order_for_client(user["id"])
    if existing:
        return err("Sizda allaqachon faol buyurtma bor.", status=409)
    price = pricing.fare(region, tariff, km)
    order_id = db.create_order(
        client_id=user["id"],
        region_id=region_id,
        tariff_id=tariff_id,
        payment_method=payment_method,
        pickup_text=body.get("pickup_text"),
        pickup_lat=body.get("pickup_lat"),
        pickup_lng=body.get("pickup_lng"),
        dest_text=body.get("dest_text"),
        dest_lat=body.get("dest_lat"),
        dest_lng=body.get("dest_lng"),
        est_km=km,
        price=price,
        order_type="app",
    )
    bot = request.app["bot"]
    dispatchers = db.list_admin_ids("dispatcher")
    if dispatchers:
        asyncio.create_task(dispatch.notify_dispatchers_new_order(bot, order_id))
    else:
        asyncio.create_task(dispatch.dispatch_order(bot, order_id))
    return ok(order_public(db.get_order(order_id)))


@routes.get("/api/client/order/active")
async def active_order(request: web.Request):
    user = require_user(request)
    order = db.get_active_order_for_client(user["id"])
    return ok(order_public(order) if order else None)


@routes.get("/api/client/order/{order_id}")
async def order_detail(request: web.Request):
    user = require_user(request)
    order = db.get_order(int(request.match_info["order_id"]))
    if not order or order["client_id"] != user["id"]:
        return err("Topilmadi.", status=404)
    return ok(order_public(order))


@routes.post("/api/client/order/{order_id}/cancel")
async def cancel_order(request: web.Request):
    user = require_user(request)
    order_id = int(request.match_info["order_id"])
    success = db.cancel_order_by_client(order_id, user["id"])
    if not success:
        return err("Bu buyurtmani hozir bekor qilib bo'lmaydi (allaqachon yo'lga chiqilgan yoki yakunlangan).", status=409)
    return ok({"cancelled": True})


@routes.post("/api/client/order/{order_id}/rate")
async def rate_order(request: web.Request):
    user = require_user(request)
    order_id = int(request.match_info["order_id"])
    body = await request.json()
    try:
        stars = int(body["stars"])
    except (KeyError, ValueError):
        return err("stars (1-5) kerak.")
    if not (1 <= stars <= 5):
        return err("stars 1 dan 5 gacha bo'lishi kerak.")
    order = db.get_order(order_id)
    if not order or order["client_id"] != user["id"] or order["status"] != "finished":
        return err("Bu buyurtmani baholab bo'lmaydi.", status=409)
    db.rate_order(order_id, stars)
    if order["driver_id"]:
        db.add_driver_rating(order["driver_id"], stars)
    return ok({"rated": True})


@routes.get("/api/client/orders")
async def orders_history(request: web.Request):
    user = require_user(request)
    orders = db.get_orders_for_client(user["id"], limit=20)
    return ok([order_public(o) for o in orders])
