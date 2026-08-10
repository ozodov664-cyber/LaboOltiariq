"""Mini app — dispetcher tomoni API'lari (buyurtmalarni tayinlash, haydovchilar holati)."""
from aiohttp import web

import db
import pricing
from webcommon import ok, err, require_user, require_dispatcher, order_public

routes = web.RouteTableDef()


@routes.post("/api/dispatcher/login")
async def login(request: web.Request):
    user = require_user(request)
    body = await request.json()
    password = body.get("password", "")
    if password != db.get_setting("dispatcher_password"):
        return err("Parol noto'g'ri.", status=403)
    db.add_admin_id(user["id"], "dispatcher")
    db.upsert_user(user["id"], role="dispatcher")
    return ok({"logged_in": True})


@routes.get("/api/dispatcher/orders")
async def active_orders(request: web.Request):
    require_dispatcher(request)
    orders = db.list_active_orders()
    result = []
    for o in orders:
        client = db.get_user(o["client_id"])
        item = order_public(o)
        item["client_name"] = (o.get("phone_client_name") or (client["name"] if client else None))
        item["client_phone"] = (o.get("phone_client_phone") or (client["phone"] if client else None))
        result.append(item)
    return ok(result)


@routes.get("/api/dispatcher/drivers")
async def drivers_status(request: web.Request):
    require_dispatcher(request)
    drivers = db.list_drivers()
    result = []
    for d in drivers:
        tariff = db.get_tariff(d["tariff"])
        result.append({
            "id": d["id"], "name": d["name"], "phone": d["phone"],
            "tariff_name": tariff["name"] if tariff else d["tariff"],
            "status": d["status"], "blocked": bool(d["blocked"]),
            "rating": round(d["rating"], 1),
            "sub_active": db.driver_subscription_active(d),
        })
    return ok(result)


@routes.get("/api/dispatcher/available_drivers/{tariff_id}")
async def available_drivers(request: web.Request):
    require_dispatcher(request)
    drivers = db.list_available_drivers(request.match_info["tariff_id"])
    return ok([{"id": d["id"], "name": d["name"], "rating": round(d["rating"], 1)} for d in drivers])


@routes.post("/api/dispatcher/order")
async def create_order(request: web.Request):
    """Dispetcher telefon orqali kelgan buyurtmani qo'lda kiritadi."""
    user = require_user(request)
    require_dispatcher(request)
    body = await request.json()
    try:
        region_id = int(body["region_id"])
        tariff_id = body["tariff_id"]
        km = float(body.get("est_km", 4.0))
        client_name = (body.get("client_name") or "").strip()
        client_phone = (body.get("client_phone") or "").strip()
    except (KeyError, ValueError, TypeError):
        return err("region_id, tariff_id, est_km, client_name, client_phone kerak.")
    if not client_name or not client_phone:
        return err("Mijoz ismi va telefon raqami kerak.")
    region = db.get_region(region_id)
    tariff = db.get_tariff(tariff_id)
    if not region or not tariff:
        return err("Hudud yoki mashina turi topilmadi.", status=404)
    client_id = db.upsert_phone_client(client_name, client_phone)
    price = pricing.fare(region, tariff, km)
    order_id = db.create_order(
        client_id=client_id, region_id=region_id, tariff_id=tariff_id, payment_method=body.get("payment_method", "naqd"),
        pickup_text=body.get("pickup_text"), pickup_lat=None, pickup_lng=None,
        dest_text=body.get("dest_text"), dest_lat=None, dest_lng=None,
        est_km=km, price=price, order_type="phone",
        phone_client_name=client_name, phone_client_phone=client_phone, created_by=user["id"],
    )
    return ok(order_public(db.get_order(order_id)))


@routes.post("/api/dispatcher/order/{order_id}/assign")
async def assign_driver(request: web.Request):
    require_dispatcher(request)
    order_id = int(request.match_info["order_id"])
    body = await request.json()
    try:
        driver_id = int(body["driver_id"])
    except (KeyError, ValueError):
        return err("driver_id kerak.")
    order = db.get_order(order_id)
    if not order or order["status"] != "new":
        return err("Bu buyurtmani tayinlab bo'lmaydi (allaqachon olingan yoki yakunlangan).", status=409)
    success = db.accept_order(order_id, driver_id)
    if not success:
        return err("Boshqa haydovchi allaqachon oldi.", status=409)
    bot = request.app["bot"]
    driver = db.get_driver(driver_id)
    region = db.get_region(order["region_id"])
    try:
        await bot.send_message(
            driver_id,
            f"✅ Sizga buyurtma #{order_id} tayinlandi (dispetcher tomonidan)\n"
            f"🗺 {region['name']}\n📍 {order['pickup_text'] or '-'}",
        )
    except Exception:
        pass
    return ok(order_public(db.get_order(order_id)))


@routes.post("/api/dispatcher/order/{order_id}/cancel")
async def cancel_order(request: web.Request):
    require_dispatcher(request)
    order_id = int(request.match_info["order_id"])
    order = db.get_order(order_id)
    if not order or order["status"] in ("finished", "cancelled"):
        return err("Bu buyurtmani bekor qilib bo'lmaydi.", status=409)
    db.cancel_order(order_id)
    if order["driver_id"]:
        db.set_driver_status(order["driver_id"], "available")
    return ok({"cancelled": True})
