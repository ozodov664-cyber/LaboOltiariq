# LaboOltiariq — Telegram taksi boti + Mini App (backend)

## 🆕 Mini App qo'shildi

Endi botning barcha rollari (mijoz, haydovchi, dispetcher, admin) uchun to'liq **Telegram
Mini App** (Web App) bor — `webapp/` papkasida. Backend o'zgarmadi (aiogram + SQLite), ustiga
`aiohttp` веб-server qo'shildi, u ham `/api/*` JSON API'ni, ham mini app statik fayllarini
xizmat qiladi — bularning barchasi **bitta jarayonda**, bot polling bilan bir vaqtda ishlaydi.

**MUHIM — deploy turi o'zgardi:** avval `Procfile`da `worker:` edi (chunki bot faqat polling
qilardi, port ochmasdi). Endi mini app uchun HTTP port kerak, shuning uchun `Procfile`
`web:` ga o'zgartirildi. Railway avtomatik `PORT` muhit o'zgaruvchisini beradi — kodda
allaqachon shu o'zgaruvchidan foydalaniladi (`web.py`).

### Mini App'ni Telegram'ga ulash (BotFather orqali)

1. Railway'da deploy qilingandan keyin, loyihangizning ommaviy domenini oling: Railway
   loyihasi → Settings → Networking → **Generate Domain** (masalan
   `https://labooltiariq-bot-production.up.railway.app`)
2. Telegram'da @BotFather ga yozing → `/mybots` → botingizni tanlang → **Bot Settings →
   Menu Button → Configure Menu Button**
3. URL sifatida shu domeningizni kiriting (oxiriga `/` bilan, masalan
   `https://labooltiariq-bot-production.up.railway.app/`)
4. Tugma matnini kiriting, masalan `🚕 Ochish`
5. Endi bot chatining pastki chap burchagida doimiy tugma chiqadi — bosilganda mini app
   ochiladi va foydalanuvchi (mijoz/haydovchi/dispetcher/admin) rolini tanlaydi

**Eslatma:** mini app faqat **HTTPS** orqali ishlaydi — Railway domeni avtomatik HTTPS
beradi, qo'shimcha sozlash shart emas.

### Mini App arxitekturasi (qisqacha)

- `webauth.py` — Telegram `initData`ni tasdiqlaydi (bot tokeni bilan HMAC imzo tekshiruvi),
  shuning uchun mini appdan kelgan har bir so'rov haqiqatan shu botning shu foydalanuvchisidan
  ekani kafolatlanadi
- `webcommon.py` — umumiy yordamchi funksiyalar (auth, JSON javob formatlash)
- `api_client.py`, `api_driver.py`, `api_dispatcher.py`, `api_admin.py` — har bir rol uchun
  `/api/...` endpoint'lari, hammasi mavjud `db.py`/`pricing.py`/`dispatch.py`dan foydalanadi
  (kod takrorlanmagan — bot va mini app bir xil manbadan ishlaydi)
- `web.py` — aiohttp ilovasini yig'adi, statik fayllarni (`webapp/`) va API'ni ulaydi
- `webapp/` — frontend: `index.html`, `app.js`, `style.css` (build kerak emas, oddiy vanilla
  JS + Leaflet xarita kutubxonasi CDN orqali)

### Bilish kerak bo'lgan cheklovlar

- **Haydovchi joylashuvi faqat mini app ochiq turganda yuboriladi** — bu Telegram Mini
  App'larning umumiy cheklovi (fon rejimida ishlay olmaydi). Haydovchi telefon ekranini
  o'chirsa yoki appni yopsa, joylashuv yangilanishi to'xtaydi. Buyurtma qabul qilish/yakunlash
  esa bot orqali (push xabar + tugma) baribir ishlayveradi — mini app faqat qo'shimcha,
  qulayroq interfeys.
- Admin/dispetcher parollari brauzer xotirasida (sahifa yopilguncha) saqlanadi — sahifani
  qayta ochsangiz, qayta parol so'raladi (xavfsizlik uchun ataylab shunday).


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

Endi bot mini app uchun **HTTP port ham ochadi** (bot polling bilan bir vaqtda) — shuning
uchun Railway'da xizmat turi **web** bo'lishi kerak (`Procfile`da allaqachon shunday
sozlangan: `web: python3 main.py`). Railway `PORT` muhit o'zgaruvchisini o'zi beradi, kodda
avtomatik shundan foydalaniladi — qo'shimcha sozlash shart emas.

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
5. **Ommaviy domen oling**: Service → Settings → Networking → **Generate Domain**. Bu
   manzil mini app URL'i bo'ladi (yuqoridagi "Mini App'ni Telegram'ga ulash" bo'limiga qarang).
6. Deploy tugagach, loglarda `Bot ... started polling` va `Mini app HTTP server ishga
   tushdi` qatorlarini ko'rasiz — hammasi ishga tushgan bo'ladi.
7. Birinchi ishga tushgandan keyin, botga Telegram orqali:
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
