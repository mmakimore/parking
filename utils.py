"""
Утилиты и валидация ParkingBot
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

# Регулярные выражения для валидации
PHONE_REGEX = r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
CARD_REGEX = r'^[0-9]{16}$'
DATE_REGEX = r'^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.(20[2-9][0-9])$'
TIME_REGEX = r'^([01][0-9]|2[0-3]):([0-5][0-9])$'


def validate_name(name: str) -> Tuple[bool, str]:
    """Валидация имени и фамилии"""
    name = name.strip()
    if len(name) < 2:
        return False, "❌ Имя слишком короткое. Минимум 2 символа."
    if len(name) > 50:
        return False, "❌ Имя слишком длинное. Максимум 50 символов."
    return True, name


def validate_phone(phone: str) -> Tuple[bool, str]:
    """Валидация и нормализация телефона"""
    # Убираем все кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if not re.match(PHONE_REGEX, phone):
        return False, "❌ Неверный формат телефона. Введите в формате +7XXXXXXXXXX или 8XXXXXXXXXX"
    
    # Нормализуем к формату 8XXXXXXXXXX
    if cleaned.startswith('+7'):
        cleaned = '8' + cleaned[2:]
    elif cleaned.startswith('7') and len(cleaned) == 11:
        cleaned = '8' + cleaned[1:]
    
    if len(cleaned) != 11:
        return False, "❌ Номер телефона должен содержать 11 цифр"
    
    return True, cleaned


def luhn_check(card_number: str) -> bool:
    """Проверка номера карты алгоритмом Луна"""
    digits = [int(d) for d in card_number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    
    total = sum(odd_digits)
    for d in even_digits:
        d = d * 2
        if d > 9:
            d = d - 9
        total += d
    
    return total % 10 == 0


def validate_card(card: str) -> Tuple[bool, str]:
    """Валидация номера карты"""
    # Убираем пробелы и другие символы
    cleaned = re.sub(r'\D', '', card)
    
    if not re.match(CARD_REGEX, cleaned):
        return False, "❌ Номер карты должен содержать 16 цифр"
    
    if not luhn_check(cleaned):
        return False, "❌ Неверный номер карты. Проверьте правильность ввода."
    
    return True, cleaned


def validate_date(date_str: str) -> Tuple[bool, Optional[datetime]]:
    """Валидация даты в формате ДД.ММ.ГГГГ"""
    if not re.match(DATE_REGEX, date_str):
        return False, None
    
    try:
        parsed = datetime.strptime(date_str, "%d.%m.%Y")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if parsed < today:
            return False, None
        
        return True, parsed
    except ValueError:
        return False, None


def validate_time(time_str: str) -> Tuple[bool, Optional[str]]:
    """Валидация времени в формате ЧЧ:ММ"""
    if not re.match(TIME_REGEX, time_str):
        return False, None
    return True, time_str


def validate_price(price_str: str) -> Tuple[bool, float]:
    """Валидация цены"""
    try:
        price = float(price_str.replace(',', '.'))
        if price <= 0:
            return False, 0
        if price > 10000:
            return False, 0
        return True, price
    except ValueError:
        return False, 0


def validate_spot_number(spot_number: str) -> Tuple[bool, str]:
    """Валидация номера парковочного места"""
    spot_number = spot_number.strip()
    if len(spot_number) < 1:
        return False, "❌ Номер места не может быть пустым"
    if len(spot_number) > 10:
        return False, "❌ Номер места слишком длинный. Максимум 10 символов."
    return True, spot_number


def format_datetime(dt: datetime) -> str:
    """Форматирование даты и времени"""
    return dt.strftime("%d.%m.%Y %H:%M")


def format_date(dt: datetime) -> str:
    """Форматирование только даты"""
    return dt.strftime("%d.%m.%Y")


def format_time(dt: datetime) -> str:
    """Форматирование только времени"""
    return dt.strftime("%H:%M")


def parse_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """Парсинг даты и времени"""
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def get_next_days(count: int = 6) -> list:
    """Получить список ближайших дней"""
    today = datetime.now()
    days = []
    for i in range(count):
        day = today + timedelta(days=i)
        days.append(day.strftime("%d.%m.%Y"))
    return days


def get_time_slots() -> list:
    """Получить временные слоты по 2 часа"""
    slots = []
    for hour in range(0, 24, 2):
        start = f"{hour:02d}:00"
        end = f"{(hour + 2) % 24:02d}:00"
        slots.append(f"{start}-{end}")
    return slots


def calculate_price(price_per_hour: float, start: datetime, end: datetime) -> float:
    """Расчет стоимости бронирования"""
    duration = (end - start).total_seconds() / 3600  # часы
    return round(price_per_hour * duration, 2)


def mask_card(card_number: str) -> str:
    """Маскировка номера карты (показать только последние 4 цифры)"""
    if len(card_number) >= 4:
        return f"****{card_number[-4:]}"
    return "****"


def get_weekday_name(dt: datetime) -> str:
    """Получить название дня недели"""
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return days[dt.weekday()]
