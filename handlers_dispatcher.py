import time
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandObject

import db
import pricing
import dispatch
import keyboards as kb
from states import DispatcherLogin, DispatcherAddOrder

router = Router(name="dispatcher")

_dispatchers = set()  # in-memory session of telegram ids currently authed as dispatcher this run


def money(n):
    return f"{round(n):,}".replace(",", " ")


def is_dispatcher(user_id):
    if user_id in _dispatchers:
        return True
    # Xotiradagi sessiya bot qayta ishga tushganda (masalan Railway'da har deployda) tozalanadi —
    # lekin bazada avval tasdiqlangan dispetcher bo'lsa, parolni qayta so'ramasdan tanib olamiz.
    if any(a["user_id"] == user_id for a in db.list_admin_ids("dispatcher")):
        _dispatchers.add(user_id)
        return True
    return False


@router.message(Command("dispetcher"))
async def dispatcher_login(message: Message, state: FSMContext, command: CommandObject):
    if command.args:
        await try_password(message, command.args.strip())
    else:
        await state.set_state(DispatcherLogin.waiting_password)
        await message.answer(
            "📡 <b>Dispetcher kirish</b>\n━━━━━━━━━━━━━━━━━━\n🔑 Parolni kiriting:",
            parse_mode="HTML",
        )


@router.message(DispatcherLogin.waiting_password)
async def dispatcher_password_input(message: Message, state: FSMContext):
    await state.clear()
    await try_password(message, message.text.strip())


async def try_password(message: Message, password: str):
    if password != db.get_setting("dispatcher_password"):
        await message.answer("❌ Parol noto'g'ri.")
        return
    _dispatchers.add(message.from_user.id)
    db.add_admin_id(message.from_user.id, "dispatcher")  # SOS xabarlarini olishi uchun doimiy saqlanadi
    # users jadvalida ham qatori bo'lishi kerak — aks holda "Zakaz qo'shish" orqali yaratilgan
    # buyurtmalarning client_id FOREIGN KEY'i (dispetcherning o'z ID'siga) xatolik beradi
    db.upsert_user(message.from_user.id, role="dispatcher")
    await message.answer(
        "✅ <b>Dispetcher panelga xush kelibsiz!</b>\n━━━━━━━━━━━━━━━━━━\nQuyidagi menyudan foydalaning 👇",
        reply_markup=kb.dispatcher_menu_kb(),
        parse_mode="HTML",
    )


@router.message(F.text == "📋 Faol buyurtmalar")
async def active_orders(message: Message):
    if not is_dispatcher(message.from_user.id):
        return
    orders = db.list_active_orders()
    if not orders:
        await message.answer("Faol buyurtmalar yo'q.")
        return
    labels = {"new": "Yangi", "accepted": "Qabul qilindi", "in_progress": "Yo'lda", "waiting": "Kutmoqda"}
    for o in orders:
        region = db.get_region(o["region_id"])
        client = db.get_user(o["client_id"])
        text = (
            f"#{o['id']} · {labels.get(o['status'], o['status'])}\n"
            f"👤 {client['name']}\n🗺 {region['name']} · 💰 {money(o['price'])} so'm"
        )
        if o["status"] == "new":
            available = db.list_available_drivers(o["tariff_id"])
            await message.answer(text, reply_markup=kb.dispatcher_new_order_kb(o["id"], available))
        elif o["status"] == "accepted":
            available = db.list_available_drivers(o["tariff_id"])
            await message.answer(text, reply_markup=kb.dispatcher_order_kb(o["id"], available))
        else:
            # Yo'lda/kutmoqda bosqichidagi safarni qayta tayinlab bo'lmaydi — faqat bekor qilish tugmasi
            await message.answer(text, reply_markup=kb.dcancel_only_kb(o["id"]))


@router.message(F.text == "🚦 Haydovchilar holati")
async def drivers_status(message: Message):
    if not is_dispatcher(message.from_user.id):
        return
    drivers = db.list_drivers()
    if not drivers:
        await message.answer("Haydovchilar yo'q.")
        return
    now = int(time.time())
    lines = []
    for d in drivers:
        status = "🔒 bloklangan" if d["blocked"] else ("🟢 bo'sh" if d["status"] == "available" else "🟡 band")
        sub_ok = d.get("sub_until") and d["sub_until"] > now
        sub_mark = "💳✅" if sub_ok else "💳❌"
        loc = ""
        if d.get("loc_updated_at"):
            age_min = (now - d["loc_updated_at"]) // 60
            loc = f" · 📍{age_min}m oldin"
        t = db.get_tariff(d["tariff"])
        tariff_label = t["name"] if t else d["tariff"]
        lines.append(f"{d['name']} · {tariff_label} · {status} · ⭐{d['rating']:.1f} · {sub_mark}{loc}")
    await message.answer("\n".join(lines) + "\n\nTo'liq joylashuvni ko'rish uchun admin panelidagi "
                          "'📍 Xaydovchilar joylashuvi' bo'limidan foydalaning.")


@router.callback_query(F.data.startswith("dispatch_confirm:"))
async def dispatch_confirm(call: CallbackQuery, bot):
    """Dispetcher buyurtmani tasdiqladi — endi yaqin (15 km ichidagi) haydovchilarga
    bosqichma-bosqich, masofaga qarab boshqacha ovoz bilan zayavka ketadi."""
    order_id = int(call.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["status"] != "new":
        await call.answer("Bu buyurtma endi tasdiqlanmaydi", show_alert=True)
        return
    await call.message.edit_text(call.message.text + "\n\n✅ Tasdiqlandi — haydovchilarga yuborilmoqda.")
    await call.answer()
    asyncio.create_task(dispatch.dispatch_order(bot, order_id))


@router.callback_query(F.data.startswith("reassign:"))
async def reassign(call: CallbackQuery, bot):
    _, order_id, driver_id = call.data.split(":")
    order_id, driver_id = int(order_id), int(driver_id)
    order = db.get_order(order_id)
    if not order or order["status"] not in ("new", "accepted"):
        await call.answer("Bu buyurtma endi qayta tayinlanmaydi", show_alert=True)
        return
    if driver_id == order["driver_id"]:
        await call.answer("Bu haydovchida buyurtma allaqachon bor", show_alert=True)
        return
    previous_driver_id = order["driver_id"] if order["status"] == "accepted" else None
    ok = db.accept_order(order_id, driver_id) if order["status"] == "new" else True
    if order["status"] == "accepted":
        # already assigned — dispatcher force-reassigns
        with db.get_conn() as conn:
            conn.execute("UPDATE orders SET driver_id=? WHERE id=?", (driver_id, order_id))
    db.set_driver_status(driver_id, "busy")
    if previous_driver_id:
        # eski haydovchini "band" holatida abadiy qolib ketmasligi uchun bo'shatamiz
        db.set_driver_status(previous_driver_id, "available")
        try:
            await bot.send_message(previous_driver_id, f"⚠️ Buyurtma #{order_id} dispetcher tomonidan boshqa haydovchiga qayta tayinlandi.")
        except Exception:
            pass
    await call.message.edit_text(call.message.text + f"\n\n✅ Haydovchi tayinlandi.")
    await call.answer()
    # Buyurtma "new" holatidan tayinlangan bo'lsa, unga yuborilgan boshqa haydovchilarning
    # xabarlarini ham "band bo'ldi" deb avtomatik tahrirlaymiz.
    await dispatch.mark_order_taken_for_others(bot, order_id, driver_id)
    driver = db.get_driver(driver_id)
    try:
        await bot.send_message(
            driver_id,
            f"📌 Dispetcher sizga buyurtma #{order_id} ni tayinladi.\n📍 {order['pickup_text']}",
            reply_markup=kb.trip_controls_kb(order_id, "accepted"),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("dcancel:"))
async def dispatcher_cancel(call: CallbackQuery, bot):
    order_id = int(call.data.split(":")[1])
    order = db.get_order(order_id)
    db.cancel_order(order_id)
    if order and order["driver_id"]:
        db.set_driver_status(order["driver_id"], "available")
    await call.message.edit_text(call.message.text + "\n\n✖️ Bekor qilindi (dispetcher).")
    await call.answer()
    if order:
        try:
            await bot.send_message(order["client_id"], f"Buyurtma #{order_id} dispetcher tomonidan bekor qilindi.")
        except Exception:
            pass


# ---------------- telefon orqali olingan buyurtmani qo'lda qo'shish ----------------
@router.message(F.text == "➕ Zakaz qo'shish")
async def add_order_start(message: Message, state: FSMContext):
    if not is_dispatcher(message.from_user.id):
        return
    await state.set_state(DispatcherAddOrder.phone)
    await message.answer(
        "Mijozning telefon raqamini kiriting (masalan +998901234567):\n\n"
        "(Agar bu raqam avval qo'ng'iroq qilgan bo'lsa, ismi bazadan avtomatik topiladi — "
        "qayta kiritish shart emas)",
        reply_markup=kb.remove_kb(),
    )


@router.message(DispatcherAddOrder.phone)
async def add_order_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    existing = db.get_phone_client_by_phone(phone)
    if existing and existing.get("name"):
        await state.update_data(name=existing["name"])
        await state.set_state(DispatcherAddOrder.pickup)
        await message.answer(
            f"👤 Bazada topildi: {existing['name']}\n\n"
            f"Qayerdan olib ketish kerak? Joylashuvni yuboring yoki manzilni yozing:",
            reply_markup=kb.location_kb(),
        )
        return
    await state.set_state(DispatcherAddOrder.name)
    await message.answer("Bu raqam bazada yo'q. Mijozning ism-familiyasini kiriting:")


@router.message(DispatcherAddOrder.name)
async def add_order_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(DispatcherAddOrder.pickup)
    await message.answer(
        "Qayerdan olib ketish kerak? Joylashuvni yuboring yoki manzilni yozing:",
        reply_markup=kb.location_kb(),
    )


@router.message(DispatcherAddOrder.pickup, F.location)
async def add_order_pickup_location(message: Message, state: FSMContext):
    await state.update_data(
        pickup_text="Joylashuv orqali yuborildi",
        pickup_lat=message.location.latitude,
        pickup_lng=message.location.longitude,
    )
    await state.set_state(DispatcherAddOrder.destination)
    await message.answer(
        "Qayerga borish kerak? Manzil joylashuvini yuboring yoki matn bilan yozing "
        "(noma'lum bo'lsa \"-\" yuboring yoki quyidagi tugmani bosing):",
        reply_markup=kb.location_kb(skip_text="➖ Manzil noma'lum"),
    )


@router.message(DispatcherAddOrder.pickup, F.text)
async def add_order_pickup(message: Message, state: FSMContext):
    await state.update_data(pickup_text=message.text.strip(), pickup_lat=None, pickup_lng=None)
    await state.set_state(DispatcherAddOrder.destination)
    await message.answer(
        "Qayerga borish kerak? Manzil joylashuvini yuboring yoki matn bilan yozing "
        "(noma'lum bo'lsa \"-\" yuboring yoki quyidagi tugmani bosing):",
        reply_markup=kb.location_kb(skip_text="➖ Manzil noma'lum"),
    )


@router.message(DispatcherAddOrder.destination, F.location)
async def add_order_destination_location(message: Message, state: FSMContext):
    data = await state.get_data()
    dest_lat, dest_lng = message.location.latitude, message.location.longitude
    km = None
    if data.get("pickup_lat") is not None:
        # Ikkala nuqta ham GPS orqali ma'lum — haqiqiy yo'l masofasini avtomatik hisoblaymiz,
        # dispetcherdan endi km qo'lda so'ralmaydi.
        km = await pricing.route_km(data["pickup_lat"], data["pickup_lng"], dest_lat, dest_lng)
    await state.update_data(dest_text="Joylashuv orqali yuborildi", dest_lat=dest_lat, dest_lng=dest_lng, km=km)
    await state.set_state(DispatcherAddOrder.region)
    await message.answer("Hududni tanlang:", reply_markup=kb.remove_kb())
    await message.answer("👇", reply_markup=kb.regions_inline_kb(prefix="dregion"))


@router.message(DispatcherAddOrder.destination, F.text == "➖ Manzil noma'lum")
async def add_order_destination_skip(message: Message, state: FSMContext):
    await state.update_data(dest_text=None, dest_lat=None, dest_lng=None)
    await state.set_state(DispatcherAddOrder.region)
    await message.answer("Hududni tanlang:", reply_markup=kb.remove_kb())
    await message.answer("👇", reply_markup=kb.regions_inline_kb(prefix="dregion"))


@router.message(DispatcherAddOrder.destination, F.text)
async def add_order_destination(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(dest_text=None if text == "-" else text, dest_lat=None, dest_lng=None)
    await state.set_state(DispatcherAddOrder.region)
    await message.answer("Hududni tanlang:", reply_markup=kb.remove_kb())
    await message.answer("👇", reply_markup=kb.regions_inline_kb(prefix="dregion"))


@router.callback_query(DispatcherAddOrder.region, F.data.startswith("dregion:"))
async def add_order_region(call: CallbackQuery, state: FSMContext):
    region_id = int(call.data.split(":")[1])
    await state.update_data(region_id=region_id)
    data = await state.get_data()
    km = data.get("km")
    if km is not None:
        # Pickup va destination ikkalasi ham joylashuv orqali berilgan — masofa allaqachon
        # avtomatik hisoblangan, km'ni qo'lda so'rashning hojati yo'q.
        await state.set_state(DispatcherAddOrder.tariff)
        await call.message.answer(
            f"📏 Masofa avtomatik hisoblandi: ~{km:.1f} km\nTarifni tanlang:",
            reply_markup=kb.tariffs_inline_kb(region_id, km, prefix="dtariff"),
        )
        await call.answer()
        return
    await state.set_state(DispatcherAddOrder.km)
    await call.message.answer("Taxminiy masofani km da kiriting (masalan: 5 yoki 5.5):")
    await call.answer()


@router.message(DispatcherAddOrder.km)
async def add_order_km(message: Message, state: FSMContext):
    try:
        km = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Iltimos, faqat son kiriting, masalan: 5 yoki 5.5")
        return
    await state.update_data(km=km)
    data = await state.get_data()
    await state.set_state(DispatcherAddOrder.tariff)
    await message.answer("Tarifni tanlang:", reply_markup=kb.tariffs_inline_kb(data["region_id"], km, prefix="dtariff"))


@router.callback_query(DispatcherAddOrder.tariff, F.data.startswith("dtariff:"))
async def add_order_tariff(call: CallbackQuery, state: FSMContext):
    tariff_id = call.data.split(":")[1]
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(DispatcherAddOrder.payment)
    await call.message.answer("To'lov turini tanlang:", reply_markup=kb.payment_inline_kb(prefix="dpay"))
    await call.answer()


@router.callback_query(DispatcherAddOrder.payment, F.data.startswith("dpay:"))
async def add_order_payment(call: CallbackQuery, state: FSMContext, bot):
    payment = call.data.split(":")[1]
    data = await state.get_data()
    await state.clear()
    region = db.get_region(data["region_id"])
    tariff = db.get_tariff(data["tariff_id"])
    km = data["km"]
    price = pricing.fare(region, tariff, km)
    # Mijozni doimiy (telefon raqami bo'yicha barqaror) ID bilan saqlaymiz — shu raqam keyingi
    # safar qo'ng'iroq qilsa, ismi bazadan avtomatik topiladi. Bu ID dispetcherning shaxsiy
    # Telegram ID'sidan mustaqil, shuning uchun dispetcher o'zi mijoz sifatida taksi chaqirsa ham
    # bu buyurtmalar bilan hech qanday to'qnashuv bo'lmaydi.
    client_id = db.upsert_phone_client(data["name"], data["phone"])
    order_id = db.create_order(
        client_id=client_id,
        region_id=data["region_id"],
        tariff_id=data["tariff_id"],
        payment_method=payment,
        pickup_text=data["pickup_text"],
        pickup_lat=data.get("pickup_lat"),
        pickup_lng=data.get("pickup_lng"),
        dest_text=data.get("dest_text"),
        dest_lat=data.get("dest_lat"),
        dest_lng=data.get("dest_lng"),
        est_km=km,
        price=price,
        order_type="phone",
        phone_client_name=data["name"],
        phone_client_phone=data["phone"],
        created_by=call.from_user.id,
    )
    await call.message.answer(
        f"✅ Buyurtma #{order_id} qo'shildi ({data['name']}, {data['phone']}) — {money(price)} so'm.\n"
        f"Haydovchilarga yuborilmoqda...",
        reply_markup=kb.dispatcher_menu_kb(),
    )
    await call.answer()
    # Dispetcher o'zi qo'lda kiritgani uchun qo'shimcha tasdiqlash shart emas — darhol yuboriladi.
    # Eslatma: agar pickup joylashuv sifatida yuborilgan bo'lsa, masofaga qarab bosqichma-bosqich
    # va ovozli signal bilan ketadi (xuddi mijoz ilovadan buyurtma bergandagidek); aks holda
    # (faqat matn bilan manzil kiritilgan bo'lsa) barcha mos haydovchilarga birdaniga, ovozsiz boradi.
    asyncio.create_task(dispatch.dispatch_order(bot, order_id))
