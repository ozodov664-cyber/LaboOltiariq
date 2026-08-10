from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


class OrderFlow(StatesGroup):
    waiting_pickup = State()
    waiting_destination = State()
    waiting_region = State()
    waiting_tariff = State()
    waiting_payment = State()


class DriverLogin(StatesGroup):
    waiting_password = State()


class DispatcherLogin(StatesGroup):
    waiting_password = State()


class AdminLogin(StatesGroup):
    waiting_password = State()


class AdminAddRegion(StatesGroup):
    name = State()
    minimalka = State()
    wait_per_min = State()


class AdminAddDriver(StatesGroup):
    forward_contact = State()
    tariff = State()
    password = State()


class AdminEditTariff(StatesGroup):
    """Admin panelda mashina (Kia/Hyundai) + kuzov (bort/tent) turi bo'yicha 1 km narxini o'zgartirish."""
    waiting_price = State()


class AdminChangePassword(StatesGroup):
    which = State()
    value = State()


class AdminBroadcast(StatesGroup):
    waiting_text = State()


class DriverStreetPickup(StatesGroup):
    waiting_region = State()


class DispatcherAddOrder(StatesGroup):
    """Dispetcher telefon orqali qabul qilgan buyurtmani qo'lda kiritishi uchun."""
    phone = State()
    name = State()
    pickup = State()
    destination = State()
    region = State()
    tariff = State()
    km = State()
    payment = State()
