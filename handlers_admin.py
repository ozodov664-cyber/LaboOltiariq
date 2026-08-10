import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandObject

import db
import keyboards as kb
from states import AdminLogin, AdminAddRegion, AdminAddDriver, AdminEditTariff, AdminChangePassword, AdminBroadcast

router = Router(name="admin")

_admins = set()  # in-memory session of telegram ids currently authed as admin this run


def money(n):
    return f"{round(n):,}".replace(",", " ")


def is_admin(user_id):
    if user_id in _admins:
        return True
    # Xotiradagi sessiya bot qayta ishga tushganda (masalan Railway'da har deployda) tozalanadi —
    # lekin bazada avval tasdiqlangan admin bo'lsa, parolni qayta so'ramasdan tanib olamiz.
    if any(a["user_id"] == user_id for a in db.list_admin_ids("admin")):
        _admins.add(user_id)
        return True
    return False


@router.message(Command("admin"))
async def admin_login(message: Message, state: FSMContext, command: CommandObject):
    if command.args:
        await try_password(message, command.args.strip())
    else:
        await state.set_state(AdminLogin.waiting_password)
        await message.answer("Admin parolini kiriting:")


@router.message(AdminLogin.waiting_password)
async def admin_password_input(message: Message, state: FSMContext):
    await state.clear()
    await try_password(message, message.text.strip())


async def try_password(message: Message, password: str):
    if password != db.get_setting("admin_password"):
        await message.answer("Parol noto'g'ri.")
        return
    _admins.add(message.from_user.id)
    db.add_admin_id(message.from_user.id, "admin")  # SOS/xabar yuborish uchun doimiy saqlanadi
    await message.answer("Admin panelga xush kelibsiz.", reply_markup=kb.admin_menu_kb())


@router.message(F.text == "📊 Statistika")
async def stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    s = db.revenue_stats()
    drivers = db.list_drivers()
    active_drivers = len([d for d in drivers if not d["blocked"]])
    await message.answer(
        f"📊 Statistika\n\n💰 Jami tushum: {money(s['revenue'])} so'm\n🚗 Safarlar: {s['trips']}\n"
        f"👥 Faol haydovchilar: {active_drivers}/{len(drivers)}"
    )


# ---------------- regions ----------------
@router.message(F.text == "🗺 Hududlar")
async def regions_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    regions = db.list_regions()
    if regions:
        lines = [f"• {r['name']}: minimalka {money(r['minimalka'])}, "
                 f"kutish/min {money(r['wait_per_min'])} so'm" for r in regions]
        await message.answer("🗺 Hududlar:\n" + "\n".join(lines), reply_markup=kb.admin_regions_kb())
        await message.answer("(yuqoridagi tugmani bosib hududni o'chirishingiz mumkin)")
    else:
        await message.answer("Hududlar yo'q.")
    await message.answer("Yangi hudud qo'shish uchun /addregion buyrug'ini yuboring.")


@router.message(Command("addregion"))
async def add_region_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddRegion.name)
    await message.answer("Yangi hudud nomi:")


@router.message(AdminAddRegion.name)
async def add_region_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminAddRegion.minimalka)
    await message.answer("Minimalka summasi (so'm):")


@router.message(AdminAddRegion.minimalka)
async def add_region_min(message: Message, state: FSMContext):
    try:
        v = int(message.text.strip())
    except ValueError:
        await message.answer("Raqam kiriting.")
        return
    await state.update_data(minimalka=v)
    await state.set_state(AdminAddRegion.wait_per_min)
    await message.answer("Kutish narxi (so'm / 1 daqiqa):")


@router.message(AdminAddRegion.wait_per_min)
async def add_region_wait(message: Message, state: FSMContext):
    try:
        v = int(message.text.strip())
    except ValueError:
        await message.answer("Raqam kiriting.")
        return
    data = await state.get_data()
    # Eslatma: hududda alohida "1 km narxi" endi yo'q (0 sifatida saqlanadi) — narx endi
    # tanlangan mashina+kuzov turiga (tariff.km_price, "🚐 Mashina narxlari" bo'limi) bog'liq.
    db.add_region(data["name"], data["minimalka"], 0, v)
    await state.clear()
    await message.answer(f"✅ Hudud qo'shildi: {data['name']}", reply_markup=kb.admin_menu_kb())


@router.callback_query(F.data.startswith("delregion:"))
async def del_region(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    region_id = int(call.data.split(":")[1])
    db.delete_region(region_id)
    await call.message.edit_text(call.message.text + "\n\n🗑 O'chirildi.")
    await call.answer()


# ---------------- drivers ----------------
@router.message(F.text == "🚗 Haydovchilar")
async def drivers_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    drivers = db.list_drivers()
    if not drivers:
        await message.answer("Haydovchilar yo'q.")
    else:
        await message.answer("Haydovchini tanlang:", reply_markup=kb.admin_drivers_kb())
    await message.answer(
        "Yangi haydovchi qo'shish uchun /adddriver buyrug'ini yuboring.\n"
        "(Haydovchining Telegram ID raqami kerak bo'ladi — buni haydovchi @userinfobot orqali biladi)"
    )


@router.message(Command("adddriver"))
async def add_driver_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddDriver.forward_contact)
    await message.answer(
        "Ma'lumotlarni shu formatda yuboring:\n<code>telegram_id, Ism Familiya, +998901234567</code>",
        parse_mode="HTML",
    )


@router.message(AdminAddDriver.forward_contact)
async def add_driver_info(message: Message, state: FSMContext):
    parts = [p.strip() for p in message.text.split(",")]
    if len(parts) != 3 or not parts[0].isdigit():
        await message.answer("Format xato. Qayta urinib ko'ring: telegram_id, Ism Familiya, +998901234567")
        return
    await state.update_data(driver_id=int(parts[0]), name=parts[1], phone=parts[2])
    await state.set_state(AdminAddDriver.tariff)
    rows = [[InlineKeyboardButton(text=t["name"], callback_data=f"newdrvtariff:{t['id']}")] for t in db.list_tariffs()]
    await message.answer("Tarifni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(AdminAddDriver.tariff, F.data.startswith("newdrvtariff:"))
async def add_driver_tariff(call: CallbackQuery, state: FSMContext):
    tariff_id = call.data.split(":")[1]
    await state.update_data(tariff=tariff_id)
    await state.set_state(AdminAddDriver.password)
    pw = db.gen_driver_password()
    await state.update_data(suggested_pass=pw)
    await call.message.answer(f"Parolni kiriting, yoki avtomatik parol uchun /auto yuboring (taklif: {pw}):")
    await call.answer()


@router.message(AdminAddDriver.password)
async def add_driver_password(message: Message, state: FSMContext):
    data = await state.get_data()
    password = data["suggested_pass"] if message.text.strip() == "/auto" else message.text.strip()
    db.create_driver(data["driver_id"], data["tariff"], password, name=data["name"], phone=data["phone"])
    await state.clear()
    await message.answer(
        f"✅ Haydovchi qo'shildi!\n👤 {data['name']}\n🔑 Parol: <code>{password}</code>\n\n"
        f"Haydovchi botga /driver buyrug'i bilan kirib, shu parolni yuboradi.",
        parse_mode="HTML",
        reply_markup=kb.admin_menu_kb(),
    )
    await message.answer(
        "⚠️ Bu haydovchi hozircha onlayn bo'la olmaydi — avval boshlang'ich to'lovni belgilang:",
        reply_markup=kb.sub_period_kb(data["driver_id"]),
    )


@router.callback_query(F.data.startswith("drvinfo:"))
async def driver_info(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    driver_id = int(call.data.split(":")[1])
    d = db.get_driver(driver_id)
    if not d:
        await call.answer("Topilmadi", show_alert=True)
        return
    now = int(time.time())
    if d.get("sub_until") and d["sub_until"] > now:
        sub_line = f"💳 Obuna: ✅ {db.fmt_dt(d['sub_until'])} gacha"
    else:
        sub_line = "💳 Obuna: ❌ to'lanmagan / muddati tugagan"
    tariff = db.get_tariff(d["tariff"])
    tariff_label = tariff["name"] if tariff else d["tariff"]
    text = (f"👤 {d['name']}\n📞 {d['phone']}\n🚗 Mashina: {tariff_label}\n⭐ {d['rating']:.1f} "
            f"({d['rating_count']} baho)\n🔑 Parol: {d['pass']}\n{sub_line}\n"
            f"Holat: {'🔒 bloklangan' if d['blocked'] else ('🟢 bo\u2019sh' if d['status']=='available' else '🟡 band')}")
    await call.message.answer(text, reply_markup=kb.driver_actions_kb(driver_id, d["blocked"]))
    await call.answer()


@router.callback_query(F.data.startswith("subpay:"))
async def sub_pay(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    _, driver_id, days = call.data.split(":")
    driver_id, days = int(driver_id), int(days)
    new_until = db.extend_driver_subscription(driver_id, days)
    d = db.get_driver(driver_id)
    await call.message.answer(
        f"✅ {d['name']} uchun to'lov qayd etildi.\nObuna muddati: {db.fmt_dt(new_until)} gacha"
    )
    await call.answer("To'lov belgilandi")


# ---------------- driver locations (Admin haydovchi qayerdaligini ko'rishi) ----------------
@router.message(F.text == "📍 Xaydovchilar joylashuvi")
async def driver_locations(message: Message, bot):
    if not is_admin(message.from_user.id):
        return
    drivers = db.list_drivers_with_location()
    if not drivers:
        await message.answer(
            "Hozircha hech bir haydovchi joylashuvini yubormagan.\n"
            "Haydovchi o'z menyusidagi '📍 Lokatsiyani yangilash' tugmasini bosishi kerak."
        )
        return
    now = int(time.time())
    shown = 0
    for d in drivers:
        age_min = (now - (d.get("loc_updated_at") or now)) // 60
        status = "🟢 bo'sh" if d["status"] == "available" else ("🟡 band" if d["status"] == "busy" else "⚪ oflayn")
        tariff = db.get_tariff(d["tariff"])
        tariff_label = tariff["name"] if tariff else d["tariff"]
        try:
            await bot.send_venue(
                message.chat.id, d["lat"], d["lng"],
                title=f"{d['name']} · {status}",
                address=f"Mashina: {tariff_label} · {age_min} daqiqa oldin yangilangan",
            )
            shown += 1
        except Exception:
            pass
    if shown == 0:
        await message.answer("Joylashuvlarni ko'rsatib bo'lmadi.")


# ---------------- subscriptions overview ----------------
@router.message(F.text == "💳 Obunalar")
async def subs_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    drivers = db.list_drivers()
    if not drivers:
        await message.answer("Haydovchilar yo'q.")
        return
    now = int(time.time())
    lines = []
    for d in drivers:
        if d.get("sub_until") and d["sub_until"] > now:
            days_left = (d["sub_until"] - now) // 86400
            lines.append(f"✅ {d['name']} — {days_left} kun qoldi ({db.fmt_dt(d['sub_until'])})")
        else:
            lines.append(f"❌ {d['name']} — to'lanmagan")
    week_price = db.get_setting("sub_price_week") or "0"
    month_price = db.get_setting("sub_price_month") or "0"
    await message.answer(
        "💳 Obunalar holati:\n" + "\n".join(lines) +
        f"\n\nNarxlar: 1 hafta — {money(int(week_price))} so'm, 1 oy — {money(int(month_price))} so'm "
        "(/narxobuna orqali o'zgartiring)\n\n"
        "To'lovni belgilash uchun '🚗 Haydovchilar' bo'limidan haydovchini tanlang → to'lov tugmasi."
    )


@router.message(Command("narxobuna"))
async def set_sub_price(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    try:
        week, month = command.args.split()
        db.set_setting("sub_price_week", str(int(week)))
        db.set_setting("sub_price_month", str(int(month)))
        await message.answer("✅ Obuna narxlari yangilandi.")
    except Exception:
        w = db.get_setting("sub_price_week") or "0"
        m = db.get_setting("sub_price_month") or "0"
        await message.answer(
            f"Foydalanish: /narxobuna <hafta_narxi> <oy_narxi>\nJoriy: hafta {money(int(w))}, oy {money(int(m))} so'm"
        )


# ---------------- broadcast (hamma haydovchiga xabar) ----------------
@router.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminBroadcast.waiting_text)
    await message.answer("Barcha haydovchilarga yuboriladigan xabar matnini kiriting:")


@router.message(AdminBroadcast.waiting_text)
async def broadcast_send(message: Message, state: FSMContext, bot):
    await state.clear()
    text = message.text
    drivers = db.list_drivers()
    sent = 0
    for d in drivers:
        try:
            await bot.send_message(d["id"], f"📢 <b>Admin xabari:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Xabar {sent}/{len(drivers)} haydovchiga yetkazildi.", reply_markup=kb.admin_menu_kb())


@router.callback_query(F.data.startswith("drvtoggle:"))
async def driver_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    driver_id = int(call.data.split(":")[1])
    d = db.get_driver(driver_id)
    db.set_driver_blocked(driver_id, not d["blocked"])
    await call.message.edit_text(call.message.text + ("\n\n🔒 Bloklandi." if not d["blocked"] else "\n\n✅ Blokdan chiqarildi."))
    await call.answer()


@router.callback_query(F.data.startswith("drvpass:"))
async def driver_new_pass(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    driver_id = int(call.data.split(":")[1])
    new_pass = db.gen_driver_password()
    db.set_driver_password(driver_id, new_pass)
    await call.message.answer(f"🔑 Yangi parol: <code>{new_pass}</code>", parse_mode="HTML")
    await call.answer("Parol yangilandi")


# ---------------- mashina + kuzov narxlari (avvalgi "tariflar") ----------------
@router.message(F.text == "🚐 Mashina narxlari")
async def tariffs_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    tariffs = db.list_tariffs()
    listing = "\n".join(f"• {t['name']}: {money(t['km_price'])} so'm/km" for t in tariffs)
    await message.answer(
        f"🚐 Mashina turlari va 1 km narxi:\n{listing}\n\n"
        f"Narxni o'zgartirish uchun mashinani tanlang:",
        reply_markup=kb.admin_tariffs_kb(),
    )


@router.callback_query(F.data.startswith("edittariff:"))
async def edit_tariff_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    tariff_id = call.data.split(":")[1]
    tariff = db.get_tariff(tariff_id)
    if not tariff:
        await call.answer("Topilmadi", show_alert=True)
        return
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(AdminEditTariff.waiting_price)
    await call.message.answer(
        f"{tariff['name']} uchun yangi 1 km narxini kiriting (so'm), hozirgi: {money(tariff['km_price'])} so'm:"
    )
    await call.answer()


@router.message(AdminEditTariff.waiting_price)
async def edit_tariff_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("Iltimos, faqat son kiriting, masalan: 1000")
        return
    data = await state.get_data()
    db.set_tariff_price(data["tariff_id"], price)
    await state.clear()
    tariff = db.get_tariff(data["tariff_id"])
    await message.answer(
        f"✅ {tariff['name']} uchun 1 km narxi {money(price)} so'mga o'zgartirildi.",
        reply_markup=kb.admin_menu_kb(),
    )


@router.message(Command("tariff"))
async def set_tariff(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    # usage: /tariff kia_bort 1000
    try:
        tid, price = command.args.split()
        db.set_tariff_price(tid, int(price))
        tariff = db.get_tariff(tid)
        name = tariff["name"] if tariff else tid
        await message.answer(f"✅ {name} uchun 1 km narxi {money(int(price))} so'mga o'zgartirildi.")
    except Exception:
        tariffs = db.list_tariffs()
        listing = "\n".join(f"• {t['id']} ({t['name']}): {money(t['km_price'])} so'm/km" for t in tariffs)
        await message.answer(f"Foydalanish: /tariff <id> <1km narxi>\n\nJoriy narxlar:\n{listing}")


# ---------------- passwords ----------------
@router.message(F.text == "🔐 Parollar")
async def passwords_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        f"Dispetcher paroli: <code>{db.get_setting('dispatcher_password')}</code>\n"
        f"Admin paroli: <code>{db.get_setting('admin_password')}</code>\n\n"
        f"O'zgartirish: /setpass dispetcher YangiParol\n/setpass admin YangiParol",
        parse_mode="HTML",
    )


@router.message(Command("setpass"))
async def set_pass(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    try:
        which, value = command.args.split(maxsplit=1)
        key = "dispatcher_password" if which.lower().startswith("disp") else "admin_password"
        db.set_setting(key, value.strip())
        await message.answer("✅ Parol yangilandi.")
    except Exception:
        await message.answer("Foydalanish: /setpass dispetcher YangiParol")
