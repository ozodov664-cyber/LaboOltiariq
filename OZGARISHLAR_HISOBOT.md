# Hisobot — Buyurtma qabul qilish: "muddat o'tgan" / "oldin qabul qilingan" tizimi

## ✅ Bu safar nima qilindi

Avvalgi versiyada allaqachon **atom darajasida himoyalangan** edi: bitta buyurtmani ikkita
haydovchi bir vaqtda bossa ham, faqat bittasiga tegishli bo'lardi (`db.accept_order`, SQLite
`UPDATE ... WHERE status='new'` — bazaning o'zi hakamlik qiladi). Lekin ikkinchi haydovchiga
har doim bitta xil xabar ko'rsatilardi: **"allaqachon boshqa haydovchiga tegishli"** — buyurtma
nega qabul qilinmayotgani (kech qolindimi, bekor qilindimi, umuman muddati o'tganmi) aniq
emas edi. Aynan shu — siz so'ragan qism — endi to'liq qilindi:

### 1. Buyurtmaning "muddati" endi haqiqiy tushuncha (`db.py`)
- `ORDER_TTL_SECONDS = 20 daqiqa` — agar buyurtma 20 daqiqa ichida **hech kim** tomonidan
  qabul qilinmasa, u avtomatik **"muddati tugagan"** deb belgilanadi (`status='cancelled'`,
  `cancel_reason='expired'`).
- `db.accept_order()` endi buni tekshiradi: eskirgan buyurtmani birov keyinroq "✅ Qabul
  qilish" bossa ham — endi qabul qila olmaydi.
- Yangi `db.order_fail_reason(order_id)` funksiyasi — qabul qilish muvaffaqiyatsiz bo'lganda
  ANIQ sababni qaytaradi: `expired` (muddati tugagan) | `cancelled` (mijoz/dispetcher bekor
  qilgan) | `taken` (boshqa haydovchi OLDIN qabul qilib ulgurgan) | `not_found`.
- Yangi `db.expire_stale_orders()` — barcha eskirgan buyurtmalarni bir yo'la tozalaydi (fon
  vazifasi uchun, pastga qarang).

### 2. Haydovchiga endi ANIQ xabar ko'rsatiladi (`handlers_driver.py`)
"✅ Qabul qilish" tugmasi bosilganda, agar muvaffaqiyatsiz bo'lsa:
- **Muddati tugagan** → "⏰ Bu buyurtmaning muddati tugagan — uzoq vaqt hech kim javob
  bermagani uchun avtomatik bekor bo'lgan."
- **Oldin qabul qilingan** → "❌ Bu buyurtma oldin boshqa haydovchi tomonidan qabul qilingan."
- **Bekor qilingan** (mijoz/dispetcher) → "🚫 Bu buyurtma mijoz (yoki dispetcher) tomonidan
  bekor qilingan."
- **Topilmadi** → "❌ Bu buyurtma topilmadi."

Har birida mos qisqa alert (`show_alert=True`) ham chiqadi, shuning uchun haydovchi darhol
tushunadi — nega bosilmayapti.

### 3. Fon rejimidagi avtomatik tozalash (`dispatch.py` + `main.py`)
Yangi `dispatch.expire_orders_loop(bot)` — bot ishga tushgandan boshlab **har daqiqada** ishga
tushadi, eskirgan (`ORDER_TTL_SECONDS` dan ko'p kutgan) buyurtmalarni topib, avtomatik
"muddati tugagan" deb belgilaydi VA **mijozga o'zi xabar beradi**:
> "⏰ Buyurtmangiz muddati tugadi. Afsuski, uzoq vaqt hech qanday haydovchi javob bermadi.
> Iltimos, qayta urinib ko'ring."

(Telefon orqali dispetcher kiritgan buyurtmalarga bu xabar yuborilmaydi — chunki u yerda
mijoz bot ichida emas.) Bu `main.py`da `asyncio.create_task(...)` orqali ulandi — botni qayta
ishga tushirish shart emas, `python3 main.py` bilan avtomatik ishlaydi.

### 4. Mijoz tarixida ham ko'rinadi (`handlers_client.py`)
"📜 Tarix" bo'limida endi muddati tugagan buyurtmalar oddiy "✖️ Bekor qilingan" emas, balki
aniq **"⏰ Muddati tugagan"** deb ko'rsatiladi.

### 5. Tekshirildi
- Barcha `.py` fayllar `python3 -m py_compile` bilan sintaksis xatosiz.
- Real SQLite bazada avtomatlashtirilgan test o'tkazildi: (a) ikki haydovchi bir vaqtda
  bosganda faqat bittasi oladi, ikkinchisiga `"taken"` sababi qaytadi; (b) eskirgan buyurtmani
  qabul qilishga urinilganda `"expired"` qaytadi va real holatda ham bazada `cancelled` +
  `cancel_reason='expired'` bo'lib qoladi; (c) mijoz bekor qilgan buyurtmaga `"cancelled"`
  qaytadi; (d) fon tozalash funksiyasi eskirgan buyurtmalarni to'g'ri topib, belgilab beradi.
  Hammasi kutilganidek ishladi.

## 📌 Bu — umumiy ishning bir qismi (siz "30%" desangiz, shu qism)

README'da yozilganidek, quyidagilar **avvaldan** ishlagan (bu safar tegilmadi, faqat
tasdiqlandi/testdan o'tkazildi):
- Mijoz `/start` orqali ism+telefon bilan ro'yxatdan o'tadi, joylashuv yuboradi
- Buyurtma avval eng yaqin haydovchiga, keyin bosqichma-bosqich kengroq doiraga ketadi
  (masofaga qarab turli ovozli signal bilan)
- Buyurtmani bitta haydovchi qabul qilsa, ikkinchisi qabul qila olmaydi (baza darajasida)
- Obuna (to'lov) muddati tugagan haydovchi onlayn bo'la olmaydi / buyurtma ololmaydi
- Haydovchi joylashuvini (jonli) yuboradi, admin xaritada ko'radi
- Dispetcher tasdiqlash bosqichi, "➕ Zakaz qo'shish" (telefon orqali qo'lda kiritish)

## 📋 Keyingi navbatdagi qadamlar (tavsiya — 70% qolgan qismdan)

1. **TTL vaqtini o'zingizga moslash** — hozir 20 daqiqa (`db.ORDER_TTL_SECONDS`); kerak
   bo'lsa bittagina raqamni o'zgartirish orqali qisqartirish/uzaytirish mumkin.
2. **Boshqa haydovchilarga ham "band bo'ldi" xabari** — hozir faqat bosgan haydovchiga darhol
   javob boradi; boshqa haydovchilarga yuborilgan eski xabarlarni ham avtomatik
   "❌ band bo'ldi" deb tahrirlash mumkin (buning uchun har bir yuborilgan xabar ID'sini
   bazada saqlash kerak bo'ladi — kichik, lekin alohida ish).
3. **Qolgan menyularni "premium" qilish** — buyurtma jarayoni, admin/dispetcher ichki
   bo'limlari hali oddiy matn ko'rinishida (README'dagi eski tavsiya, hali dolzarb).
4. **Real Telegram'da to'liq sinov** — bu yerda faqat kod/baza darajasida (avtomatlashtirilgan
   test bilan) tekshirildi; `BOT_TOKEN` bilan haqiqiy botda to'liq oqimni qayta sinab ko'rish
   tavsiya etiladi.
5. README'dagi "Nima ishlamaydi" ro'yxati (haqiqiy yo'l masofasi/karta to'lovi/jonli xarita)
   hali ham amal qiladi — bular alohida biznes qarorlari, avvalgi hisobotda batafsil
   tushuntirilgan.
