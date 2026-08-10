from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
import db


def contact_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def location_kb(skip_text=None):
    rows = [[KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)]]
    if skip_text:
        rows.append([KeyboardButton(text=skip_text)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


def remove_kb():
    return ReplyKeyboardRemove()


def client_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚕 Taksi chaqirish")],
            [KeyboardButton(text="📋 Buyurtmalarim"), KeyboardButton(text="👤 Profil")],
            [KeyboardButton(text="📜 Tarix"), KeyboardButton(text="🆘 Yordam")],
        ],
        resize_keyboard=True,
    )


def driver_menu_kb(online: bool):
    toggle = "🔴 Oflayn bo'lish" if online else "🟢 Onlayn bo'lish"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=toggle)],
            [KeyboardButton(text="📍 Lokatsiyani yangilash", request_location=True)],
            [KeyboardButton(text="🛑 Yo'lda mijoz oldim"), KeyboardButton(text="🚗 Joriy safar")],
            [KeyboardButton(text="📊 Statistikam"), KeyboardButton(text="💳 Obunam")],
        ],
        resize_keyboard=True,
    )


def dispatcher_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Zakaz qo'shish")],
            [KeyboardButton(text="📋 Faol buyurtmalar")],
            [KeyboardButton(text="🚦 Haydovchilar holati")],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="🗺 Hududlar"), KeyboardButton(text="🚗 Haydovchilar")],
            [KeyboardButton(text="🚐 Mashina narxlari"), KeyboardButton(text="📍 Xaydovchilar joylashuvi")],
            [KeyboardButton(text="💳 Obunalar"), KeyboardButton(text="📢 Xabar yuborish")],
            [KeyboardButton(text="🔐 Parollar")],
        ],
        resize_keyboard=True,
    )


def regions_inline_kb(prefix="region"):
    rows = []
    for r in db.list_regions():
        rows.append([InlineKeyboardButton(text=r["name"], callback_data=f"{prefix}:{r['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tariffs_inline_kb(region_id, km, prefix="tariff"):
    region = db.get_region(region_id)
    rows = []
    import pricing
    for t in db.list_tariffs():
        price = pricing.fare(region, t, km)
        rows.append([InlineKeyboardButton(
            text=f"{t['name']} · {price:,} so'm".replace(",", " "),
            callback_data=f"{prefix}:{t['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_tariffs_kb():
    rows = []
    for t in db.list_tariffs():
        rows.append([InlineKeyboardButton(
            text=f"{t['name']} — {t['km_price']:,} so'm/km".replace(",", " "),
            callback_data=f"edittariff:{t['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_inline_kb(prefix="pay"):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💵 Naqd", callback_data=f"{prefix}:naqd"),
        InlineKeyboardButton(text="💳 Karta", callback_data=f"{prefix}:karta"),
    ]])


def confirm_order_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Buyurtmani tasdiqlash", callback_data="confirm_order"),
        InlineKeyboardButton(text="✖️ Bekor qilish", callback_data="cancel_order_draft"),
    ]])


def accept_order_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept:{order_id}")
    ]])


def trip_controls_kb(order_id, stage, waiting=False, auto=False):
    if stage == "accepted":
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🚗 Safarni boshlash", callback_data=f"start:{order_id}")
        ]])
    if stage == "in_progress":
        wait_btn = "⏹ Kutishni to'xtatish" if waiting else "⏳ Kutishni yoqish"
        wait_cb = f"waitoff:{order_id}" if waiting else f"waiton:{order_id}"
        rows = []
        if not waiting:
            rows.append([InlineKeyboardButton(text=wait_btn, callback_data=wait_cb),
                         InlineKeyboardButton(text="🏁 Yakunlash", callback_data=f"finish:{order_id}")])
        else:
            rows.append([InlineKeyboardButton(text=wait_btn, callback_data=wait_cb)])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    return None


def status_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖️ Buyurtmani bekor qilish", callback_data=f"clientcancel:{order_id}")
    ]])


def rating_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐" * n, callback_data=f"rate:{order_id}:{n}") for n in range(1, 6)
    ]])


def dispatcher_order_kb(order_id, drivers):
    rows = [[InlineKeyboardButton(text=f"👤 {d['name']}", callback_data=f"reassign:{order_id}:{d['id']}")]
            for d in drivers[:6]]
    rows.append([InlineKeyboardButton(text="✖️ Bekor qilish", callback_data=f"dcancel:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dispatcher_new_order_kb(order_id, drivers):
    """Yangi (hali tasdiqlanmagan) buyurtma uchun: yaqin haydovchilarga avtomatik yuborish
    (masofa bo'yicha, ovozli signal bilan) YOKI aniq bitta haydovchini tanlab tayinlash YOKI bekor qilish."""
    rows = [[InlineKeyboardButton(text="✅ Yaqin haydovchilarga yuborish", callback_data=f"dispatch_confirm:{order_id}")]]
    for d in drivers[:6]:
        rows.append([InlineKeyboardButton(text=f"👤 {d['name']} ga tayinlash", callback_data=f"reassign:{order_id}:{d['id']}")])
    rows.append([InlineKeyboardButton(text="✖️ Bekor qilish", callback_data=f"dcancel:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dcancel_only_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖️ Bekor qilish", callback_data=f"dcancel:{order_id}")
    ]])


def admin_drivers_kb():
    rows = []
    for d in db.list_drivers():
        t = db.get_tariff(d["tariff"])
        tariff_label = t["name"] if t else d["tariff"]
        label = f"{'🔒' if d['blocked'] else '🚗'} {d['name']} ({tariff_label})"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"drvinfo:{d['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def driver_actions_kb(driver_user_id, blocked):
    toggle = "✅ Blokdan chiqarish" if blocked else "🚫 Bloklash"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle, callback_data=f"drvtoggle:{driver_user_id}")],
        [InlineKeyboardButton(text="🔑 Parolni yangilash", callback_data=f"drvpass:{driver_user_id}")],
        [InlineKeyboardButton(text="💳 1 hafta to'lov", callback_data=f"subpay:{driver_user_id}:7"),
         InlineKeyboardButton(text="💳 1 oy to'lov", callback_data=f"subpay:{driver_user_id}:30")],
    ])


def sub_period_kb(driver_user_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="1 hafta", callback_data=f"subpay:{driver_user_id}:7"),
        InlineKeyboardButton(text="1 oy", callback_data=f"subpay:{driver_user_id}:30"),
    ]])


def admin_regions_kb():
    rows = []
    for r in db.list_regions():
        rows.append([InlineKeyboardButton(
            text=f"🗑 {r['name']} — minimalka {r['minimalka']:,} so'm".replace(",", " "),
            callback_data=f"delregion:{r['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)
