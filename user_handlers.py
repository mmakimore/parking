"""
Обработчики пользователей ParkingBot
"""
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import (
    get_main_menu_keyboard, get_cancel_keyboard, get_cancel_menu_keyboard,
    get_banks_keyboard, get_dates_keyboard, get_time_slots_keyboard,
    get_yes_no_keyboard, get_confirm_keyboard, get_available_slots_keyboard,
    get_no_slots_keyboard, get_user_spots_keyboard, get_spot_actions_keyboard,
    get_user_bookings_keyboard, get_booking_actions_keyboard,
    get_notifications_keyboard, get_profile_keyboard, get_notify_options_keyboard
)
from utils import (
    validate_name, validate_phone, validate_card, validate_date,
    validate_time, validate_price, validate_spot_number,
    format_datetime, mask_card, calculate_price, parse_datetime
)
from config import MAX_SPOTS_PER_USER, MAX_ACTIVE_BOOKINGS

logger = logging.getLogger(__name__)
router = Router()


# ==================== STATES ====================

class RegistrationStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_card = State()
    waiting_bank = State()


class AddSpotStates(StatesGroup):
    waiting_spot_number = State()
    waiting_start_date = State()
    waiting_start_date_manual = State()
    waiting_start_time = State()
    waiting_start_time_manual = State()
    waiting_end_date = State()
    waiting_end_date_manual = State()
    waiting_end_time = State()
    waiting_end_time_manual = State()
    waiting_partial = State()
    waiting_price = State()
    confirming = State()


class SearchStates(StatesGroup):
    waiting_date = State()
    waiting_date_manual = State()
    selecting_slot = State()
    confirming_booking = State()


class NotifyStates(StatesGroup):
    selecting_option = State()
    waiting_date = State()
    waiting_date_manual = State()


# ==================== REGISTRATION ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    user = db.get_user_by_telegram_id(message.from_user.id)
    
    if user:
        is_admin = user['role'] == 'admin'
        await message.answer(
            f"👋 Добро пожаловать, <b>{user['full_name']}</b>!\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(is_admin),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "👋 Добро пожаловать в <b>ParkingBot</b>!\n\n"
            "Это платформа для аренды парковочных мест между жильцами ЖК.\n\n"
            "Для начала давайте зарегистрируемся.\n\n"
            "📝 Введите ваше <b>имя и фамилию</b>:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(RegistrationStates.waiting_name)


@router.message(RegistrationStates.waiting_name)
async def process_registration_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена.")
        return
    
    is_valid, result = validate_name(message.text)
    if not is_valid:
        await message.answer(result)
        return
    
    await state.update_data(full_name=result)
    await message.answer(
        "📞 Введите ваш <b>номер телефона</b>:\n(формат: +7XXXXXXXXXX или 8XXXXXXXXXX)",
        parse_mode="HTML"
    )
    await state.set_state(RegistrationStates.waiting_phone)


@router.message(RegistrationStates.waiting_phone)
async def process_registration_phone(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена.")
        return
    
    is_valid, result = validate_phone(message.text)
    if not is_valid:
        await message.answer(result)
        return
    
    await state.update_data(phone=result)
    await message.answer(
        "💳 Введите <b>номер банковской карты</b>:\n(16 цифр, можно с пробелами)",
        parse_mode="HTML"
    )
    await state.set_state(RegistrationStates.waiting_card)


@router.message(RegistrationStates.waiting_card)
async def process_registration_card(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена.")
        return
    
    is_valid, result = validate_card(message.text)
    if not is_valid:
        await message.answer(result)
        return
    
    await state.update_data(card_number=result)
    await message.answer(
        "🏦 Выберите ваш <b>банк</b>:",
        reply_markup=get_banks_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationStates.waiting_bank)


@router.callback_query(RegistrationStates.waiting_bank, F.data.startswith("bank_"))
async def process_registration_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.replace("bank_", "")
    data = await state.get_data()
    
    user_id = db.create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=data['full_name'],
        phone=data['phone'],
        card_number=data['card_number'],
        bank=bank
    )
    
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 Имя: {data['full_name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"💳 Карта: {mask_card(data['card_number'])}\n"
        f"🏦 Банк: {bank}",
        parse_mode="HTML"
    )
    
    await callback.message.answer(
        "🎉 Добро пожаловать!\n\n"
        "• 📅 <b>Найти место</b> - найти и забронировать парковку\n"
        "• ➕ <b>Добавить место</b> - сдать своё место в аренду",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    
    await notify_admins_new_user(callback.bot, data['full_name'], data['phone'])


async def notify_admins_new_user(bot, full_name: str, phone: str):
    admins = db.get_admins()
    for admin in admins:
        try:
            await bot.send_message(
                admin['telegram_id'],
                f"👤 <b>Новый пользователь!</b>\n\nИмя: {full_name}\nТелефон: {phone}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin['telegram_id']}: {e}")


# ==================== MAIN MENU ====================

@router.message(F.text == "🔙 Главное меню")
async def go_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    user = db.get_user_by_telegram_id(message.from_user.id)
    is_admin = user and user['role'] == 'admin'
    await message.answer("🏠 <b>Главное меню</b>", reply_markup=get_main_menu_keyboard(is_admin), parse_mode="HTML")


@router.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    user = db.get_user_by_telegram_id(message.from_user.id)
    is_admin = user and user['role'] == 'admin'
    await message.answer("❌ Действие отменено.", reply_markup=get_main_menu_keyboard(is_admin))


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = db.get_user_by_telegram_id(callback.from_user.id)
    is_admin = user and user['role'] == 'admin'
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = db.get_user_by_telegram_id(callback.from_user.id)
    is_admin = user and user['role'] == 'admin'
    await callback.message.edit_text("🏠 Главное меню")
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))


# ==================== ADD PARKING SPOT ====================

@router.message(F.text == "➕ Добавить место")
async def add_spot_start(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return
    
    spots_count = db.get_user_spots_count(user['id'])
    if spots_count >= MAX_SPOTS_PER_USER:
        await message.answer(f"❌ Вы достигли лимита в {MAX_SPOTS_PER_USER} мест.")
        return
    
    await state.update_data(supplier_id=user['id'])
    await message.answer(
        "➕ <b>Добавление парковочного места</b>\n\nВведите <b>номер места</b>:\n(например: А12, 45, B3)",
        reply_markup=get_cancel_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AddSpotStates.waiting_spot_number)


@router.message(AddSpotStates.waiting_spot_number)
async def process_spot_number(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_spot_number(message.text)
    if not is_valid:
        await message.answer(result)
        return
    
    await state.update_data(spot_number=result)
    await message.answer("📅 Выберите <b>дату начала</b>:", reply_markup=get_dates_keyboard("start_date"), parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_start_date)


@router.callback_query(AddSpotStates.waiting_start_date, F.data.startswith("start_date_"))
async def process_start_date(callback: CallbackQuery, state: FSMContext):
    date_value = callback.data.replace("start_date_", "")
    
    if date_value == "manual":
        await callback.message.edit_text("📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>:", parse_mode="HTML")
        await state.set_state(AddSpotStates.waiting_start_date_manual)
        return
    
    is_valid, _ = validate_date(date_value)
    if not is_valid:
        await callback.answer("❌ Неверная дата", show_alert=True)
        return
    
    await state.update_data(start_date=date_value)
    await callback.message.edit_text("⏰ Выберите <b>время начала</b>:", reply_markup=get_time_slots_keyboard("start_time"), parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_start_time)


@router.message(AddSpotStates.waiting_start_date_manual)
async def process_start_date_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, _ = validate_date(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ")
        return
    
    await state.update_data(start_date=message.text)
    await message.answer("⏰ Выберите <b>время начала</b>:", reply_markup=get_time_slots_keyboard("start_time"), parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_start_time)


@router.callback_query(AddSpotStates.waiting_start_time, F.data.startswith("start_time_"))
async def process_start_time(callback: CallbackQuery, state: FSMContext):
    time_value = callback.data.replace("start_time_", "")
    
    if time_value == "manual":
        await callback.message.edit_text("⏰ Введите время в формате <b>ЧЧ:ММ</b>:", parse_mode="HTML")
        await state.set_state(AddSpotStates.waiting_start_time_manual)
        return
    
    await state.update_data(start_time=time_value)
    await callback.message.edit_text("📅 Выберите <b>дату окончания</b>:", reply_markup=get_dates_keyboard("end_date"), parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_end_date)


@router.message(AddSpotStates.waiting_start_time_manual)
async def process_start_time_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_time(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат. Введите время в формате ЧЧ:ММ")
        return
    
    await state.update_data(start_time=result)
    await message.answer("📅 Выберите <b>дату окончания</b>:", reply_markup=get_dates_keyboard("end_date"), parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_end_date)


@router.callback_query(AddSpotStates.waiting_end_date, F.data.startswith("end_date_"))
async def process_end_date(callback: CallbackQuery, state: FSMContext):
    date_value = callback.data.replace("end_date_", "")
    
    if date_value == "manual":
        await callback.message.edit_text("📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>:", parse_mode="HTML")
        await state.set_state(AddSpotStates.waiting_end_date_manual)
        return
    
    data = await state.get_data()
    is_valid, parsed_end = validate_date(date_value)
    _, parsed_start = validate_date(data['start_date'])
    
    if not is_valid or parsed_end < parsed_start:
        await callback.answer("❌ Дата окончания должна быть не раньше даты начала", show_alert=True)
        return
    
    await state.update_data(end_date=date_value)
    await callback.message.edit_text("⏰ Выберите <b>время окончания</b>:", reply_markup=get_time_slots_keyboard("end_time"), parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_end_time)


@router.message(AddSpotStates.waiting_end_date_manual)
async def process_end_date_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    data = await state.get_data()
    is_valid, parsed_end = validate_date(message.text)
    _, parsed_start = validate_date(data['start_date'])
    
    if not is_valid:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ")
        return
    
    if parsed_end < parsed_start:
        await message.answer("❌ Дата окончания должна быть не раньше даты начала")
        return
    
    await state.update_data(end_date=message.text)
    await message.answer("⏰ Выберите <b>время окончания</b>:", reply_markup=get_time_slots_keyboard("end_time"), parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_end_time)


@router.callback_query(AddSpotStates.waiting_end_time, F.data.startswith("end_time_"))
async def process_end_time(callback: CallbackQuery, state: FSMContext):
    time_value = callback.data.replace("end_time_", "")
    
    if time_value == "manual":
        await callback.message.edit_text("⏰ Введите время в формате <b>ЧЧ:ММ</b>:", parse_mode="HTML")
        await state.set_state(AddSpotStates.waiting_end_time_manual)
        return
    
    data = await state.get_data()
    start_dt = parse_datetime(data['start_date'], data['start_time'])
    end_dt = parse_datetime(data['end_date'], time_value)
    
    if end_dt <= start_dt:
        await callback.answer("❌ Время окончания должно быть позже времени начала", show_alert=True)
        return
    
    await state.update_data(end_time=time_value)
    await callback.message.edit_text(
        "🔄 Можно ли сдавать место <b>по частям</b>?\n\n"
        "Если Да - арендаторы смогут бронировать часть времени.\n"
        "Если Нет - только весь период целиком.",
        reply_markup=get_yes_no_keyboard("partial"),
        parse_mode="HTML"
    )
    await state.set_state(AddSpotStates.waiting_partial)


@router.message(AddSpotStates.waiting_end_time_manual)
async def process_end_time_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_time(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат. Введите время в формате ЧЧ:ММ")
        return
    
    data = await state.get_data()
    start_dt = parse_datetime(data['start_date'], data['start_time'])
    end_dt = parse_datetime(data['end_date'], result)
    
    if end_dt <= start_dt:
        await message.answer("❌ Время окончания должно быть позже времени начала")
        return
    
    await state.update_data(end_time=result)
    await message.answer(
        "🔄 Можно ли сдавать место <b>по частям</b>?",
        reply_markup=get_yes_no_keyboard("partial"),
        parse_mode="HTML"
    )
    await state.set_state(AddSpotStates.waiting_partial)


@router.callback_query(AddSpotStates.waiting_partial, F.data.startswith("partial_"))
async def process_partial(callback: CallbackQuery, state: FSMContext):
    is_partial = callback.data == "partial_yes"
    await state.update_data(is_partial_allowed=is_partial)
    await callback.message.edit_text("💰 Введите <b>цену за час</b> в рублях (от 1 до 10000):", parse_mode="HTML")
    await state.set_state(AddSpotStates.waiting_price)


@router.message(AddSpotStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, price = validate_price(message.text)
    if not is_valid:
        await message.answer("❌ Введите корректную цену от 1 до 10000 рублей")
        return
    
    await state.update_data(price_per_hour=price)
    data = await state.get_data()
    partial_text = "✅ Да" if data['is_partial_allowed'] else "❌ Нет"
    
    await message.answer(
        f"📋 <b>Проверьте данные:</b>\n\n"
        f"🏠 Место: <b>{data['spot_number']}</b>\n"
        f"📅 Начало: <b>{data['start_date']} {data['start_time']}</b>\n"
        f"📅 Конец: <b>{data['end_date']} {data['end_time']}</b>\n"
        f"🔄 Частичная аренда: {partial_text}\n"
        f"💰 Цена: <b>{price}₽/час</b>\n\nВсё верно?",
        reply_markup=get_confirm_keyboard("spot_confirm"),
        parse_mode="HTML"
    )
    await state.set_state(AddSpotStates.confirming)


@router.callback_query(AddSpotStates.confirming, F.data.startswith("spot_confirm_"))
async def confirm_spot(callback: CallbackQuery, state: FSMContext):
    if callback.data == "spot_confirm_no":
        await state.clear()
        user = db.get_user_by_telegram_id(callback.from_user.id)
        is_admin = user and user['role'] == 'admin'
        await callback.message.edit_text("❌ Добавление места отменено.")
        await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))
        return
    
    data = await state.get_data()
    
    spot_id = db.create_parking_spot(
        supplier_id=data['supplier_id'],
        spot_number=data['spot_number'],
        price_per_hour=data['price_per_hour'],
        is_partial_allowed=data['is_partial_allowed']
    )
    
    start_dt = parse_datetime(data['start_date'], data['start_time'])
    end_dt = parse_datetime(data['end_date'], data['end_time'])
    db.create_spot_availability(spot_id, start_dt, end_dt)
    
    await state.clear()
    user = db.get_user_by_telegram_id(callback.from_user.id)
    is_admin = user and user['role'] == 'admin'
    
    await callback.message.edit_text(
        f"✅ <b>Место успешно добавлено!</b>\n\n"
        f"🏠 Номер: {data['spot_number']}\n"
        f"📅 Доступно: {data['start_date']} {data['start_time']} - {data['end_date']} {data['end_time']}\n"
        f"💰 Цена: {data['price_per_hour']}₽/час",
        parse_mode="HTML"
    )
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))
    await check_and_send_notifications(callback.bot, spot_id, start_dt, end_dt, data)


async def check_and_send_notifications(bot, spot_id: int, start_dt: datetime, end_dt: datetime, spot_data: dict):
    notifications = db.get_matching_notifications(spot_id, start_dt, end_dt)
    for notif in notifications:
        try:
            await bot.send_message(
                notif['telegram_id'],
                f"🔔 <b>Появилось свободное место!</b>\n\n"
                f"🏠 Место: {spot_data['spot_number']}\n"
                f"📅 Время: {spot_data['start_date']} {spot_data['start_time']} - {spot_data['end_date']} {spot_data['end_time']}\n"
                f"💰 Цена: {spot_data['price_per_hour']}₽/час",
                parse_mode="HTML"
            )
            db.deactivate_notification(notif['id'])
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")


# ==================== SEARCH & BOOKING ====================

@router.message(F.text == "📅 Найти место")
async def search_start(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return
    
    await state.update_data(user_id=user['id'])
    await message.answer("🔍 <b>Поиск парковочного места</b>\n\nВыберите дату:", reply_markup=get_dates_keyboard("search_date"), parse_mode="HTML")
    await state.set_state(SearchStates.waiting_date)


@router.callback_query(SearchStates.waiting_date, F.data.startswith("search_date_"))
async def process_search_date(callback: CallbackQuery, state: FSMContext):
    date_value = callback.data.replace("search_date_", "")
    
    if date_value == "manual":
        await callback.message.edit_text("📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>:", parse_mode="HTML")
        await state.set_state(SearchStates.waiting_date_manual)
        return
    
    is_valid, _ = validate_date(date_value)
    if not is_valid:
        await callback.answer("❌ Неверная дата", show_alert=True)
        return
    
    await state.update_data(search_date=date_value)
    await show_available_slots(callback, state, date_value)


@router.message(SearchStates.waiting_date_manual)
async def process_search_date_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, parsed_date = validate_date(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ")
        return
    
    await state.update_data(search_date=message.text)
    date_obj = datetime.strptime(message.text, "%d.%m.%Y")
    date_str = date_obj.strftime("%Y-%m-%d")
    slots = db.get_available_slots(date_str)
    
    if not slots:
        await message.answer(
            "😔 На эту дату нет свободных мест.",
            reply_markup=get_no_slots_keyboard()
        )
    else:
        await message.answer(
            f"🏠 <b>Найдено {len(slots)} слотов</b>\n\nВыберите место:",
            reply_markup=get_available_slots_keyboard(slots),
            parse_mode="HTML"
        )
    await state.set_state(SearchStates.selecting_slot)


async def show_available_slots(callback: CallbackQuery, state: FSMContext, date_value: str):
    date_obj = datetime.strptime(date_value, "%d.%m.%Y")
    date_str = date_obj.strftime("%Y-%m-%d")
    slots = db.get_available_slots(date_str)
    
    if not slots:
        await callback.message.edit_text("😔 На эту дату нет свободных мест.", reply_markup=get_no_slots_keyboard())
    else:
        await callback.message.edit_text(
            f"🏠 <b>Найдено {len(slots)} слотов</b>\n\nВыберите место:",
            reply_markup=get_available_slots_keyboard(slots),
            parse_mode="HTML"
        )
    await state.set_state(SearchStates.selecting_slot)


@router.callback_query(SearchStates.selecting_slot, F.data.startswith("slot_"))
async def select_slot(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.replace("slot_", ""))
    slot = db.get_availability_by_id(slot_id)
    
    if not slot:
        await callback.answer("❌ Слот больше не доступен", show_alert=True)
        return
    
    data = await state.get_data()
    
    if slot['supplier_id'] == data['user_id']:
        await callback.answer("❌ Вы не можете забронировать своё место", show_alert=True)
        return
    
    active_bookings = db.get_active_bookings_count(data['user_id'])
    if active_bookings >= MAX_ACTIVE_BOOKINGS:
        await callback.answer(f"❌ Лимит {MAX_ACTIVE_BOOKINGS} бронирований", show_alert=True)
        return
    
    start_dt = datetime.fromisoformat(slot['start_time'])
    end_dt = datetime.fromisoformat(slot['end_time'])
    total_price = calculate_price(slot['price_per_hour'], start_dt, end_dt)
    hours = (end_dt - start_dt).total_seconds() / 3600
    
    await state.update_data(
        selected_slot_id=slot_id, spot_id=slot['spot_id'],
        start_time=start_dt, end_time=end_dt, total_price=total_price,
        supplier_card=slot['card_number'], supplier_bank=slot['bank'],
        spot_number=slot['spot_number'], supplier_telegram_id=slot['supplier_telegram_id']
    )
    
    await callback.message.edit_text(
        f"📋 <b>Подтверждение бронирования</b>\n\n"
        f"🏠 Место: <b>{slot['spot_number']}</b>\n"
        f"📅 Начало: <b>{format_datetime(start_dt)}</b>\n"
        f"📅 Конец: <b>{format_datetime(end_dt)}</b>\n"
        f"⏱ Длительность: <b>{hours:.1f} ч.</b>\n"
        f"💰 Стоимость: <b>{total_price}₽</b>\n\nПодтвердить?",
        reply_markup=get_confirm_keyboard("booking_confirm"),
        parse_mode="HTML"
    )
    await state.set_state(SearchStates.confirming_booking)


@router.callback_query(SearchStates.confirming_booking, F.data.startswith("booking_confirm_"))
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    if callback.data == "booking_confirm_no":
        await state.clear()
        user = db.get_user_by_telegram_id(callback.from_user.id)
        is_admin = user and user['role'] == 'admin'
        await callback.message.edit_text("❌ Бронирование отменено.")
        await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))
        return
    
    data = await state.get_data()
    
    booking_id = db.create_booking(
        customer_id=data['user_id'], spot_id=data['spot_id'],
        availability_id=data['selected_slot_id'],
        start_time=data['start_time'], end_time=data['end_time'],
        total_price=data['total_price']
    )
    
    await state.clear()
    user = db.get_user_by_telegram_id(callback.from_user.id)
    is_admin = user and user['role'] == 'admin'
    
    await callback.message.edit_text(
        f"✅ <b>Бронирование #{booking_id} создано!</b>\n\n"
        f"🏠 Место: {data['spot_number']}\n"
        f"📅 Время: {format_datetime(data['start_time'])} - {format_datetime(data['end_time'])}\n"
        f"💰 К оплате: <b>{data['total_price']}₽</b>\n\n"
        f"<b>💳 Реквизиты:</b>\n"
        f"🏦 Банк: {data['supplier_bank']}\n"
        f"💳 Карта: {mask_card(data['supplier_card'])}\n\n"
        f"⏰ Время на оплату: 24 часа",
        parse_mode="HTML"
    )
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))
    
    try:
        await callback.bot.send_message(
            data['supplier_telegram_id'],
            f"🎉 <b>Новое бронирование!</b>\n\n"
            f"🏠 Место: {data['spot_number']}\n"
            f"📅 Время: {format_datetime(data['start_time'])} - {format_datetime(data['end_time'])}\n"
            f"💰 Сумма: {data['total_price']}₽",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to notify supplier: {e}")


@router.callback_query(F.data == "search_again")
async def search_again(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔍 <b>Поиск</b>\n\nВыберите дату:", reply_markup=get_dates_keyboard("search_date"), parse_mode="HTML")
    await state.set_state(SearchStates.waiting_date)


# ==================== NOTIFICATIONS ====================

@router.callback_query(F.data == "notify_available")
async def notify_available_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔔 <b>Уведомление о месте</b>\n\nВыберите тип:", reply_markup=get_notify_options_keyboard(), parse_mode="HTML")
    await state.set_state(NotifyStates.selecting_option)


@router.callback_query(NotifyStates.selecting_option, F.data == "notify_any")
async def notify_any(callback: CallbackQuery, state: FSMContext):
    user = db.get_user_by_telegram_id(callback.from_user.id)
    db.create_spot_notification(user_id=user['id'], notify_any=True)
    await state.clear()
    is_admin = user['role'] == 'admin'
    await callback.message.edit_text("✅ <b>Подписка оформлена!</b>\n\nВы получите уведомление при появлении любого места.", parse_mode="HTML")
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))


@router.callback_query(NotifyStates.selecting_option, F.data == "notify_date")
async def notify_date_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📅 Выберите дату:", reply_markup=get_dates_keyboard("notify_date"), parse_mode="HTML")
    await state.set_state(NotifyStates.waiting_date)


@router.callback_query(NotifyStates.waiting_date, F.data.startswith("notify_date_"))
async def process_notify_date(callback: CallbackQuery, state: FSMContext):
    date_value = callback.data.replace("notify_date_", "")
    
    if date_value == "manual":
        await callback.message.edit_text("📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>:", parse_mode="HTML")
        await state.set_state(NotifyStates.waiting_date_manual)
        return
    
    user = db.get_user_by_telegram_id(callback.from_user.id)
    date_obj = datetime.strptime(date_value, "%d.%m.%Y")
    date_str = date_obj.strftime("%Y-%m-%d")
    
    db.create_spot_notification(user_id=user['id'], desired_date=date_str, notify_any=False)
    await state.clear()
    is_admin = user['role'] == 'admin'
    await callback.message.edit_text(f"✅ <b>Подписка оформлена!</b>\n\nУведомим при появлении места на {date_value}.", parse_mode="HTML")
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))


@router.message(NotifyStates.waiting_date_manual)
async def process_notify_date_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, parsed_date = validate_date(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат")
        return
    
    user = db.get_user_by_telegram_id(message.from_user.id)
    date_str = parsed_date.strftime("%Y-%m-%d")
    db.create_spot_notification(user_id=user['id'], desired_date=date_str, notify_any=False)
    await state.clear()
    is_admin = user['role'] == 'admin'
    await message.answer(f"✅ <b>Подписка оформлена!</b>\n\nУведомим при появлении места на {message.text}.", reply_markup=get_main_menu_keyboard(is_admin), parse_mode="HTML")


@router.message(F.text == "🔔 Уведомления")
async def show_notifications(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return
    
    notifications = db.get_user_notifications(user['id'])
    
    if not notifications:
        await message.answer("🔔 <b>Ваши подписки</b>\n\nУ вас нет активных подписок.", parse_mode="HTML")
    else:
        await message.answer(
            f"🔔 <b>Ваши подписки</b>\n\nАктивных: {len(notifications)}\n\nНажмите для удаления:",
            reply_markup=get_notifications_keyboard(notifications),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("del_notif_"))
async def delete_notification(callback: CallbackQuery, state: FSMContext):
    notif_id = int(callback.data.replace("del_notif_", ""))
    db.deactivate_notification(notif_id)
    
    user = db.get_user_by_telegram_id(callback.from_user.id)
    notifications = db.get_user_notifications(user['id'])
    
    if not notifications:
        await callback.message.edit_text("✅ Подписка удалена. Активных подписок нет.")
    else:
        await callback.message.edit_text(
            f"✅ Удалено.\n\n🔔 <b>Ваши подписки</b>\n\nАктивных: {len(notifications)}",
            reply_markup=get_notifications_keyboard(notifications),
            parse_mode="HTML"
        )


# ==================== MY SPOTS ====================

@router.message(F.text == "🏠 Мои места")
async def show_my_spots(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return
    
    spots = db.get_user_spots(user['id'])
    
    if not spots:
        await message.answer("🏠 <b>Мои места</b>\n\nУ вас нет добавленных мест.\n\nНажмите '➕ Добавить место'.", parse_mode="HTML")
    else:
        await message.answer(
            f"🏠 <b>Мои места</b>\n\nВсего: {len(spots)}",
            reply_markup=get_user_spots_keyboard(spots),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("myspot_"))
async def show_spot_details(callback: CallbackQuery, state: FSMContext):
    spot_id = int(callback.data.replace("myspot_", ""))
    spot = db.get_spot_by_id(spot_id)
    
    if not spot:
        await callback.answer("❌ Место не найдено", show_alert=True)
        return
    
    availabilities = db.get_spot_availabilities(spot_id)
    avail_text = ""
    if availabilities:
        for av in availabilities[:5]:
            start = datetime.fromisoformat(av['start_time'])
            end = datetime.fromisoformat(av['end_time'])
            status = "🟢" if not av['is_booked'] else "🔴"
            avail_text += f"\n{status} {format_datetime(start)} - {format_datetime(end)}"
    else:
        avail_text = "\nНет активных слотов"
    
    partial_text = "✅ Да" if spot['is_partial_allowed'] else "❌ Нет"
    
    await callback.message.edit_text(
        f"🏠 <b>Место: {spot['spot_number']}</b>\n\n"
        f"💰 Цена: {spot['price_per_hour']}₽/час\n"
        f"🔄 Частичная аренда: {partial_text}\n\n"
        f"<b>📅 Слоты:</b>{avail_text}",
        reply_markup=get_spot_actions_keyboard(spot_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("delete_spot_"))
async def delete_spot(callback: CallbackQuery, state: FSMContext):
    spot_id = int(callback.data.replace("delete_spot_", ""))
    db.delete_spot(spot_id)
    await callback.answer("✅ Место удалено")
    
    user = db.get_user_by_telegram_id(callback.from_user.id)
    spots = db.get_user_spots(user['id'])
    
    if not spots:
        await callback.message.edit_text("🏠 <b>Мои места</b>\n\nУ вас нет мест.", parse_mode="HTML")
    else:
        await callback.message.edit_text(f"🏠 <b>Мои места</b>\n\nВсего: {len(spots)}", reply_markup=get_user_spots_keyboard(spots), parse_mode="HTML")


@router.callback_query(F.data == "my_spots")
async def back_to_my_spots(callback: CallbackQuery, state: FSMContext):
    user = db.get_user_by_telegram_id(callback.from_user.id)
    spots = db.get_user_spots(user['id'])
    await callback.message.edit_text(f"🏠 <b>Мои места</b>\n\nВсего: {len(spots)}", reply_markup=get_user_spots_keyboard(spots), parse_mode="HTML")


# ==================== MY BOOKINGS ====================

@router.message(F.text == "📋 Мои бронирования")
async def show_my_bookings(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return
    
    bookings = db.get_user_bookings(user['id'])
    
    if not bookings:
        await message.answer("📋 <b>Мои бронирования</b>\n\nУ вас нет бронирований.", parse_mode="HTML")
    else:
        await message.answer(f"📋 <b>Мои бронирования</b>\n\nВсего: {len(bookings)}", reply_markup=get_user_bookings_keyboard(bookings), parse_mode="HTML")


@router.callback_query(F.data.startswith("booking_") & ~F.data.startswith("booking_confirm"))
async def show_booking_details(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.replace("booking_", ""))
    booking = db.get_booking_by_id(booking_id)
    
    if not booking:
        await callback.answer("❌ Не найдено", show_alert=True)
        return
    
    start = datetime.fromisoformat(booking['start_time'])
    end = datetime.fromisoformat(booking['end_time'])
    status_text = {'pending': '⏳ Ожидает оплаты', 'confirmed': '✅ Подтверждено', 'cancelled': '❌ Отменено', 'completed': '✔️ Завершено'}.get(booking['status'], '❓')
    
    await callback.message.edit_text(
        f"📋 <b>Бронирование #{booking_id}</b>\n\n"
        f"🏠 Место: {booking['spot_number']}\n"
        f"📅 {format_datetime(start)} - {format_datetime(end)}\n"
        f"💰 {booking['total_price']}₽\n"
        f"📊 {status_text}\n\n"
        f"<b>💳 Реквизиты:</b>\n"
        f"🏦 {booking['bank']}\n"
        f"💳 {mask_card(booking['card_number'])}",
        reply_markup=get_booking_actions_keyboard(booking_id, booking['status']),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking_handler(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.replace("cancel_booking_", ""))
    db.cancel_booking(booking_id)
    await callback.answer("✅ Бронирование отменено")
    
    user = db.get_user_by_telegram_id(callback.from_user.id)
    bookings = db.get_user_bookings(user['id'])
    
    if not bookings:
        await callback.message.edit_text("📋 <b>Мои бронирования</b>\n\nНет бронирований.", parse_mode="HTML")
    else:
        await callback.message.edit_text(f"📋 <b>Мои бронирования</b>\n\nВсего: {len(bookings)}", reply_markup=get_user_bookings_keyboard(bookings), parse_mode="HTML")


@router.callback_query(F.data == "my_bookings")
async def back_to_my_bookings(callback: CallbackQuery, state: FSMContext):
    user = db.get_user_by_telegram_id(callback.from_user.id)
    bookings = db.get_user_bookings(user['id'])
    await callback.message.edit_text(f"📋 <b>Мои бронирования</b>\n\nВсего: {len(bookings)}", reply_markup=get_user_bookings_keyboard(bookings), parse_mode="HTML")


# ==================== PROFILE ====================

@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return
    
    stats = db.get_user_statistics(user['id'])
    role_text = {'user': '👤 Пользователь', 'supplier': '🏠 Поставщик', 'admin': '👑 Администратор'}.get(user['role'], '👤')
    
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📛 Имя: {user['full_name']}\n"
        f"📞 Телефон: {user['phone']}\n"
        f"💳 Карта: {mask_card(user['card_number'])}\n"
        f"🏦 Банк: {user['bank']}\n"
        f"🎭 Роль: {role_text}\n\n"
        f"<b>📊 Статистика:</b>\n"
        f"📋 Бронирований: {stats['total_bookings']}\n"
        f"🏠 Мест: {stats['total_spots']}\n"
        f"💸 Потрачено: {stats['total_spent']}₽\n"
        f"💰 Заработано: {stats['total_earned']}₽",
        reply_markup=get_profile_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back")
async def back_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = db.get_user_by_telegram_id(callback.from_user.id)
    is_admin = user and user['role'] == 'admin'
    await callback.message.edit_text("🏠 Главное меню")
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))


# ==================== EDIT PROFILE ====================

class EditProfileStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_card = State()
    waiting_bank = State()


@router.callback_query(F.data == "edit_name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите новое <b>имя и фамилию</b>:", parse_mode="HTML")
    await state.set_state(EditProfileStates.waiting_name)


@router.message(EditProfileStates.waiting_name)
async def process_edit_name(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_name(message.text)
    if not is_valid:
        await message.answer(result)
        return
    
    user = db.get_user_by_telegram_id(message.from_user.id)
    db.update_user(user['id'], full_name=result)
    
    await state.clear()
    await message.answer(f"✅ Имя изменено на: <b>{result}</b>", parse_mode="HTML")
    await show_profile(message, state)


@router.callback_query(F.data == "edit_phone")
async def edit_phone_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📞 Введите новый <b>номер телефона</b>:\n(формат: +7XXXXXXXXXX)", parse_mode="HTML")
    await state.set_state(EditProfileStates.waiting_phone)


@router.message(EditProfileStates.waiting_phone)
async def process_edit_phone(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_phone(message.text)
    if not is_valid:
        await message.answer(result)
        return
    
    user = db.get_user_by_telegram_id(message.from_user.id)
    db.update_user(user['id'], phone=result)
    
    await state.clear()
    await message.answer(f"✅ Телефон изменён на: <b>{result}</b>", parse_mode="HTML")
    await show_profile(message, state)


@router.callback_query(F.data == "edit_card")
async def edit_card_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💳 Введите новый <b>номер карты</b>:\n(16 цифр)", parse_mode="HTML")
    await state.set_state(EditProfileStates.waiting_card)


@router.message(EditProfileStates.waiting_card)
async def process_edit_card(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_card(message.text)
    if not is_valid:
        await message.answer(result)
        return
    
    user = db.get_user_by_telegram_id(message.from_user.id)
    await state.update_data(new_card=result)
    
    from keyboards import get_banks_keyboard
    await message.answer("🏦 Выберите банк:", reply_markup=get_banks_keyboard())
    await state.set_state(EditProfileStates.waiting_bank)


@router.callback_query(EditProfileStates.waiting_bank, F.data.startswith("bank_"))
async def process_edit_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.replace("bank_", "")
    data = await state.get_data()
    
    user = db.get_user_by_telegram_id(callback.from_user.id)
    db.update_user(user['id'], card_number=data['new_card'], bank=bank)
    
    await state.clear()
    await callback.message.edit_text(f"✅ Карта изменена!\n\n💳 {mask_card(data['new_card'])}\n🏦 {bank}", parse_mode="HTML")
    
    # Показываем профиль заново
    user = db.get_user_by_telegram_id(callback.from_user.id)
    stats = db.get_user_statistics(user['id'])
    role_text = {'user': '👤 Пользователь', 'supplier': '🏠 Поставщик', 'admin': '👑 Администратор'}.get(user['role'], '👤')
    
    await callback.message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📛 Имя: {user['full_name']}\n"
        f"📞 Телефон: {user['phone']}\n"
        f"💳 Карта: {mask_card(user['card_number'])}\n"
        f"🏦 Банк: {user['bank']}\n"
        f"🎭 Роль: {role_text}\n\n"
        f"<b>📊 Статистика:</b>\n"
        f"📋 Бронирований: {stats['total_bookings']}\n"
        f"🏠 Мест: {stats['total_spots']}\n"
        f"💸 Потрачено: {stats['total_spent']}₽\n"
        f"💰 Заработано: {stats['total_earned']}₽",
        reply_markup=get_profile_keyboard(),
        parse_mode="HTML"
    )


# ==================== ADD SLOT TO EXISTING SPOT ====================

class AddSlotStates(StatesGroup):
    waiting_start_date = State()
    waiting_start_date_manual = State()
    waiting_start_time = State()
    waiting_start_time_manual = State()
    waiting_end_date = State()
    waiting_end_date_manual = State()
    waiting_end_time = State()
    waiting_end_time_manual = State()


@router.callback_query(F.data.startswith("add_slot_"))
async def add_slot_start(callback: CallbackQuery, state: FSMContext):
    spot_id = int(callback.data.replace("add_slot_", ""))
    await state.update_data(spot_id=spot_id)
    
    await callback.message.edit_text(
        "📅 <b>Добавление нового слота</b>\n\nВыберите дату начала:",
        reply_markup=get_dates_keyboard("slot_start_date"),
        parse_mode="HTML"
    )
    await state.set_state(AddSlotStates.waiting_start_date)


@router.callback_query(AddSlotStates.waiting_start_date, F.data.startswith("slot_start_date_"))
async def process_slot_start_date(callback: CallbackQuery, state: FSMContext):
    date_value = callback.data.replace("slot_start_date_", "")
    
    if date_value == "manual":
        await callback.message.edit_text("📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>:", parse_mode="HTML")
        await state.set_state(AddSlotStates.waiting_start_date_manual)
        return
    
    is_valid, _ = validate_date(date_value)
    if not is_valid:
        await callback.answer("❌ Неверная дата", show_alert=True)
        return
    
    await state.update_data(start_date=date_value)
    await callback.message.edit_text("⏰ Выберите время начала:", reply_markup=get_time_slots_keyboard("slot_start_time"), parse_mode="HTML")
    await state.set_state(AddSlotStates.waiting_start_time)


@router.message(AddSlotStates.waiting_start_date_manual)
async def process_slot_start_date_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, _ = validate_date(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат")
        return
    
    await state.update_data(start_date=message.text)
    await message.answer("⏰ Выберите время начала:", reply_markup=get_time_slots_keyboard("slot_start_time"))
    await state.set_state(AddSlotStates.waiting_start_time)


@router.callback_query(AddSlotStates.waiting_start_time, F.data.startswith("slot_start_time_"))
async def process_slot_start_time(callback: CallbackQuery, state: FSMContext):
    time_value = callback.data.replace("slot_start_time_", "")
    
    if time_value == "manual":
        await callback.message.edit_text("⏰ Введите время в формате <b>ЧЧ:ММ</b>:", parse_mode="HTML")
        await state.set_state(AddSlotStates.waiting_start_time_manual)
        return
    
    await state.update_data(start_time=time_value)
    await callback.message.edit_text("📅 Выберите дату окончания:", reply_markup=get_dates_keyboard("slot_end_date"), parse_mode="HTML")
    await state.set_state(AddSlotStates.waiting_end_date)


@router.message(AddSlotStates.waiting_start_time_manual)
async def process_slot_start_time_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_time(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат")
        return
    
    await state.update_data(start_time=result)
    await message.answer("📅 Выберите дату окончания:", reply_markup=get_dates_keyboard("slot_end_date"))
    await state.set_state(AddSlotStates.waiting_end_date)


@router.callback_query(AddSlotStates.waiting_end_date, F.data.startswith("slot_end_date_"))
async def process_slot_end_date(callback: CallbackQuery, state: FSMContext):
    date_value = callback.data.replace("slot_end_date_", "")
    
    if date_value == "manual":
        await callback.message.edit_text("📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>:", parse_mode="HTML")
        await state.set_state(AddSlotStates.waiting_end_date_manual)
        return
    
    data = await state.get_data()
    is_valid, parsed_end = validate_date(date_value)
    _, parsed_start = validate_date(data['start_date'])
    
    if not is_valid or parsed_end < parsed_start:
        await callback.answer("❌ Дата окончания должна быть не раньше даты начала", show_alert=True)
        return
    
    await state.update_data(end_date=date_value)
    await callback.message.edit_text("⏰ Выберите время окончания:", reply_markup=get_time_slots_keyboard("slot_end_time"), parse_mode="HTML")
    await state.set_state(AddSlotStates.waiting_end_time)


@router.message(AddSlotStates.waiting_end_date_manual)
async def process_slot_end_date_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    data = await state.get_data()
    is_valid, parsed_end = validate_date(message.text)
    _, parsed_start = validate_date(data['start_date'])
    
    if not is_valid or parsed_end < parsed_start:
        await message.answer("❌ Неверная дата")
        return
    
    await state.update_data(end_date=message.text)
    await message.answer("⏰ Выберите время окончания:", reply_markup=get_time_slots_keyboard("slot_end_time"))
    await state.set_state(AddSlotStates.waiting_end_time)


@router.callback_query(AddSlotStates.waiting_end_time, F.data.startswith("slot_end_time_"))
async def process_slot_end_time(callback: CallbackQuery, state: FSMContext):
    time_value = callback.data.replace("slot_end_time_", "")
    
    if time_value == "manual":
        await callback.message.edit_text("⏰ Введите время в формате <b>ЧЧ:ММ</b>:", parse_mode="HTML")
        await state.set_state(AddSlotStates.waiting_end_time_manual)
        return
    
    data = await state.get_data()
    start_dt = parse_datetime(data['start_date'], data['start_time'])
    end_dt = parse_datetime(data['end_date'], time_value)
    
    if end_dt <= start_dt:
        await callback.answer("❌ Время окончания должно быть позже времени начала", show_alert=True)
        return
    
    # Создаём слот
    db.create_spot_availability(data['spot_id'], start_dt, end_dt)
    
    spot = db.get_spot_by_id(data['spot_id'])
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Слот добавлен!</b>\n\n"
        f"🏠 Место: {spot['spot_number']}\n"
        f"📅 {data['start_date']} {data['start_time']} - {data['end_date']} {time_value}",
        parse_mode="HTML"
    )
    
    # Проверяем уведомления
    spot_data = {
        'spot_number': spot['spot_number'],
        'start_date': data['start_date'],
        'start_time': data['start_time'],
        'end_date': data['end_date'],
        'end_time': time_value,
        'price_per_hour': spot['price_per_hour']
    }
    await check_and_send_notifications(callback.bot, data['spot_id'], start_dt, end_dt, spot_data)
    
    user = db.get_user_by_telegram_id(callback.from_user.id)
    is_admin = user and user['role'] == 'admin'
    await callback.message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))


@router.message(AddSlotStates.waiting_end_time_manual)
async def process_slot_end_time_manual(message: Message, state: FSMContext):
    if message.text in ["❌ Отмена", "🔙 Главное меню"]:
        await cancel_action(message, state)
        return
    
    is_valid, result = validate_time(message.text)
    if not is_valid:
        await message.answer("❌ Неверный формат")
        return
    
    data = await state.get_data()
    start_dt = parse_datetime(data['start_date'], data['start_time'])
    end_dt = parse_datetime(data['end_date'], result)
    
    if end_dt <= start_dt:
        await message.answer("❌ Время окончания должно быть позже")
        return
    
    db.create_spot_availability(data['spot_id'], start_dt, end_dt)
    spot = db.get_spot_by_id(data['spot_id'])
    
    await state.clear()
    await message.answer(
        f"✅ <b>Слот добавлен!</b>\n\n"
        f"🏠 Место: {spot['spot_number']}\n"
        f"📅 {data['start_date']} {data['start_time']} - {data['end_date']} {result}",
        parse_mode="HTML"
    )
    
    spot_data = {
        'spot_number': spot['spot_number'],
        'start_date': data['start_date'],
        'start_time': data['start_time'],
        'end_date': data['end_date'],
        'end_time': result,
        'price_per_hour': spot['price_per_hour']
    }
    await check_and_send_notifications(message.bot, data['spot_id'], start_dt, end_dt, spot_data)
    
    user = db.get_user_by_telegram_id(message.from_user.id)
    is_admin = user and user['role'] == 'admin'
    await message.answer("Выберите действие:", reply_markup=get_main_menu_keyboard(is_admin))


# ==================== SPOT BOOKINGS (for supplier) ====================

@router.callback_query(F.data.startswith("spot_bookings_"))
async def show_spot_bookings(callback: CallbackQuery, state: FSMContext):
    spot_id = int(callback.data.replace("spot_bookings_", ""))
    spot = db.get_spot_by_id(spot_id)
    
    if not spot:
        await callback.answer("❌ Место не найдено", show_alert=True)
        return
    
    # Получаем бронирования этого места
    bookings = []
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, u.full_name as customer_name, u.phone as customer_phone
            FROM bookings b
            JOIN users u ON b.customer_id = u.id
            WHERE b.spot_id = ? AND b.status IN ('pending', 'confirmed')
            ORDER BY b.start_time ASC
        ''', (spot_id,))
        bookings = [dict(row) for row in cursor.fetchall()]
    
    if not bookings:
        await callback.message.edit_text(
            f"📋 <b>Бронирования места {spot['spot_number']}</b>\n\n"
            f"Нет активных бронирований.",
            reply_markup=get_spot_actions_keyboard(spot_id),
            parse_mode="HTML"
        )
        return
    
    text = f"📋 <b>Бронирования места {spot['spot_number']}</b>\n\n"
    
    for b in bookings[:10]:
        start = datetime.fromisoformat(b['start_time'])
        end = datetime.fromisoformat(b['end_time'])
        status_emoji = '⏳' if b['status'] == 'pending' else '✅'
        
        text += (
            f"{status_emoji} <b>#{b['id']}</b>\n"
            f"👤 {b['customer_name']}\n"
            f"📞 {b['customer_phone']}\n"
            f"📅 {format_datetime(start)} - {format_datetime(end)}\n"
            f"💰 {b['total_price']}₽\n\n"
        )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_spot_actions_keyboard(spot_id),
        parse_mode="HTML"
    )
