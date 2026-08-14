import time
import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandObject

import db
import pricing
import dispatch
import keyboards as kb
from states import DriverLogin, DriverStreetPickup

router = Router(name="driver")


def money(n):
    return f"{round(n):,}".replace(",", " ")


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def sub_warning_text(driver):
    if driver.get("sub_until") and driver["sub_until"] > int(time.time()):
        return None
    when = f"\nOldingi obuna tugagan sana: {db.fmt_dt(driver['sub_until'])}" if driver.get("sub_until") else "\nHali birorta to'lov qilinmagan."
    return (
        "❌ Obuna muddati tugagan yoki hali to'lanmagan.\n"
        "Onlayn bo'lish va buyurtma olish uchun admin orqali to'lovni tasdiqlatib oling."
        + when
    )


@router.message(Command("driver"))
async def driver_login_cmd(message: Message, state: FSMContext, command: CommandObject):
    driver = db.get_driver(message.from_user.id)
    if driver and not driver["blocked"]:
        await state_login_ok(message, driver)
        return
    if not driver:
        await message.answer(
            "🚫 Siz haydovchi sifatida ro'yxatdan o'tmagansiz.\nAdmin sizni qo'shishi va parol berishi kerak."
        )
        return
    if driver["blocked"]:
        await message.answer("🔒 Hisobingiz bloklangan. Admin bilan bog'laning.")
        return
    if command.args:
        await try_password(message, state, command.args.strip())
    else:
        await state.set_state(DriverLogin.waiting_password)
        await message.answer(
            "🚗 <b>Haydovchi kirish</b>\n━━━━━━━━━━━━━━━━━━\n🔑 Shaxsiy parolingizni kiriting:",
            parse_mode="HTML",
        )


@router.message(DriverLogin.waiting_password)
async def driver_password_input(message: Message, state: FSMContext):
    await try_password(message, state, message.text.strip())


async def try_password(message: Message, state: FSMContext, password: str):
    driver = db.get_driver(message.from_user.id)
    if not driver or driver["blocked"] or driver["pass"] != password:
        await message.answer("❌ Parol noto'g'ri yoki hisobingiz bloklangan.")
        return
    await state.clear()
    await state_login_ok(message, driver)


async def state_login_ok(message: Message, driver):
    tariff = db.get_tariff(driver["tariff"])
    tariff_label = tariff["name"] if tariff else driver["tariff"]
    online = driver["status"] == "available"
    status_line = "🟢 Onlayn" if online else "⚪️ Oflayn"
    await message.answer(
        f"🚗 <b>Xush kelibsiz, {esc(driver['name'])}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚘 Mashina: <b>{esc(tariff_label)}</b>\n"
        f"⭐ Reyting: <b>{driver['rating']:.1f}</b>\n"
        f"{status_line}",
        reply_markup=kb.driver_menu_kb(online=online),
        parse_mode="HTML",
    )


@router.message(F.text.in_(["🟢 Onlayn bo'lish", "🔴 Oflayn bo'lish"]))
async def toggle_online(message: Message):
    driver = db.get_driver(message.from_user.id)
    if not driver:
        return
    active = db.get_active_order_for_driver(message.from_user.id)
    if active and driver["status"] == "busy":
        await message.answer("Joriy buyurtmani yakunlamasdan oflayn bo'la olmaysiz.")
        return
    going_online = driver["status"] != "available"
    if going_online:
        warn = sub_warning_text(driver)
        if warn:
            await message.answer(warn)
            return
    new_status = "available" if going_online else "offline"
    db.set_driver_status(message.from_user.id, new_status)
    await message.answer(
        "Siz endi onlaynsiz ✅" if new_status == "available" else "Siz oflaynsiz.",
        reply_markup=kb.driver_menu_kb(online=new_status == "available"),
    )


# ---------------- location tracking (so admin/dispetcher haydovchi qayerdaligini ko'radi) ----------------
@router.message(F.location)
async def driver_location(message: Message):
    driver = db.get_driver(message.from_user.id)
    if not driver:
        return
    db.set_driver_location(message.from_user.id, message.location.latitude, message.location.longitude)
    await message.answer("📍 Lokatsiyangiz yangilandi.")


@router.edited_message(F.location)
async def driver_location_live(message: Message):
    """Telegram 'Live Location' (jonli joylashuv) yuborilganda avtomatik yangilanadi — tugma bosish shart emas."""
    driver = db.get_driver(message.from_user.id)
    if not driver:
        return
    db.set_driver_location(message.from_user.id, message.location.latitude, message.location.longitude)


# ---------------- subscription (obuna) ----------------
@router.message(F.text == "💳 Obunam")
async def sub_status(message: Message):
    driver = db.get_driver(message.from_user.id)
    if not driver:
        return
    now = int(time.time())
    week_price = db.get_setting("sub_price_week") or "0"
    month_price = db.get_setting("sub_price_month") or "0"
    if driver["sub_until"] and driver["sub_until"] > now:
        left_days = (driver["sub_until"] - now) // 86400
        await message.answer(
            f"💳 Obunangiz faol ✅\nTugash sanasi: {db.fmt_dt(driver['sub_until'])}\nQoldi: {left_days} kun"
        )
    else:
        await message.answer(
            "❌ Obunangiz faol emas. Onlayn bo'lish uchun to'lov qiling va adminga xabar bering.\n\n"
            f"Narxlar (taxminiy): 1 hafta — {money(int(week_price))} so'm, 1 oy — {money(int(month_price))} so'm"
        )


# ---------------- joriy safarni tiklash (agar mijoz/haydovchi ilova keshini tozalasa ham buyurtma yo'qolmaydi) ----------------
@router.message(F.text == "🚗 Joriy safar")
async def current_trip(message: Message):
    order = db.get_active_order_for_driver(message.from_user.id)
    if not order:
        await message.answer("Sizda hozir faol safar yo'q.")
        return
    waiting = order["status"] == "waiting"
    stage = "accepted" if order["status"] == "accepted" else "in_progress"
    text = f"🚗 Buyurtma #{order['id']}\n{order['actual_km']} km · {money(order['price'])} so'm"
    if order["order_type"] == "street":
        text += "\n🛑 (Yo'lda/bordyurdan olingan mijoz)"
    elif order.get("phone_client_name"):
        text += f"\n👤 {order['phone_client_name']} · 📞 {order.get('phone_client_phone') or '-'}"
        text += f"\n📍 {order['pickup_text']}"
    else:
        client = db.get_user(order["client_id"])
        if client:
            text += f"\n👤 {client['name']} · 📞 {client['phone']}"
        text += f"\n📍 {order['pickup_text']}"
    await message.answer(text, reply_markup=kb.trip_controls_kb(order["id"], stage, waiting=waiting))


@router.message(F.text == "📊 Statistikam")
async def driver_stats(message: Message):
    driver = db.get_driver(message.from_user.id)
    if not driver:
        return
    orders = [o for o in db.list_recent_orders(500) if o["driver_id"] == message.from_user.id and o["status"] == "finished"]
    revenue = sum(o["price"] for o in orders)
    await message.answer(
        f"📊 Statistika\nSafarlar: {len(orders)}\nTushum: {money(revenue)} so'm\nReyting: {driver['rating']:.1f} ⭐"
    )


# ---------------- yo'lda (bordyurdan) mijoz olish ----------------
@router.message(F.text == "🛑 Yo'lda mijoz oldim")
async def street_pickup_start(message: Message, state: FSMContext):
    driver = db.get_driver(message.from_user.id)
    if not driver or driver["blocked"]:
        return
    warn = sub_warning_text(driver)
    if warn:
        await message.answer(warn)
        return
    active = db.get_active_order_for_driver(message.from_user.id)
    if active:
        await message.answer("Avval joriy safarni yakunlang.")
        return
    await state.set_state(DriverStreetPickup.waiting_region)
    await message.answer(
        "Mijoz qaysi hududda o'tirdi? Hududni tanlang — taksometrni o'zingiz boshqarasiz:",
        reply_markup=kb.regions_inline_kb(prefix="streetregion"),
    )


@router.callback_query(DriverStreetPickup.waiting_region, F.data.startswith("streetregion:"))
async def street_pickup_region(call: CallbackQuery, state: FSMContext):
    region_id = int(call.data.split(":")[1])
    await state.clear()
    driver = db.get_driver(call.from_user.id)
    if not driver:
        await call.answer("Xatolik", show_alert=True)
        return
    region = db.get_region(region_id)
    tariff = db.get_tariff(driver["tariff"])
    price = pricing.fare(region, tariff, 0)
    order_id = db.create_order(
        client_id=call.from_user.id, region_id=region_id, tariff_id=driver["tariff"], payment_method="naqd",
        pickup_text="Yo'lda (bordyurdan)", pickup_lat=None, pickup_lng=None,
        dest_text=None, dest_lat=None, dest_lng=None, est_km=0, price=price, order_type="street",
    )
    db.accept_order(order_id, call.from_user.id)
    db.start_trip(order_id)
    db.set_driver_status(call.from_user.id, "busy")
    await call.message.edit_text("🛑 Yo'lda mijoz qabul qilindi.")
    await call.message.answer(
        f"🚗 Safar boshlandi (yo'lda).\nNarx: {money(price)} so'm (o'zgarmaydi)\n"
        f"Kutish yoqilsa ham umumiy narx shu summadan oshmaydi. Kerak bo'lsa \"⏳ Kutish\" va "
        f"\"🏁 Yakunlash\" tugmalaridan foydalaning. To'liq xarita va navigatsiya uchun ilovadan "
        f"(mini app) foydalaning: /start → 🚗 Haydovchi.",
        reply_markup=kb.trip_controls_kb(order_id, "in_progress"),
    )
    await call.answer()


# ---------------- accepting orders ----------------
@router.callback_query(F.data.startswith("accept:"))
async def accept_order(call: CallbackQuery, bot):
    order_id = int(call.data.split(":")[1])
    driver = db.get_driver(call.from_user.id)
    if not driver or driver["blocked"]:
        await call.answer("Siz haydovchi emassiz yoki bloklangansiz", show_alert=True)
        return
    if driver["status"] != "available":
        await call.answer("Avval onlayn bo'ling yoki joriy buyurtmani yakunlang", show_alert=True)
        return
    if not db.driver_subscription_active(driver):
        db.set_driver_status(call.from_user.id, "offline")
        await call.answer("Obuna muddati tugagan. Admin bilan bog'lanib to'lovni tasdiqlating.", show_alert=True)
        return
    ok = db.accept_order(order_id, call.from_user.id)
    if not ok:
        reason = db.order_fail_reason(order_id)
        if reason == "expired":
            note = "⏰ Bu buyurtmaning muddati tugagan — uzoq vaqt hech kim javob bermagani uchun avtomatik bekor bo'lgan."
            alert = "Buyurtma muddati tugagan"
        elif reason == "cancelled":
            note = "🚫 Bu buyurtma mijoz (yoki dispetcher) tomonidan bekor qilingan."
            alert = "Buyurtma bekor qilingan"
        elif reason == "not_found":
            note = "❌ Bu buyurtma topilmadi."
            alert = "Buyurtma topilmadi"
        else:
            note = "❌ Bu buyurtma oldin boshqa haydovchi tomonidan qabul qilingan."
            alert = "Oldin qabul qilingan"
        try:
            await call.message.edit_text(call.message.text + f"\n\n{note}")
        except Exception:
            pass  # xabar allaqachon o'zgartirilgan bo'lishi mumkin (masalan tezkor qayta bosish) — muhim emas
        await call.answer(alert, show_alert=True)
        return
    db.set_driver_status(call.from_user.id, "busy")
    order = db.get_order(order_id)
    is_phone_order = bool(order.get("phone_client_name"))
    await call.message.edit_text(call.message.text + "\n\n✅ Siz qabul qildingiz.")
    # Shu buyurtma yuborilgan boshqa haydovchilarning xabarlarini avtomatik "band bo'ldi"
    # deb tahrirlaymiz — ular endi eskirgan zayavkani ko'rib chalg'imaydi.
    await dispatch.mark_order_taken_for_others(bot, order_id, call.from_user.id)
    if is_phone_order:
        client_line = f"👤 Mijoz: {order['phone_client_name']}\n📞 {order.get('phone_client_phone') or '-'}\n"
    else:
        client = db.get_user(order["client_id"])
        client_line = f"👤 Mijoz: {client['name']}\n📞 {client['phone']}\n"
    await call.message.answer(
        client_line + f"📍 {order['pickup_text']}"
        + (f"\n🏁 {order['dest_text']}" if order['dest_text'] else ""),
        reply_markup=kb.trip_controls_kb(order_id, "accepted"),
    )
    await call.answer()
    if is_phone_order:
        # Telefon orqali olingan buyurtma — haqiqiy mijoz botda emas, buyurtmani kiritgan
        # dispetcherga xabar beramiz (client_id endi mijozning doimiy "virtual" ID'si,
        # real Telegram chat emas — shuning uchun created_by ishlatiladi).
        notify_id = order.get("created_by") or order["client_id"]
        try:
            await bot.send_message(
                notify_id,
                f"🚗 Buyurtma #{order_id} uchun haydovchi topildi: {driver['name']} · ⭐ {driver['rating']:.1f} · 📞 {driver['phone']}\n"
                f"Mijozga ({order['phone_client_name']}, {order.get('phone_client_phone') or '-'}) qo'ng'iroq qilib xabar bering.",
            )
        except Exception:
            pass
    else:
        try:
            await bot.send_message(
                order["client_id"],
                f"🚗 Haydovchi topildi!\n{driver['name']} · ⭐ {driver['rating']:.1f}\n📞 {driver['phone']}\nSizga yo'lda.",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("start:"))
async def start_trip(call: CallbackQuery, bot):
    order_id = int(call.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != call.from_user.id:
        await call.answer("Xatolik", show_alert=True)
        return
    db.start_trip(order_id)
    await call.message.edit_text("🚗 Safar boshlandi.\n0.0 km · " + money(order["price"]) + " so'm",
                                  reply_markup=kb.trip_controls_kb(order_id, "in_progress"))
    await call.answer()
    try:
        await bot.send_message(order["client_id"], "🚗 Haydovchi safarni boshladi. Yaxshi yo'l!")
    except Exception:
        pass


@router.callback_query(F.data.startswith("waiton:"))
async def wait_on(call: CallbackQuery, bot):
    order_id = int(call.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != call.from_user.id:
        await call.answer("Xatolik", show_alert=True)
        return
    db.start_waiting(order_id)
    await call.message.edit_text(
        call.message.text + "\n\n⏳ Kutish yoqildi.",
        reply_markup=kb.trip_controls_kb(order_id, "in_progress", waiting=True),
    )
    await call.answer()


@router.callback_query(F.data.startswith("waitoff:"))
async def wait_off(call: CallbackQuery):
    order_id = int(call.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != call.from_user.id or not order["wait_started_at"]:
        await call.answer("Xatolik", show_alert=True)
        return
    region = db.get_region(order["region_id"])
    seconds = int(time.time()) - order["wait_started_at"]
    added = pricing.wait_charge(seconds, region["wait_per_min"])
    new_total = order["price"] + added
    # Mijozga boshida ko'rsatilgan narx (quoted_price) — bundan oshib ketmasligi kerak.
    ceiling = order.get("quoted_price") or order["price"]
    new_total = min(new_total, ceiling)
    db.stop_waiting(order_id, seconds, added, new_total)
    await call.message.edit_text(
        f"🚗 Safar davom etmoqda.\n{order['actual_km']} km · {money(new_total)} so'm\n"
        f"(kutish: {seconds} soniya · +{money(added)} so'm)",
        reply_markup=kb.trip_controls_kb(order_id, "in_progress"),
    )
    await call.answer(f"Kutish: {seconds}s · +{money(added)} so'm")


@router.callback_query(F.data.startswith("finish:"))
async def finish_trip(call: CallbackQuery, bot):
    order_id = int(call.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["driver_id"] != call.from_user.id:
        await call.answer("Xatolik", show_alert=True)
        return
    db.finish_order(order_id)
    db.set_driver_status(call.from_user.id, "available")
    driver = db.get_driver(call.from_user.id)
    await call.message.edit_text(f"🏁 Safar yakunlandi.\nJami: {money(order['price'])} so'm\nRahmat!")
    await call.answer()
    if order.get("phone_client_name"):
        # Telefon orqali olingan buyurtma — dispetcherga yakun haqida xabar, mijozdan bot orqali baho so'ralmaydi
        notify_id = order.get("created_by") or order["client_id"]
        try:
            await bot.send_message(
                notify_id,
                f"🏁 Buyurtma #{order_id} yakunlandi.\n💰 {money(order['price'])} so'm",
            )
        except Exception:
            pass
    elif order["order_type"] != "street":
        try:
            await bot.send_message(
                order["client_id"],
                f"🏁 Safar yakunlandi.\n💰 {money(order['price'])} so'm\n\nHaydovchini baholang:",
                reply_markup=kb.rating_kb(order_id),
            )
        except Exception:
            pass
