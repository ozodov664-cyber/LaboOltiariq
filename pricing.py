"""Narx hisoblash — frontend demodagi mantiq bilan bir xil, shunda ikkalasi
(brauzer demo va real bot) doim bir xil narxni ko'rsatadi."""
import math
import logging
import os

import aiohttp

log = logging.getLogger(__name__)

INCLUDED_KM = 3  # minimalka ichiga kiruvchi km

# OSRM — bepul, ochiq kodli marshrut hisoblash xizmati (Google/Yandex kabi API kalit shart emas).
# Standart holatda Anthropic'ning ochiq demo serveri ishlatiladi — u FAQAT SINOV uchun, ko'p
# so'rov yoki productionda ishonchli ishlashga kafolat bermaydi. O'z OSRM serveringizni
# ko'targandan keyin uni QAYTA KOD YOZMASDAN, faqat Railway'dagi OSRM_BASE_URL muhit
# o'zgaruvchisi orqali ulashingiz mumkin. Pastdagi "PRODUCTIONGA O'TISH" izohini o'qing.
OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
OSRM_TIMEOUT_SECONDS = 4


def fare(region: dict, tariff: dict, km: float) -> int:
    """Narx = hudud minimalkasi + (INCLUDED_KM dan oshgan har km) * tanlangan mashina/kuzov
    turining 1 km narxi. 1 km narxi endi hududga emas, tanlangan mashina (Kia/Hyundai) va
    kuzov turiga (bort/tent) bog'liq — buni admin panelda ("🚗 Mashina narxlari") sozlanadi."""
    extra_km = max(0.0, km - INCLUDED_KM)
    base = region["minimalka"] + extra_km * tariff["km_price"]
    return round(base)


FREE_WAIT_SECONDS = 60  # kutishning birinchi 1 daqiqasi (60 soniya) tekin — pul faqat shundan keyingi vaqt uchun olinadi


def wait_charge(seconds: int, wait_per_min: int) -> int:
    """Kutish narxi: birinchi 1 daqiqa (60 soniya) TEKIN, shundan keyingi har daqiqa uchun
    admin kiritgan summa (wait_per_min, hudud sozlamalarida) bo'yicha hisoblanadi."""
    billable_seconds = max(0, seconds - FREE_WAIT_SECONDS)
    return round((billable_seconds / 60) * wait_per_min)


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """Ikki GPS nuqta orasidagi to'g'ri chiziq masofasi (km) + ko'cha buralishlari uchun
    taxminiy +30% tuzatish. Bu REAL yo'l masofasi emas — faqat OSRM (yoki boshqa marshrut
    API) ishlamay qolganda zaxira (fallback) sifatida ishlatiladi."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1.3


async def real_road_km(lat1, lng1, lat2, lng2) -> float | None:
    """OSRM orqali ikki GPS nuqta orasidagi HAQIQIY yo'l (haydash) masofasini km da qaytaradi.
    Xizmat ishlamasa yoki javob bermasa — None qaytaradi (chaqiruvchi tomon haversine'ga o'tishi kerak)."""
    url = f"{OSRM_BASE_URL}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}"
    params = {"overview": "false"}
    try:
        timeout = aiohttp.ClientTimeout(total=OSRM_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data.get("code") != "Ok" or not data.get("routes"):
                    return None
                meters = data["routes"][0]["distance"]
                return round(meters / 1000, 2)
    except Exception as e:
        log.warning("OSRM route so'rovi muvaffaqiyatsiz: %s", e)
        return None


async def route_km(lat1, lng1, lat2, lng2) -> float:
    """Narx hisoblash uchun ISHLATILADIGAN asosiy funksiya: avval haqiqiy yo'l masofasini
    (OSRM) so'raydi, u ishlamasa to'g'ri chiziq (haversine + tuzatish) formulasiga tushadi —
    shunda mijoz har doim narx ko'radi, xizmat vaqtincha ishlamay qolsa ham buyurtma to'xtamaydi."""
    km = await real_road_km(lat1, lng1, lat2, lng2)
    if km is not None:
        return km
    return round(haversine_km(lat1, lng1, lat2, lng2), 1)


# ---------------- PRODUCTIONGA O'TISH ----------------
# Yuqoridagi OSRM_BASE_URL — router.project-osrm.org — Uzbekistonni ham qamrab oladi
# (OpenStreetMap ma'lumotlari asosida), lekin bu OMMAVIY DEMO SERVER: sekinlashishi,
# vaqti-vaqti bilan ishlamay qolishi yoki ko'p so'rovda bloklashi mumkin (shuning uchun
# har doim haversine fallback bor — buyurtma hech qachon "narxsiz" qolib ketmaydi).
#
# Jiddiy (production) foydalanish uchun 2 ta variant:
#
# 1) O'ZINGIZNING OSRM SERVERINGIZ (bepul, faqat server xarajati):
#    - Docker bilan bitta buyruqda ko'tariladi, O'zbekiston (yoki Markaziy Osiyo) OSM
#      xaritasi yuklab olinadi va shu manzilga (masalan http://your-server:5000) o'zingiz
#      egalik qilasiz — cheklov yo'q, tezroq va barqaror.
#    - Qo'llanma: https://github.com/Project-OSRM/osrm-backend#using-docker
#    - Keyin shu faylda OSRM_BASE_URL ni o'z serveringiz manziliga almashtirasiz — xolos,
#      boshqa hech narsani o'zgartirish shart emas.
#
# 2) GOOGLE DISTANCE MATRIX yoki YANDEX ROUTER API (pullik, lekin ko'proq haydash
#    vaqti/tirbandlik ma'lumoti bilan):
#    - Google/Yandex konsolida hisob ochib, billing yoqib, API kalit olasiz.
#    - real_road_km() funksiyasi ichidagi so'rovni OSRM o'rniga shu API chaqiruviga
#      almashtirasiz (URL, parametrlar va javobni ajratib olish qismi boshqacha bo'ladi) —
#      qolgan hamma joy (route_km, fare va h.k.) o'zgarishsiz qoladi.
