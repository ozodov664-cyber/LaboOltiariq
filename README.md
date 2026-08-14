# LaboOltiariq — Telegram taksi boti (to'liq menyu asosida)

## 🆕 Mini App (Web App) olib tashlandi

Bot endi **to'liq oddiy Telegram bot menyulari** orqali ishlaydi — alohida Web App/Mini App
yo'q. Barcha rollar (mijoz, haydovchi, dispetcher, admin) ro'yxatdan o'tish, buyurtma berish
va boshqarishni **bot ichidagi tugmalar (reply/inline keyboard)** orqali amalga oshiradi,
xuddi mini app qo'shilishidan oldingi kabi.

O'chirilgan fayllar: `web.py`, `webauth.py`, `webcommon.py`, `api_client.py`, `api_driver.py`,
`api_dispatcher.py`, `api_admin.py`, va butun `webapp/` papkasi (frontend: `index.html`,
`app.js`, `style.css`). Bot endi hech qanday HTTP port ochmaydi — faqat Telegram bilan
polling orqali gaplashadi, shuning uchun `Procfile` yana `worker:` turiga qaytarildi (avval
mini app uchun `web:` qilingan edi).

**Ro'yxatdan o'tish va barcha menyular endi "premium" ko'rinishda**: sarlavhalar, chiziqlar
va qalin matn (HTML formatlash) bilan chiroyliroq bezatildi — mijoz, haydovchi, dispetcher
va admin uchun kirish/xush kelibsiz ekranlari yangilandi.

> **Eslatma:** haydovchi joylashuvini doimiy (fon rejimida) uzatish endi faqat Telegram
> "Live Location" funksiyasi orqali bo'ladi (avval buni mini app ham qila olardi, ochiq
> turgan vaqtda) — bot buni allaqachon qabul qiladi (`📍 Lokatsiyani yangilash` tugmasi).


## Eski yangilanishlar

- **Dispetcher tasdiqlash bosqichi**: endi mijoz buyurtma bergach, u avtomatik ravishda
  haydovchilarga ketmaydi — avval barcha ro'yxatdan o'tgan dispetcherlarga (`/dispetcher`
  orqali kirgan) push xabar sifatida boradi. Dispetcher \"✅ Yaqin haydovchilarga yuborish\"
  tugmasini bossagina, zayavka 15 km radiusdagi mos haydovchilarga (avval eng yaqiniga,
  keyin bosqichma-bosqich) ketadi. Agar hech qanday dispetcher hali tizimga kirmagan bo'lsa
  (masalan yangi o'rnatilgan bot), buyurtma osilib qolmasligi uchun eski tartibda — to'g'ridan
  to'g'ri haydovchilarga — ketadi.
- **Masofaga qarab ovozli signal**: haydovchiga zayavka matn bilan birga qisqa ovozli xabar
  (voice) sifatida ham boradi, ohanglar yoqimli \"zang\" (chime) tipida — asabga tegadigan
  qattiq bip emas. Mijozgacha 10 km gacha bo'lsa tezroq ikkita ding, 10–15 km oralig'ida bitta
  xotirjam ding, 15–40 km oralig'ida eng past va uzun, yumshoq ohang. Har bir xabarda \"Sizgacha:
  ~X km\" ko'rinishida aniq masofa ham yoziladi. 40 km dan uzoqdagi haydovchilarga umuman
  yuborilmaydi (agar radius ichida hech kim topilmasa — buyurtma osilib qolmasin deb, baribir
  hammaga ovozsiz yuboriladi). Ovoz fayllari `assets/chime_near.ogg`, `assets/chime_medium.ogg`,
  `assets/chime_far.ogg` — statik, oldindan tayyorlangan, serverda ffmpeg shart emas.
- **Dispetcher: \"➕ Zakaz qo'shish\"** — telefon orqali qo'ng'iroq qilib buyurtma bergan
  mijozlar uchun, dispetcher panelida qo'lda buyurtma kiritish (ism, telefon, manzil, hudud,
  taxminiy km, tarif, to'lov turi). Bunday buyurtmalar avtomatik ravishda \"phone\" turida
  belgilanadi va yaratilgach darhol (qo'shimcha tasdiqlashsiz) haydovchilarga yuboriladi —
  chunki uni allaqachon dispetcher tasdiqlab kiritgan. Manzil matn bilan kiritilgani uchun
  GPS yo'q — shu sababli bu turdagi buyurtmalarda masofaga qarab saralash/ovoz ishlamaydi
  (barcha mos haydovchilarga birdaniga, ovozsiz boradi).
- **Km'ni to'g'ri (haqiqiy yo'l bo'yicha) hisoblash**: mijoz ikkala nuqtani (qayerdan/qayerga)
  joylashuv sifatida yuborganda, endi masofa avval **OSRM** (bepul, ochiq marshrut xizmati)
  orqali haqiqiy haydash yo'li bo'yicha so'raladi; xizmat ishlamay qolsa (tarmoq, limit va h.k.)
  avtomatik to'g'ri chiziq (Haversine + tuzatish) formulasiga tushadi — mijoz har doim narx
  ko'raveradi. Batafsili `pricing.py` ichidagi izohda — jumladan, o'z OSRM serveringizni
  qanday ko'tarish yoki Google/Yandex'ga qanday o'tish mumkinligi haqida.


Bu — brauzer demosidagi mantiqni **haqiqiy, ishlaydigan Telegram botga** aylantirgan
kod. SQLite baza, aiogram 3 kutubxonasi asosida yozilgan. Kodning har bir qismi
sinovdan o'tkazilgan (buyurtma yaratish → qabul qilish → km/kutish hisoblash →
yakunlash → baholash — to'liq zanjir mahalliy testda ishladi).

## Nima ishlaydi (haqiqatan)


- Mijoz `/start` orqali ro'yxatdan o'tadi (ism + telefon, **bir marta**, keyin saqlanadi)
- Taksi chaqirish: joylashuv yuborish (yoki matn bilan manzil), hudud/tarif/to'lov tanlash
- Agar mijoz **ikkala** nuqtani (qayerdan/qayerga) joylashuv sifatida yuborsa — masofa
  **haqiqiy GPS koordinatalari** asosida avtomatik hisoblanadi (Haversine formula + 30%
  ko'cha buralish tuzatishi)
- Yangi buyurtma **avval eng yaqin haydovchiga** yuboriladi (agar mijoz va haydovchi joylashuvi
  ma'lum bo'lsa); 20 soniyada javob bo'lmasa keyingi 2 ta yaqin haydovchiga, yana 20 soniyadan
  keyin qolgan barcha mos haydovchilarga yuboriladi. Birinchi bosgan haydovchi oladi (baza
  darajasida himoyalangan — ikki kishi bir vaqtda bossa ham faqat bittasiga tegadi)
- **Obuna tizimi (foizsiz)**: har bir safardan komissiya yechilmaydi. Haydovchi haftalik yoki
  oylik to'lov qiladi (admin to'lovni tasdiqlaydi), to'lov muddati tugasa — haydovchi onlayn
  bo'la olmaydi va yangi buyurtma ololmaydi, toki admin yangi to'lovni belgilamaguncha
- **Haydovchi joylashuvi**: haydovchi lokatsiyasini yuboradi (yoki Telegram "Live Location"
  orqali uzatadi), admin panelda "📍 Xaydovchilar joylashuvi" bo'limida barcha onlayn
  haydovchilarning xaritadagi joyini (pin sifatida) ko'radi
- **Bordyurdan (yo'ldan) mijoz olish**: haydovchi ilova orqali emas, ko'chada mijoz uchratsa
  "🛑 Yo'lda mijoz oldim" tugmasi orqali hududni tanlab, taksometrni o'zi boshqaradi
  (+1 km, kutish, yakunlash — xuddi oddiy safar kabi)
- **Admin xabar yuborish**: admin "📢 Xabar yuborish" orqali yozgan matni barcha haydovchilarga
  bir zumda yetkaziladi
- **Joriy safarni tiklash**: haydovchi (yoki uning Telegram ilovasi/keshi) buyurtma tugmalarini
  yo'qotib qo'ysa, "🚗 Joriy safar" tugmasi orqali istalgan vaqt qayta chaqirib olishi mumkin —
  barcha ma'lumot serverdagi bazada saqlanadi, hech qachon yo'qolmaydi
- **Mijoz uchun qulayliklar**: buyurtmani bekor qilish (hali qabul qilinmagan/yo'lga
  chiqilmagan bosqichda), "📜 Tarix" (oxirgi buyurtmalar), "🆘 Yordam" (SOS — adminga darhol xabar)
- Haydovchi: safarni boshlash → +1 km → kutish (yoqish/o'chirish, soniya asosida
  proporsional narx) → yakunlash — hammasi real vaqtda mijozga xabar sifatida boradi
- Dispetcher: `/dispetcher <parol>` — faol buyurtmalarni ko'radi, qayta tayinlaydi, bekor qiladi,
  haydovchilar holatini (onlayn/band, obuna, oxirgi joylashuv vaqti) ko'radi
- Admin: `/admin <parol>` — hududlar/narxlar, tarif koeffitsientlari, haydovchi
  qo'shish/bloklash/parol yangilash, obuna to'lovlarini belgilash, tushum statistikasi
- Har bir rol **alohida parol** bilan himoyalangan (`/setpass` orqali admin o'zgartiradi)

## Nima ishlamaydi / o'zingiz qo'shishingiz kerak bo'ladi (halol ro'yxat)

Buni yashirmayman — quyidagilarsiz bu "to'liq Yandex" bo'la olmaydi:

1. **Haqiqiy yo'l masofasi** — hozir to'g'ri chiziq (Haversine) ishlatiladi. Aniq yo'l
   masofasi uchun Google Distance Matrix API yoki Yandex Router API kerak — bular
   pullik va o'z API kalitingizni talab qiladi.
2. **To'lov tizimi** — hozir faqat "naqd/karta" degan belgi saqlanadi, real pul
   o'tkazilmaydi. Karta to'lovini ishlatish uchun Payme yoki Click bilan **tadbirkor
   sifatida shartnoma** tuzib, ularning merchant API'sini ulashingiz kerak.
3. **Xarita ko'rinishi** — Telegram o'zi joylashuvni xarita sifatida ko'rsatadi
   (foydalanuvchi buni ilova ichida ko'radi), lekin botda "jonli harakatlanuvchi
   mashina" animatsiyasi yo'q — buning uchun haydovchi ilovasi doimiy joylashuv
   yuborib turishi va sizda buni chizadigan frontend (masalan Web App + xarita
   widget) bo'lishi kerak.
4. **Ishonchlilik/monitoring** — hozircha bitta jarayon (`python3 main.py`) sifatida
   ishlaydi. Productionda process manager (systemd/Docker), xatoliklarni kuzatish
   (Sentry) va zaxira nusxalash (SQLite faylini muntazam backup qilish) kerak bo'ladi.
5. **Ko'lam** — SQLite bitta serverda yaxshi ishlaydi (bir necha yuz faol buyurtma/kun
   darajasida). Katta shaharlarga (minglab buyurtma) chiqsangiz Postgres'ga o'tish tavsiya
   etiladi — schema deyarli bir xil qoladi, faqat `db.py` dagi ulanish qatlamini
   almashtirasiz.
6. **Haqiqiy jonli xarita** — admin panelidagi "📍 Xaydovchilar joylashuvi" har safar
   bosilganda joriy nuqtalarni ko'rsatadi (Telegram pin sifatida), lekin **avtomatik
   yangilanib turadigan, harakatlanuvchi xarita** emas — buning uchun Web App +
   xarita widget (masalan Yandex Maps JS API yoki Leaflet) va haydovchi ilovasi
   tomonidan doimiy joylashuv yuborib turish (Live Location) kerak. Bot buni
   qabul qilishga tayyor (`db.set_driver_location` chaqiriladi), frontend qismi yo'q, xolos.
7. **Ro'yxatdan o'tish holati (FSM)** hozircha xotirada (`MemoryStorage`) saqlanadi —
   ya'ni bot serveri qayta ishga tushsa, "ism kiritish" kabi tugallanmagan qadam
   qayta boshlanadi. Bu **buyurtma va safar ma'lumotlariga tegmaydi** (ular doim
   SQLite'da, hech qachon yo'qolmaydi) — faqat registratsiya/forma to'ldirish jarayoni
   uchun. Katta yuklamada buni Redis-based storage'ga almashtirish tavsiya etiladi.

Bularning hech biri "qo'shimcha kod yozish qiyin" degani emas — bular **sizning
biznes qarorlaringiz va shartnomalaringizga bog'liq** narsalar (qaysi to'lov
provayder, qaysi xarita API, qayerda hosting). Men buni sizning o'rningizga hal
qila olmayman, lekin kodni shu integratsiyalarni qo'shish oson bo'ladigan tarzda
yozdim (masalan `pricing.py` ichidagi `haversine_km` funksiyasini keyinchalik haqiqiy
Router API chaqiruviga almashtirish — bitta funksiyani o'zgartirish, xolos).

## O'rnatish

```bash
# 1) Kerakli paketni o'rnatish
pip install -r requirements.txt

# 2) @BotFather ga Telegram'da yozing, /newbot buyrug'i bilan bot yarating,
#    tokenni oling

# 3) Tokenni muhit o'zgaruvchisiga bering
export BOT_TOKEN="sizning_tokeningiz"

# 4) Ishga tushiring
python3 main.py
```

Bot ishga tushgach, `labooltiariq.db` fayli avtomatik yaratiladi (SQLite), standart
hudud/tariflar va parollar (`admin2026`, `dispetcher2026`) qo'shiladi.

**MUHIM — birinchi ishdan keyin darhol qiling:**
```
Telegramda botga: /admin admin2026
Keyin: /setpass admin YangiKuchliParol
Keyin: /setpass dispetcher YangiKuchliParol
```

## Obuna narxlarini sozlash

Standart holatda 1 hafta — 150 000 so'm, 1 oy — 500 000 so'm (faqat ma'lumot uchun,
haydovchiga ko'rsatiladi — haqiqiy pul o'tkazish bot ichida amalga oshmaydi, admin
naqd/o'zaro to'lovni qabul qilib, botda "to'lov qayd etildi" deb belgilaydi):
```
Telegramda: /narxobuna 150000 500000
```

## Haydovchiga to'lovni belgilash

Admin panelda "🚗 Haydovchilar" → kerakli haydovchini tanlang → "💳 1 hafta to'lov" yoki
"💳 1 oy to'lov" tugmasini bosing. Shundan keyingina haydovchi onlayn bo'la oladi.
Yangi qo'shilgan haydovchi ham darhol to'lov belgilanmaguncha onlayn bo'la olmaydi.

## Haydovchi qo'shish

Admin panelda `/adddriver` buyrug'ini yuboring, so'ralganda:
1. Haydovchining Telegram ID raqami (haydovchi buni `@userinfobot` orqali biladi), ismi,
   telefoni — bittada, vergul bilan: `123456789, Ism Familiya, +998901234567`
2. Tarifni tanlang (Ekonom/Komfort/Biznes)
3. Parol bering (yoki `/auto` — o'zi 4 xonali parol yaratadi)

Haydovchi keyin botga `/driver` yozib, o'z parolini kiritadi.

## Railway'ga joylash

Bot endi hech qanday HTTP port ochmaydi — faqat Telegram bilan polling orqali ishlaydi,
shuning uchun Railway'da xizmat turi **worker** bo'lishi kerak (`Procfile`da allaqachon
shunday sozlangan: `worker: python3 main.py`).

1. **Kodni GitHub'ga joylang** (yoki `railway up` orqali papkani to'g'ridan-to'g'ri yuklang —
   GitHub shart emas, lekin qulayroq).
2. Railway'da **New Project → Deploy from GitHub repo** (yoki bo'sh loyiha yaratib `railway up`).
3. **Environment Variables** bo'limida qo'shing:
   - `BOT_TOKEN` — @BotFather'dan olgan tokeningiz
   - `DB_PATH` — pastdagi Volume bilan birga ishlatiladi (masalan `/app/data/labooltiariq.db`)
4. **Volume qo'shing** (SQLite fayli saqlanib qolishi uchun — **bu juda muhim**: Railway'da
   konteyner har safar qayta deploy qilinganda fayl tizimi tozalanadi, Volume bo'lmasa
   bazangiz — barcha buyurtmalar, haydovchilar, ro'yxatdan o'tganlar — har deployda
   yo'qolib ketadi):
   - Service → **Settings → Volumes → New Volume**
   - Mount path: `/app/data`
   - Yuqoridagi `DB_PATH` shu papka ichiga ko'rsatishi kerak: `/app/data/labooltiariq.db`
5. Deploy tugagach, loglarda `Bot ... started polling` qatorini ko'rasiz — bot ishga
   tushgan bo'ladi.
6. Birinchi ishga tushgandan keyin, botga Telegram orqali:
   ```
   /admin admin2026
   /setpass admin YangiKuchliParol
   /setpass dispetcher YangiKuchliParol
   ```

**Eslatma — OSRM (km hisoblash):** Railway serverlari internetga to'liq chiqa oladi, shuning
uchun `pricing.py` ichidagi OSRM so'rovi (haqiqiy yo'l masofasi) muammosiz ishlashi kerak —
bu faqat sinov muhitida (masalan tarmoq cheklangan joyda) fallback (Haversine)ga tushishi
mumkin edi.

## Serverga doimiy joylash (VPS misolida, systemd)

```ini
# /etc/systemd/system/labooltiariq-bot.service
[Unit]
Description=LaboOltiariq Telegram Bot
After=network.target

[Service]
WorkingDirectory=/opt/labooltiariq-bot
Environment=BOT_TOKEN=sizning_tokeningiz
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now labooltiariq-bot
```

## Fayllar tuzilishi

```
db.py                  — SQLite bazasi va barcha CRUD funksiyalar
pricing.py              — narx/masofa hisoblash (frontend demo bilan bir xil formula)
states.py                — suhbat holatlari (FSM)
keyboards.py             — tugmalar
handlers_client.py       — mijoz: ro'yxat, buyurtma, kuzatish, baholash
handlers_driver.py       — haydovchi: kirish, safar boshqaruvi
handlers_dispatcher.py   — dispetcher: buyurtmalarni boshqarish
handlers_admin.py        — admin: narxlar, hududlar, haydovchilar, parollar
main.py                  — botni ishga tushiruvchi fayl
```
