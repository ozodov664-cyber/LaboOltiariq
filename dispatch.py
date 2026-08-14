"""Buyurtmani haydovchilarga yuborish (zayavka) — masofa asosida bosqichma-bosqich va
turli "ovoz" (audio signal) bilan. Bu fayl handlers_client.py va handlers_dispatcher.py
ikkalasi tomonidan ishlatiladi (shuning uchun alohida modulga chiqarildi).
"""
import asyncio
import os

from aiogram.types import FSInputFile

import db
import pricing
import keyboards as kb

# Eng yaqin haydovchini tanlash uchun bosqichlar: avval faqat eng yaqinlariga, javob bo'lmasa kengroq doiraga
NEAREST_STAGE_WAIT_SECONDS = 20

# Mijozdan (buyurtma nuqtasidan) shu radiusdan uzoqdagi haydovchilarga umuman zayavka yuborilmaydi
MAX_RADIUS_KM = 40.0
# Shu radius ichidagilarga eng "shoshilinch" ovoz bilan yuboriladi
NEAR_RADIUS_KM = 10.0
# Bundan uzoqroq, lekin o'rtacha radius ichidagilarga — xotirjamroq ovoz
MEDIUM_RADIUS_KM = 15.0

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SOUND_NEAR = os.path.join(ASSETS_DIR, "chime_near.ogg")      # <= 10 km — yoqimli, ammo tezroq "ding-ding"
SOUND_MEDIUM = os.path.join(ASSETS_DIR, "chime_medium.ogg")  # 10-15 km — bitta xotirjam "ding"
SOUND_FAR = os.path.join(ASSETS_DIR, "chime_far.ogg")        # 15-40 km — eng past, uzun, yumshoq ohang


def money(n):
    return f"{round(n):,}".replace(",", " ")


def _order_broadcast_text(order, region, tariff, distance_km=None):
    if distance_km is None:
        header = "🆕 <b>Yangi buyurtma</b>"
    elif distance_km <= NEAR_RADIUS_KM:
        header = "🔴 <b>Yaqin buyurtma!</b>"
    elif distance_km <= MEDIUM_RADIUS_KM:
        header = "🟠 <b>Yangi buyurtma</b>"
    else:
        header = "🔵 <b>Uzoqroq buyurtma</b>"
    dist_line = f"📏 Sizgacha: ~{distance_km:.1f} km\n" if distance_km is not None else ""
    return (
        f"{header} #{order['id']}\n"
        f"🗺 {region['name']} · {tariff['name']}\n"
        f"📍 {order['pickup_text']}\n"
        f"{dist_line}"
        f"📏 Safar: ~{order['est_km']} km · 💰 ~{money(order['price'])} so'm\n"
        f"💳 {'Naqd' if order['payment_method'] == 'naqd' else 'Karta'}"
    )


async def _send_alert_sound(bot, driver_id, distance_km):
    """Masofaga qarab boshqacha, yoqimli ovozli signal (voice) yuboradi:
    10 km gacha — tezroq ikkita ding, 10-15 km — bitta xotirjam ding, 15-40 km — eng past va yumshoq ohang."""
    if distance_km is None:
        return
    if distance_km <= NEAR_RADIUS_KM:
        path = SOUND_NEAR
    elif distance_km <= MEDIUM_RADIUS_KM:
        path = SOUND_MEDIUM
    elif distance_km <= MAX_RADIUS_KM:
        path = SOUND_FAR
    else:
        return
    if not os.path.exists(path):
        return
    try:
        await bot.send_voice(driver_id, FSInputFile(path))
    except Exception:
        pass  # ovoz yuborilmasa ham, asosiy matn xabar baribir boradi


async def _notify_batch(bot, drivers, order_id, region, tariff, order, distances):
    for d in drivers:
        distance_km = distances.get(d["id"])
        text = _order_broadcast_text(order, region, tariff, distance_km)
        try:
            msg = await bot.send_message(d["id"], text, reply_markup=kb.accept_order_kb(order_id), parse_mode="HTML")
        except Exception:
            continue  # haydovchi botni bloklagan bo'lishi mumkin — e'tiborsiz qoldiramiz
        # Xabar ID va matnini saqlab qo'yamiz — kimdir buyurtmani qabul qilganda, qolgan
        # haydovchilarning shu xabarlarini "band bo'ldi" deb avtomatik tahrirlash uchun kerak.
        try:
            db.save_order_broadcast(order_id, d["id"], msg.message_id, text)
        except Exception:
            pass
        await _send_alert_sound(bot, d["id"], distance_km)


async def dispatch_order(bot, order_id):
    """Buyurtmani mos, onlayn va obunasi faol haydovchilarga yuboradi.

    - Agar mijoz (pickup) joylashuvi va haydovchilarning joriy joylashuvi ma'lum bo'lsa:
      40 km radiusdagi haydovchilarga yuboriladi (agar hech kim topilmasa — buyurtma
      "osilib" qolmasligi uchun barcha mos haydovchilarga yuboriladi, radiusdan qat'iy nazar).
      Har birining xabarida mijozgacha necha km ekani ko'rsatiladi va masofaga qarab
      boshqacha (lekin har doim yoqimli) ovozli signal boradi:
      10 km gacha — tezroq ikkita ding, 10-15 km — bitta xotirjam ding,
      15-40 km — eng past, uzun va yumshoq ohang.
    - Joylashuv ma'lum bo'lmasa (masalan telefon orqali qo'lda kiritilgan buyurtma) — hammasiga
      birdaniga, ovozsiz yuboriladi, chunki masofani hisoblab bo'lmaydi.
    """
    order = db.get_order(order_id)
    if not order or order["status"] != "new":
        return
    tariff = db.get_tariff(order["tariff_id"])
    region = db.get_region(order["region_id"])

    drivers = db.list_available_drivers(order["tariff_id"])
    if not drivers:
        return

    has_pickup_gps = order["pickup_lat"] is not None
    distances = {}
    if has_pickup_gps:
        for d in drivers:
            if d.get("lat") is not None and d.get("lng") is not None:
                distances[d["id"]] = pricing.haversine_km(order["pickup_lat"], order["pickup_lng"], d["lat"], d["lng"])

    if not distances:
        # Hech kimning joylashuvi yo'q (yoki buyurtmada GPS yo'q) — eski usulda hammaga birdaniga, ovozsiz
        await _notify_batch(bot, drivers, order_id, region, tariff, order, {})
        return

    in_radius = [d for d in drivers if distances.get(d["id"], float("inf")) <= MAX_RADIUS_KM]
    if not in_radius:
        # 40 km ichida hech kim yo'q — buyurtma osilib qolmasin, hammaga yuboramiz (ovozsiz, chunki uzoq)
        await _notify_batch(bot, drivers, order_id, region, tariff, order, {})
        return

    in_radius.sort(key=lambda d: distances[d["id"]])
    next_ids = {d["id"] for d in in_radius[1:3]}
    rest_ids = {d["id"] for d in in_radius[3:]}

    # 1-bosqich: faqat eng yaqin haydovchi
    await _notify_batch(bot, in_radius[:1], order_id, region, tariff, order, distances)
    await asyncio.sleep(NEAREST_STAGE_WAIT_SECONDS)
    order = db.get_order(order_id)
    if not order or order["status"] != "new":
        return

    # 2-bosqich: keyingi 2 ta yaqin haydovchi — holatini qayta tekshirib (hali ham bo'sh/onlaynligini)
    fresh = db.list_available_drivers(order["tariff_id"])
    await _notify_batch(bot, [d for d in fresh if d["id"] in next_ids], order_id, region, tariff, order, distances)
    await asyncio.sleep(NEAREST_STAGE_WAIT_SECONDS)
    order = db.get_order(order_id)
    if not order or order["status"] != "new":
        return

    # 3-bosqich: qolgan barcha 40 km ichidagi, hali ham bo'sh haydovchilar
    if rest_ids:
        fresh = db.list_available_drivers(order["tariff_id"])
        await _notify_batch(bot, [d for d in fresh if d["id"] in rest_ids], order_id, region, tariff, order, distances)


async def mark_order_taken_for_others(bot, order_id, accepted_driver_id):
    """Buyurtmani bitta haydovchi qabul qilgach, shu buyurtma yuborilgan BOSHQA barcha
    haydovchilarning xabarlarini avtomatik "🚕 Band bo'ldi" deb tahrirlaydi va tugmani
    olib tashlaydi — ular endi eskirgan zayavkaga bossa ham ma'nosiz urinish qilmaydi."""
    broadcasts = db.get_order_broadcasts(order_id)
    for b in broadcasts:
        if b["driver_id"] == accepted_driver_id:
            continue
        try:
            await bot.edit_message_text(
                chat_id=b["driver_id"],
                message_id=b["message_id"],
                text=b["text"] + "\n\n🚕 <b>Band bo'ldi</b> — boshqa haydovchi qabul qildi.",
                parse_mode="HTML",
            )
        except Exception:
            continue  # xabar allaqachon o'zgargan/o'chirilgan yoki haydovchi botni bloklagan bo'lishi mumkin
    db.clear_order_broadcasts(order_id)


EXPIRE_SWEEP_INTERVAL_SECONDS = 60  # har 1 daqiqada eskirgan buyurtmalarni tekshirib turadi


async def expire_orders_loop(bot):
    """Fon rejimida doimiy ishlaydigan vazifa: uzoq vaqt (db.ORDER_TTL_SECONDS) hech qanday
    haydovchi qabul qilmagan buyurtmalarni avtomatik 'muddati tugagan' deb belgilaydi va
    mijozga (agar botda bo'lsa — telefon orqali kiritilgan buyurtmalarda mijoz botda emas,
    shu sababli ularga xabar yuborilmaydi) darhol xabar beradi, qayta urinib ko'rishni taklif
    qiladi. Shu tufayli buyurtma abadiy "osilib" qolmaydi va haydovchilar eski, allaqachon
    keraksiz zayavkani ko'rib chalg'imaydi."""
    while True:
        await asyncio.sleep(EXPIRE_SWEEP_INTERVAL_SECONDS)
        try:
            expired = db.expire_stale_orders()
        except Exception:
            continue
        for o in expired:
            if o.get("phone_client_name"):
                continue  # dispetcher qo'lda kiritgan buyurtma — mijoz bot ichida emas
            try:
                await bot.send_message(
                    o["client_id"],
                    "⏰ <b>Buyurtmangiz muddati tugadi</b>\n"
                    "Afsuski, uzoq vaqt hech qanday haydovchi javob bermadi. Iltimos, qayta "
                    "urinib ko'ring — hozir ko'proq haydovchi onlayn bo'lishi mumkin.",
                    parse_mode="HTML",
                )
            except Exception:
                pass


async def notify_dispatchers_new_order(bot, order_id):
    """Yangi buyurtma haqida barcha ro'yxatdan o'tgan dispetcherlarga darhol xabar beradi —
    ular tasdiqlagandan keyingina zayavka haydovchilarga ketadi."""
    order = db.get_order(order_id)
    if not order:
        return
    region = db.get_region(order["region_id"])
    tariff = db.get_tariff(order["tariff_id"])
    client_line = ""
    if order.get("phone_client_name"):
        client_line = f"👤 {order['phone_client_name']} · 📞 {order.get('phone_client_phone') or '-'}\n"
    else:
        client = db.get_user(order["client_id"])
        if client:
            client_line = f"👤 {client['name']} · 📞 {client['phone']}\n"
    text = (
        f"🆕 <b>Tasdiqlash kutilmoqda — buyurtma #{order['id']}</b>\n"
        f"{client_line}"
        f"🗺 {region['name']} · {tariff['name']}\n"
        f"📍 {order['pickup_text']}\n"
        f"📏 ~{order['est_km']} km · 💰 ~{money(order['price'])} so'm"
    )
    dispatchers = db.list_admin_ids("dispatcher")
    available = db.list_available_drivers(order["tariff_id"])
    for disp in dispatchers:
        try:
            await bot.send_message(
                disp["user_id"], text, reply_markup=kb.dispatcher_new_order_kb(order["id"], available),
                parse_mode="HTML",
            )
        except Exception:
            pass
