"""
Клавиатуры ParkingBot
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from datetime import datetime, timedelta
from typing import List, Dict, Any

from config import BANKS
from utils import get_next_days, format_date


# ==================== REPLY KEYBOARDS ====================

def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню"""
    buttons = [
        [KeyboardButton(text="📅 Найти место"), KeyboardButton(text="➕ Добавить место")],
        [KeyboardButton(text="🏠 Мои места"), KeyboardButton(text="📋 Мои бронирования")],
        [KeyboardButton(text="🔔 Уведомления"), KeyboardButton(text="👤 Профиль")],
    ]
    
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


def get_cancel_menu_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с отменой и главным меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена"), KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True
    )


def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню администратора"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="🏠 Все места")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True
    )


# ==================== INLINE KEYBOARDS ====================

def get_banks_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора банка"""
    buttons = []
    for bank in BANKS:
        buttons.append([InlineKeyboardButton(text=bank, callback_data=f"bank_{bank}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_dates_keyboard(prefix: str = "date") -> InlineKeyboardMarkup:
    """Клавиатура выбора даты (6 ближайших дней)"""
    days = get_next_days(6)
    buttons = []
    
    for i in range(0, len(days), 2):
        row = [InlineKeyboardButton(text=days[i], callback_data=f"{prefix}_{days[i]}")]
        if i + 1 < len(days):
            row.append(InlineKeyboardButton(text=days[i+1], callback_data=f"{prefix}_{days[i+1]}"))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="📅 Ввести вручную", callback_data=f"{prefix}_manual")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_time_slots_keyboard(prefix: str = "time") -> InlineKeyboardMarkup:
    """Клавиатура выбора времени (слоты по 2 часа)"""
    buttons = []
    
    # Утро
    row1 = [
        InlineKeyboardButton(text="06:00", callback_data=f"{prefix}_06:00"),
        InlineKeyboardButton(text="08:00", callback_data=f"{prefix}_08:00"),
        InlineKeyboardButton(text="10:00", callback_data=f"{prefix}_10:00"),
    ]
    # День
    row2 = [
        InlineKeyboardButton(text="12:00", callback_data=f"{prefix}_12:00"),
        InlineKeyboardButton(text="14:00", callback_data=f"{prefix}_14:00"),
        InlineKeyboardButton(text="16:00", callback_data=f"{prefix}_16:00"),
    ]
    # Вечер
    row3 = [
        InlineKeyboardButton(text="18:00", callback_data=f"{prefix}_18:00"),
        InlineKeyboardButton(text="20:00", callback_data=f"{prefix}_20:00"),
        InlineKeyboardButton(text="22:00", callback_data=f"{prefix}_22:00"),
    ]
    # Ночь
    row4 = [
        InlineKeyboardButton(text="00:00", callback_data=f"{prefix}_00:00"),
        InlineKeyboardButton(text="02:00", callback_data=f"{prefix}_02:00"),
        InlineKeyboardButton(text="04:00", callback_data=f"{prefix}_04:00"),
    ]
    
    buttons = [row1, row2, row3, row4]
    buttons.append([InlineKeyboardButton(text="⌨️ Ввести вручную", callback_data=f"{prefix}_manual")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_yes_no_keyboard(prefix: str = "choice") -> InlineKeyboardMarkup:
    """Клавиатура Да/Нет"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"{prefix}_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"{prefix}_no")
        ]
    ])


def get_confirm_keyboard(prefix: str = "confirm") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{prefix}_yes"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"{prefix}_no")
        ]
    ])


def get_available_slots_keyboard(slots: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура доступных слотов"""
    buttons = []
    
    for slot in slots[:10]:  # Ограничиваем 10 слотами
        start = datetime.fromisoformat(slot['start_time'])
        end = datetime.fromisoformat(slot['end_time'])
        
        text = f"🏠 {slot['spot_number']} | {start.strftime('%H:%M')}-{end.strftime('%H:%M')} | {slot['price_per_hour']}₽/ч"
        buttons.append([InlineKeyboardButton(
            text=text, 
            callback_data=f"slot_{slot['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔔 Уведомить при появлении", callback_data="notify_available")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_no_slots_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура когда нет свободных мест"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомить при появлении", callback_data="notify_available")],
        [InlineKeyboardButton(text="📅 Выбрать другую дату", callback_data="search_again")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])


def get_user_spots_keyboard(spots: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура мест пользователя"""
    buttons = []
    
    for spot in spots:
        text = f"🏠 {spot['spot_number']} - {spot['price_per_hour']}₽/ч"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"myspot_{spot['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_spot_actions_keyboard(spot_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с местом"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Добавить слот", callback_data=f"add_slot_{spot_id}")],
        [InlineKeyboardButton(text="📋 Бронирования", callback_data=f"spot_bookings_{spot_id}")],
        [InlineKeyboardButton(text="🗑 Удалить место", callback_data=f"delete_spot_{spot_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="my_spots")]
    ])


def get_user_bookings_keyboard(bookings: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура бронирований пользователя"""
    buttons = []
    
    for booking in bookings[:10]:
        start = datetime.fromisoformat(booking['start_time'])
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌',
            'completed': '✔️'
        }.get(booking['status'], '❓')
        
        text = f"{status_emoji} {booking['spot_number']} | {start.strftime('%d.%m %H:%M')}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"booking_{booking['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_booking_actions_keyboard(booking_id: int, status: str) -> InlineKeyboardMarkup:
    """Клавиатура действий с бронированием"""
    buttons = []
    
    if status in ['pending', 'confirmed']:
        buttons.append([InlineKeyboardButton(
            text="❌ Отменить бронирование", 
            callback_data=f"cancel_booking_{booking_id}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_bookings")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_notifications_keyboard(notifications: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура уведомлений пользователя"""
    buttons = []
    
    for notif in notifications[:10]:
        date_text = notif['desired_date'] if notif['desired_date'] else "любая дата"
        text = f"🔔 {date_text}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"del_notif_{notif['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ADMIN KEYBOARDS ====================

def get_users_pagination_keyboard(users: List[Dict[str, Any]], page: int, 
                                   total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура пользователей с пагинацией"""
    buttons = []
    
    for user in users:
        # Определяем статус
        if user['role'] == 'admin':
            status = "👑"
        elif not user['is_active']:
            status = "🚫"
        else:
            status = "✅"
        
        username_part = f"(@{user['username']})" if user['username'] else ""
        text = f"{status} {user['full_name']} {username_part}"
        
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"admin_user_{user['id']}"
        )])
    
    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"users_page_{page-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"users_page_{page+1}"))
    
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_user_admin_actions_keyboard(user_id: int, user: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Клавиатура действий администратора над пользователем"""
    buttons = []
    
    # Контакты
    if user.get('phone'):
        buttons.append([InlineKeyboardButton(
            text="📞 Позвонить", 
            url=f"tel:{user['phone']}"
        )])
    
    if user.get('username'):
        buttons.append([InlineKeyboardButton(
            text="✉️ Написать",
            url=f"https://t.me/{user['username']}"
        )])
    
    # Управление ролью
    if user['role'] != 'admin':
        buttons.append([InlineKeyboardButton(
            text="👑 Сделать админом",
            callback_data=f"make_admin_{user_id}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="👤 Снять права админа",
            callback_data=f"remove_admin_{user_id}"
        )])
    
    # Блокировка
    if user['is_active']:
        buttons.append([InlineKeyboardButton(
            text="🚫 Заблокировать",
            callback_data=f"block_user_{user_id}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="✅ Разблокировать",
            callback_data=f"unblock_user_{user_id}"
        )])
    
    # Статистика
    buttons.append([InlineKeyboardButton(
        text="📊 Статистика",
        callback_data=f"user_stats_{user_id}"
    )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="users_page_0")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_spots_keyboard(spots: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура всех мест для админа"""
    buttons = []
    
    for spot in spots[:15]:
        text = f"🏠 {spot['spot_number']} - {spot.get('supplier_name', 'N/A')}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"admin_spot_{spot['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="📞 Изменить телефон", callback_data="edit_phone")],
        [InlineKeyboardButton(text="💳 Изменить карту", callback_data="edit_card")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])


def get_notify_options_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура опций уведомления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 На конкретную дату", callback_data="notify_date")],
        [InlineKeyboardButton(text="🔔 На любое свободное место", callback_data="notify_any")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
