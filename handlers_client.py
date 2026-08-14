import asyncio
import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

import db
import pricing
import keyboards as kb
import dispatch
from states import Registration, OrderFlow

router = Router(name="client")


def money(n):
    return f"{round(n):,}".replace(",", " ")


def esc(s):
    return html.escape(str(s)) if s is not None else ""


# ---------------- registration ----------------
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if user and user["name"] and user["phone"]:
        await message.answer(
            f"👋 <b>Xush kelibsiz, {esc(user['name'].split()[0])}!</b>\n\n"
            f"🚕 <b>LaboOltiariq</b> taksi xizmatiga qaytganingizdan xursandmiz.\n"
            f"Quyidagi menyudan kerakli bo'limni tanlang 👇",
            reply_markup=kb.client_menu_kb(),
            parse_mode="HTML",
        )
        return
    await state.set_state(Registration.waiting_name)
    await message.answer(
        "✨ <b>LaboOltiariq</b> botiga xush kelibsiz!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚕 Ishonchli va tezkor taksi xizmati\n\n"
        "📝 <b>Ro'yxatdan o'tish — 1/2</b>\n"
        "Ismingizni yuboring:",
        reply_markup=kb.remove_kb(),
        parse_mode="HTML",
    )


@router.message(Registration.waiting_name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Registration.waiting_phone)
    await message.answer(
        f"✅ Rahmat, <b>{esc(message.text.strip())}</b>!\n\n"
        f"📝 <b>Ro'yxatdan o'tish — 2/2</b>\n"
        f"Endi telefon raqamingizni yuboring (tugma orqali tezroq bo'ladi):",
        reply_markup=kb.contact_kb(),
        parse_mode="HTML",
    )


@router.message(Registration.waiting_phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    db.upsert_user(message.from_user.id, name=data["name"], phone=message.contact.phone_number, role="client")
    await state.clear()
    await message.answer(
        "🎉 <b>Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Endi taksi chaqirishingiz mumkin — quyidagi menyudan foydalaning 👇",
        reply_markup=kb.client_menu_kb(),
        parse_mode="HTML",
    )


@router.message(Registration.waiting_phone, F.text)
async def reg_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+") or len(phone) < 9:
        await message.answer("⚠️ Iltimos, to'g'ri formatda yuboring: +998901234567, yoki tugma orqali yuboring.")
        return
    data = await state.get_data()
    db.upsert_user(message.from_user.id, name=data["name"], phone=phone, role="client")
    await state.clear()
    await message.answer(
        "🎉 <b>Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Endi taksi chaqirishingiz mumkin — quyidagi menyudan foydalaning 👇",
        reply_markup=kb.client_menu_kb(),
        parse_mode="HTML",
    )


@router.message(F.text == "👤 Profil")
async def show_profile(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        return
    await message.answer(
        f"👤 <b>Profilingiz</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🙍 Ism: <b>{esc(user['name'])}</b>\n"
        f"📞 Telefon: <b>{esc(user['phone'])}</b>",
        parse_mode="HTML",
    )


# ---------------- ordering ----------------
@router.message(F.text == "🚕 Taksi chaqirish")
async def start_order(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user or not user["phone"]:
        await message.answer("Avval ro'yxatdan o'ting: /start")
        return
    active = db.get_active_order_for_client(message.from_user.id)
    if active:
        await message.answer("⚠️ Sizda allaqachon faol buyurtma bor. Holatni ko'rish uchun /status yuboring.")
        return
    await state.set_state(OrderFlow.waiting_pickup)
    await message.answer(
        "🚕 <b>Yangi buyurtma</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📍 Qayerdasiz? Joylashuvingizni yuboring (aniq narx uchun eng ishonchli usul) yoki manzilni yozing:",
        reply_markup=kb.location_kb(),
        parse_mode="HTML",
    )


@router.message(OrderFlow.waiting_pickup, F.location)
async def pickup_location(message: Message, state: FSMContext):
    await state.update_data(
        pickup_text="Joylashuv orqali yuborildi",
        pickup_lat=message.location.latitude,
        pickup_lng=message.location.longitude,
    )
    await state.set_state(OrderFlow.waiting_destination)
    await message.answer(
        "Qayerga ketasiz? Manzil joylashuvini yuboring yoki matn bilan yozing "
        "(masofa aniq bo'lishi uchun joylashuv afzal):",
        reply_markup=kb.location_kb(skip_text="✏️ Faqat manzil yozaman"),
    )


@router.message(OrderFlow.waiting_pickup, F.text)
async def pickup_text(message: Message, state: FSMContext):
    await state.update_data(pickup_text=message.text.strip(), pickup_lat=None, pickup_lng=None)
    await state.set_state(OrderFlow.waiting_destination)
    await message.answer(
        "Qayerga ketasiz? Manzilni yozing yoki joylashuv yuboring:",
        reply_markup=kb.location_kb(skip_text="✏️ Faqat manzil yozaman"),
    )


@router.message(OrderFlow.waiting_destination, F.location)
async def dest_location(message: Message, state: FSMContext):
    data = await state.get_data()
    est_km = 4.0
    if data.get("pickup_lat") is not None:
        # Avval haqiqiy yo'l masofasini (OSRM) so'raymiz — ishlamasa avtomatik to'g'ri
        # chiziq (haversine) formulasiga o'tadi, mijoz baribir narxni ko'raveradi.
        est_km = await pricing.route_km(
            data["pickup_lat"], data["pickup_lng"], message.location.latitude, message.location.longitude
        )
    await state.update_data(
        dest_text="Joylashuv orqali yuborildi",
        dest_lat=message.location.latitude,
        dest_lng=message.location.longitude,
        est_km=est_km,
    )
    await ask_region(message, state)


@router.message(OrderFlow.waiting_destination, F.text == "✏️ Faqat manzil yozaman")
async def dest_skip(message: Message, state: FSMContext):
    await message.answer("Manzilni yozing:", reply_markup=kb.remove_kb())


@router.message(OrderFlow.waiting_destination, F.text)
async def dest_text_handler(message: Message, state: FSMContext):
    await state.update_data(dest_text=message.text.strip(), dest_lat=None, dest_lng=None, est_km=4.0)
    await ask_region(message, state)


async def ask_region(message: Message, state: FSMContext):
    await state.set_state(OrderFlow.waiting_region)
    await message.answer("Hududni tanlang:", reply_markup=kb.remove_kb())
    await message.answer("👇", reply_markup=kb.regions_inline_kb())


@router.callback_query(OrderFlow.waiting_region, F.data.startswith("region:"))
async def region_chosen(call: CallbackQuery, state: FSMContext):
    region_id = int(call.data.split(":")[1])
    data = await state.get_data()
    await state.update_data(region_id=region_id)
    await state.set_state(OrderFlow.waiting_tariff)
    km = data.get("est_km", 4.0)
    if data.get("pickup_lat") is None:
        # No GPS distance available — ask a rough estimate instead of guessing silently.
        await call.message.answer(
            f"Taxminiy masofa avtomatik aniqlanmadi (joylashuv yuborilmadi). Standart {km} km bo'yicha hisoblanadi.\n"
            f"Aniqroq narx uchun keyingi safar joylashuvni yuboring."
        )
    # Hudud tugmalari turgan xabarning o'zini tahrirlaymiz (yangi xabar yubormaymiz) —
    # shunda eski hudud ro'yxati ekranda qolib ketmaydi, mashina turlari o'sha joyning
    # o'zida almashadi.
    await call.message.edit_text("Tarifni tanlang:", reply_markup=kb.tariffs_inline_kb(region_id, km))
    await call.answer()


@router.callback_query(OrderFlow.waiting_tariff, F.data.startswith("tariff:"))
async def tariff_chosen(call: CallbackQuery, state: FSMContext):
    tariff_id = call.data.split(":")[1]
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(OrderFlow.waiting_payment)
    await call.message.answer("To'lov turini tanlang:", reply_markup=kb.payment_inline_kb())
    await call.answer()


@router.callback_query(OrderFlow.waiting_payment, F.data.startswith("pay:"))
async def payment_chosen(call: CallbackQuery, state: FSMContext):
    payment = call.data.split(":")[1]
    data = await state.get_data()
    region = db.get_region(data["region_id"])
    tariff = db.get_tariff(data["tariff_id"])
    km = data.get("est_km", 4.0)
    price = pricing.fare(region, tariff, km)
    await state.update_data(payment_method=payment, price=price)
    summary = (
        f"📋 <b>Buyurtma tafsilotlari</b>\n\n"
        f"📍 Qayerdan: {data['pickup_text']}\n"
        f"🏁 Qayerga: {data['dest_text']}\n"
        f"🗺 Hudud: {region['name']}\n"
        f"🚗 Tarif: {tariff['name']}\n"
        f"📏 Masofa: ~{km} km\n"
        f"💳 To'lov: {'Naqd' if payment=='naqd' else 'Karta'}\n\n"
        f"💰 <b>Taxminiy narx: {money(price)} so'm</b>"
    )
    await call.message.answer(summary, reply_markup=kb.confirm_order_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "cancel_order_draft")
async def cancel_draft(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("Buyurtma bekor qilindi.", reply_markup=kb.client_menu_kb())
    await call.answer()


@router.callback_query(F.data == "confirm_order")
async def confirm_order(call: CallbackQuery, state: FSMContext, bot):
    data = await state.get_data()
    order_id = db.create_order(
        client_id=call.from_user.id,
        region_id=data["region_id"],
        tariff_id=data["tariff_id"],
        payment_method=data["payment_method"],
        pickup_text=data["pickup_text"],
        pickup_lat=data.get("pickup_lat"),
        pickup_lng=data.get("pickup_lng"),
        dest_text=data["dest_text"],
        dest_lat=data.get("dest_lat"),
        dest_lng=data.get("dest_lng"),
        est_km=data.get("est_km", 4.0),
        price=data["price"],
    )
    await state.clear()
    await call.answer()

    # Avval dispetcherga tasdiqlash uchun yuboriladi — faqat dispetcher tasdiqlagandan (yoki hech
    # qanday dispetcher ro'yxatdan o'tmagan bo'lsa) keyin haydovchilarga zayavka ketadi.
    dispatchers = db.list_admin_ids("dispatcher")
    if dispatchers:
        await call.message.answer(
            f"✅ Buyurtma #{order_id} qabul qilindi. Dispetcher tasdiqlashini kutmoqda...\nHolatni ko'rish uchun /status",
            reply_markup=kb.client_menu_kb(),
        )
        asyncio.create_task(dispatch.notify_dispatchers_new_order(bot, order_id))
    else:
        # Hozircha birorta dispetcher /dispetcher orqali kirmagan — buyurtma osilib qolmasligi uchun
        # to'g'ridan-to'g'ri haydovchilarga yuboriladi (eski xatti-harakat, zaxira variant sifatida).
        await call.message.answer(
            f"✅ Buyurtma #{order_id} qabul qilindi. Haydovchi qidirilmoqda...\nHolatni ko'rish uchun /status",
            reply_markup=kb.client_menu_kb(),
        )
        asyncio.create_task(dispatch.dispatch_order(bot, order_id))


@router.message(Command("status"))
@router.message(F.text == "📋 Buyurtmalarim")
async def check_status(message: Message):
    order = db.get_active_order_for_client(message.from_user.id)
    if not order:
        await message.answer("Hozircha faol buyurtmangiz yo'q.")
        return
    labels = {"new": "Qidirilmoqda", "accepted": "Haydovchi topildi", "in_progress": "Yo'lda", "waiting": "Kutmoqda"}
    text = f"📋 Buyurtma #{order['id']} — {labels.get(order['status'], order['status'])}\n💰 {money(order['price'])} so'm"
    if order["driver_id"]:
        driver = db.get_driver(order["driver_id"])
        text += f"\n🚗 Haydovchi: {driver['name']} · ⭐ {driver['rating']:.1f}\n📞 {driver['phone']}"
    can_cancel = order["status"] in ("new", "accepted")
    await message.answer(text, reply_markup=kb.status_kb(order["id"]) if can_cancel else None)


@router.callback_query(F.data.startswith("clientcancel:"))
async def client_cancel_order(call: CallbackQuery, bot):
    order_id = int(call.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["client_id"] != call.from_user.id:
        await call.answer("Xatolik", show_alert=True)
        return
    if order["status"] not in ("new", "accepted"):
        await call.answer("Bu buyurtmani endi bekor qilib bo'lmaydi (safar allaqachon boshlangan).", show_alert=True)
        return
    ok = db.cancel_order_by_client(order_id, call.from_user.id)
    if not ok:
        await call.answer("Xatolik", show_alert=True)
        return
    if order["driver_id"]:
        db.set_driver_status(order["driver_id"], "available")
        try:
            await bot.send_message(order["driver_id"], f"❌ Mijoz buyurtma #{order_id} ni bekor qildi.")
        except Exception:
            pass
    await call.message.edit_text("❌ Buyurtma bekor qilindi.")
    await call.answer()


# ---------------- order history ----------------
@router.message(F.text == "📜 Tarix")
async def order_history(message: Message):
    orders = db.get_orders_for_client(message.from_user.id, limit=10)
    if not orders:
        await message.answer("Buyurtmalar tarixi hozircha bo'sh.")
        return
    labels = {
        "finished": "✅ Yakunlangan", "cancelled": "✖️ Bekor qilingan",
        "new": "⏳ Qidirilgan", "accepted": "⏳ Qabul qilingan",
        "in_progress": "⏳ Yo'lda edi", "waiting": "⏳ Kutilgan",
    }

    def _label(o):
        if o["status"] == "cancelled" and o.get("cancel_reason") == "expired":
            return "⏰ Muddati tugagan"
        return labels.get(o["status"], o["status"])

    lines = [f"#{o['id']} · {_label(o)} · {money(o['price'])} so'm" for o in orders]
    await message.answer("📜 Oxirgi buyurtmalaringiz:\n" + "\n".join(lines))


# ---------------- SOS / yordam ----------------
@router.message(F.text == "🆘 Yordam")
async def sos(message: Message, bot):
    user = db.get_user(message.from_user.id)
    order = db.get_active_order_for_client(message.from_user.id)
    admins = db.list_admin_ids()
    text = (
        f"🆘 <b>Yordam so'ralmoqda!</b>\n"
        f"👤 {user['name'] if user else message.from_user.id}\n"
        f"📞 {user['phone'] if user else '-'}"
    )
    if order:
        text += f"\n📋 Faol buyurtma #{order['id']}"
    if not admins:
        await message.answer("So'rovingiz qayd etildi, lekin hozircha ulangan admin topilmadi. Admin botga kirganda ko'radi.")
        return
    sent = 0
    for a in admins:
        try:
            await bot.send_message(a["user_id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    if sent:
        await message.answer("🆘 So'rovingiz adminga yuborildi. Tez orada bog'lanishadi.")
    else:
        await message.answer("So'rovingiz qayd etildi, lekin adminlarga yetkazib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.")


# ---------------- rating ----------------
@router.callback_query(F.data.startswith("rate:"))
async def rate_trip(call: CallbackQuery):
    _, order_id, stars = call.data.split(":")
    order_id, stars = int(order_id), int(stars)
    order = db.get_order(order_id)
    if not order or order["client_id"] != call.from_user.id:
        await call.answer("Xatolik", show_alert=True)
        return
    db.rate_order(order_id, stars)
    if order["driver_id"]:
        db.add_driver_rating(order["driver_id"], stars)
    await call.message.edit_text(f"Rahmat! Siz {stars}⭐ baho berdingiz.")
    await call.answer()
