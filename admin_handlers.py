"""
Обработчики админ-панели ParkingBot
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
    get_main_menu_keyboard, get_admin_menu_keyboard,
    get_users_pagination_keyboard, get_user_admin_actions_keyboard,
    get_admin_spots_keyboard, get_cancel_keyboard
)
from utils import mask_card, format_datetime
from config import ADMIN_PASSWORD

logger = logging.getLogger(__name__)
router = Router()

USERS_PER_PAGE = 10


class AdminStates(StatesGroup):
    waiting_password = State()
    waiting_broadcast_message = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь: /start")
        return
    
    session = db.get_admin_session(message.from_user.id)
    
    if session or user['role'] == 'admin':
        db.update_admin_session_activity(message.from_user.id)
        await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")
    else:
        await message.answer("🔐 <b>Вход в админ-панель</b>\n\nВведите пароль:", reply_markup=get_cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AdminStates.waiting_password)


@router.message(AdminStates.waiting_password)
async def process_admin_password(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        user = db.get_user_by_telegram_id(message.from_user.id)
        is_admin = user and user['role'] == 'admin'
        await message.answer("Вход отменён.", reply_markup=get_main_menu_keyboard(is_admin))
        return
    
    if message.text == ADMIN_PASSWORD:
        user = db.get_user_by_telegram_id(message.from_user.id)
        if user['role'] != 'admin':
            db.set_user_role(user['id'], 'admin')
        db.create_admin_session(user['id'], message.from_user.id)
        await state.clear()
        await message.answer("✅ <b>Вход выполнен!</b>\n\n⚙️ <b>Админ-панель</b>", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")
        db.log_admin_action('admin_login', user_id=user['id'])
    else:
        await message.answer("❌ Неверный пароль. Попробуйте снова:")


@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user or user['role'] != 'admin':
        await message.answer("❌ У вас нет прав администратора.")
        return
    db.update_admin_session_activity(message.from_user.id)
    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")


@router.message(F.text == "👥 Пользователи")
async def show_users_list(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user or user['role'] != 'admin':
        await message.answer("❌ У вас нет прав администратора.")
        return
    await show_users_page(message, 0)


async def show_users_page(message_or_callback, page: int):
    total_users = db.get_users_count()
    total_pages = max(1, (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    users = db.get_all_users(limit=USERS_PER_PAGE, offset=page * USERS_PER_PAGE)
    text = f"👥 <b>Пользователи</b>\n\nВсего: {total_users}\nСтраница: {page + 1}/{total_pages}"
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=get_users_pagination_keyboard(users, page, total_pages), parse_mode="HTML")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=get_users_pagination_keyboard(users, page, total_pages), parse_mode="HTML")


@router.callback_query(F.data.startswith("users_page_"))
async def users_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.replace("users_page_", ""))
    await show_users_page(callback, page)


@router.callback_query(F.data.startswith("admin_user_"))
async def show_user_details(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("admin_user_", ""))
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        user = dict(row) if row else None
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    stats = db.get_user_statistics(user_id)
    role_text = {'user': '👤 Пользователь', 'supplier': '🏠 Поставщик', 'admin': '👑 Администратор'}.get(user['role'], '👤')
    status_text = "✅ Активен" if user['is_active'] else "🚫 Заблокирован"
    created = datetime.fromisoformat(user['created_at']) if user['created_at'] else datetime.now()
    
    await callback.message.edit_text(
        f"👤 <b>Пользователь #{user_id}</b>\n\n"
        f"📛 Имя: {user['full_name']}\n"
        f"📱 Username: @{user['username'] or 'нет'}\n"
        f"📞 Телефон: {user['phone']}\n"
        f"💳 Карта: {user['card_number']}\n"
        f"🏦 Банк: {user['bank']}\n"
        f"🎭 Роль: {role_text}\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Регистрация: {format_datetime(created)}\n\n"
        f"<b>📊 Статистика:</b>\n"
        f"📋 Бронирований: {stats['total_bookings']}\n"
        f"🏠 Мест: {stats['total_spots']}\n"
        f"💸 Потрачено: {stats['total_spent']}₽\n"
        f"💰 Заработано: {stats['total_earned']}₽",
        reply_markup=get_user_admin_actions_keyboard(user_id, user),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("make_admin_"))
async def make_admin(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("make_admin_", ""))
    db.set_user_role(user_id, 'admin')
    await callback.answer("✅ Пользователь стал администратором")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = dict(cursor.fetchone())
    
    await callback.message.edit_reply_markup(reply_markup=get_user_admin_actions_keyboard(user_id, user))


@router.callback_query(F.data.startswith("remove_admin_"))
async def remove_admin(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("remove_admin_", ""))
    current_user = db.get_user_by_telegram_id(callback.from_user.id)
    
    if current_user['id'] == user_id:
        await callback.answer("❌ Нельзя снять права у себя", show_alert=True)
        return
    
    db.set_user_role(user_id, 'user')
    await callback.answer("✅ Права администратора сняты")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = dict(cursor.fetchone())
    
    await callback.message.edit_reply_markup(reply_markup=get_user_admin_actions_keyboard(user_id, user))


@router.callback_query(F.data.startswith("block_user_"))
async def block_user(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("block_user_", ""))
    current_user = db.get_user_by_telegram_id(callback.from_user.id)
    
    if current_user['id'] == user_id:
        await callback.answer("❌ Нельзя заблокировать себя", show_alert=True)
        return
    
    db.block_user(user_id)
    await callback.answer("✅ Пользователь заблокирован")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = dict(cursor.fetchone())
    
    await callback.message.edit_reply_markup(reply_markup=get_user_admin_actions_keyboard(user_id, user))


@router.callback_query(F.data.startswith("unblock_user_"))
async def unblock_user(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("unblock_user_", ""))
    db.unblock_user(user_id)
    await callback.answer("✅ Пользователь разблокирован")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = dict(cursor.fetchone())
    
    await callback.message.edit_reply_markup(reply_markup=get_user_admin_actions_keyboard(user_id, user))


@router.callback_query(F.data.startswith("user_stats_"))
async def show_user_stats(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("user_stats_", ""))
    stats = db.get_user_statistics(user_id)
    await callback.answer(
        f"📊 Бронирований: {stats['total_bookings']}\n"
        f"🏠 Мест: {stats['total_spots']}\n"
        f"💸 Потрачено: {stats['total_spent']}₽\n"
        f"💰 Заработано: {stats['total_earned']}₽",
        show_alert=True
    )


@router.message(F.text == "🏠 Все места")
async def show_all_spots(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user or user['role'] != 'admin':
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    spots = db.get_all_spots()
    
    if not spots:
        await message.answer("🏠 <b>Все места</b>\n\nМест пока нет.", parse_mode="HTML")
    else:
        await message.answer(f"🏠 <b>Все места</b>\n\nВсего: {len(spots)}", reply_markup=get_admin_spots_keyboard(spots), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_spot_"))
async def show_admin_spot_details(callback: CallbackQuery, state: FSMContext):
    spot_id = int(callback.data.replace("admin_spot_", ""))
    spot = db.get_spot_by_id(spot_id)
    
    if not spot:
        await callback.answer("❌ Место не найдено", show_alert=True)
        return
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT full_name, phone FROM users WHERE id = ?', (spot['supplier_id'],))
        supplier = dict(cursor.fetchone())
    
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
    
    await callback.message.edit_text(
        f"🏠 <b>Место: {spot['spot_number']}</b>\n\n"
        f"👤 Владелец: {supplier['full_name']}\n"
        f"📞 Телефон: {supplier['phone']}\n"
        f"💰 Цена: {spot['price_per_hour']}₽/час\n"
        f"🔄 Частичная аренда: {'✅' if spot['is_partial_allowed'] else '❌'}\n\n"
        f"<b>📅 Слоты:</b>{avail_text}",
        reply_markup=get_admin_spots_keyboard([]),
        parse_mode="HTML"
    )


@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user or user['role'] != 'admin':
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    stats = db.get_statistics()
    
    await message.answer(
        f"📊 <b>Статистика системы</b>\n\n"
        f"<b>👥 Пользователи:</b>\n"
        f"• Всего: {stats['total_users']}\n"
        f"• Админов: {stats['total_admins']}\n"
        f"• Сегодня: {stats['today_registrations']}\n\n"
        f"<b>🏠 Места:</b>\n"
        f"• Активных: {stats['total_spots']}\n\n"
        f"<b>📋 Бронирования:</b>\n"
        f"• Всего: {stats['total_bookings']}\n"
        f"• Ожидают: {stats['pending_bookings']}\n"
        f"• Подтверждено: {stats['confirmed_bookings']}\n"
        f"• Сегодня: {stats['today_bookings']}\n\n"
        f"<b>💰 Оборот:</b> {stats['total_revenue']}₽",
        parse_mode="HTML"
    )


@router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user or user['role'] != 'admin':
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    await message.answer(
        "📢 <b>Рассылка</b>\n\nВведите текст сообщения:\n(Поддерживается HTML)",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_broadcast_message)


@router.message(AdminStates.waiting_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Рассылка отменена.", reply_markup=get_admin_menu_keyboard())
        return
    
    broadcast_text = message.text
    users = db.get_all_users(limit=10000, offset=0)
    
    success_count = 0
    fail_count = 0
    
    status_message = await message.answer("📤 Отправка...")
    
    for user in users:
        try:
            await message.bot.send_message(user['telegram_id'], f"📢 <b>Объявление</b>\n\n{broadcast_text}", parse_mode="HTML")
            success_count += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {user['telegram_id']}: {e}")
            fail_count += 1
    
    await state.clear()
    await status_message.edit_text(f"✅ <b>Рассылка завершена!</b>\n\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}", parse_mode="HTML")
    await message.answer("Выберите действие:", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⚙️ <b>Админ-панель</b>", parse_mode="HTML")
    await callback.message.answer("Выберите действие:", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
