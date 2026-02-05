"""
База данных ParkingBot - SQLite
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """Контекстный менеджер для соединения с БД"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def init_database():
    """Инициализация базы данных"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                card_number TEXT NOT NULL,
                bank TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                balance REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица парковочных мест
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parking_spots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                spot_number TEXT NOT NULL,
                address TEXT,
                description TEXT,
                price_per_hour REAL NOT NULL,
                is_partial_allowed INTEGER DEFAULT 1,
                is_available INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица доступности мест
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spot_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_id INTEGER NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                is_booked INTEGER DEFAULT 0,
                booked_by INTEGER,
                booking_id INTEGER,
                FOREIGN KEY (spot_id) REFERENCES parking_spots (id),
                FOREIGN KEY (booked_by) REFERENCES users (id),
                FOREIGN KEY (booking_id) REFERENCES bookings (id),
                UNIQUE(spot_id, start_time, end_time)
            )
        ''')
        
        # Таблица бронирований
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                spot_id INTEGER NOT NULL,
                availability_id INTEGER,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                total_price REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                payment_status TEXT DEFAULT 'unpaid',
                payment_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES users (id),
                FOREIGN KEY (spot_id) REFERENCES parking_spots (id),
                FOREIGN KEY (availability_id) REFERENCES spot_availability (id)
            )
        ''')
        
        # Таблица уведомлений о свободных местах
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spot_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                spot_id INTEGER,
                desired_date DATE,
                start_time TIME,
                end_time TIME,
                notify_any INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (spot_id) REFERENCES parking_spots (id)
            )
        ''')
        
        # Таблица сессий админов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица логов админов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                user_id INTEGER,
                spot_id INTEGER,
                booking_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (spot_id) REFERENCES parking_spots (id),
                FOREIGN KEY (booking_id) REFERENCES bookings (id)
            )
        ''')
        
        # Создаём индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_spots_supplier_id ON parking_spots(supplier_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_spots_available ON parking_spots(is_available)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_availability_spot_id ON spot_availability(spot_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_availability_time ON spot_availability(start_time, end_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_availability_booked ON spot_availability(is_booked)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookings_customer ON bookings(customer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookings_spot ON bookings(spot_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON spot_notifications(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_active ON spot_notifications(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_logs_type ON admin_logs(action_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_logs_created ON admin_logs(created_at)')
        
        logger.info("Database initialized successfully")


# ==================== USER OPERATIONS ====================

def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Получить пользователя по telegram_id"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_user(telegram_id: int, username: str, full_name: str, 
                phone: str, card_number: str, bank: str) -> int:
    """Создать нового пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, username, full_name, phone, card_number, bank)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (telegram_id, username, full_name, phone, card_number, bank))
        user_id = cursor.lastrowid
        
        # Логируем действие
        log_admin_action('user_registered', user_id=user_id, 
                        details=json.dumps({'full_name': full_name, 'phone': phone}))
        
        return user_id


def update_user(user_id: int, **kwargs) -> bool:
    """Обновить данные пользователя"""
    allowed_fields = ['full_name', 'phone', 'card_number', 'bank', 'role', 'is_active', 'balance']
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not updates:
        return False
    
    set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [user_id]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        return cursor.rowcount > 0


def get_all_users(limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    """Получить всех пользователей с пагинацией"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?
        ''', (limit, offset))
        return [dict(row) for row in cursor.fetchall()]


def get_users_count() -> int:
    """Получить количество пользователей"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]


def get_admins() -> List[Dict[str, Any]]:
    """Получить всех администраторов"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE role = ?', ('admin',))
        return [dict(row) for row in cursor.fetchall()]


def set_user_role(user_id: int, role: str) -> bool:
    """Установить роль пользователя"""
    return update_user(user_id, role=role)


def block_user(user_id: int) -> bool:
    """Заблокировать пользователя"""
    return update_user(user_id, is_active=0)


def unblock_user(user_id: int) -> bool:
    """Разблокировать пользователя"""
    return update_user(user_id, is_active=1)


# ==================== PARKING SPOTS OPERATIONS ====================

def create_parking_spot(supplier_id: int, spot_number: str, price_per_hour: float,
                        is_partial_allowed: bool = True, address: str = None,
                        description: str = None) -> int:
    """Создать парковочное место"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO parking_spots 
            (supplier_id, spot_number, address, description, price_per_hour, is_partial_allowed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (supplier_id, spot_number, address, description, price_per_hour, int(is_partial_allowed)))
        spot_id = cursor.lastrowid
        
        # Логируем действие
        log_admin_action('spot_added', spot_id=spot_id, user_id=supplier_id,
                        details=json.dumps({'spot_number': spot_number, 'price': price_per_hour}))
        
        return spot_id


def create_spot_availability(spot_id: int, start_time: datetime, end_time: datetime) -> int:
    """Создать слот доступности для места"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO spot_availability (spot_id, start_time, end_time)
            VALUES (?, ?, ?)
        ''', (spot_id, start_time.strftime("%Y-%m-%d %H:%M:%S"), 
              end_time.strftime("%Y-%m-%d %H:%M:%S")))
        return cursor.lastrowid


def get_user_spots(user_id: int) -> List[Dict[str, Any]]:
    """Получить места пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM parking_spots WHERE supplier_id = ? AND is_available = 1
            ORDER BY created_at DESC
        ''', (user_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_user_spots_count(user_id: int) -> int:
    """Получить количество мест пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM parking_spots WHERE supplier_id = ? AND is_available = 1
        ''', (user_id,))
        return cursor.fetchone()[0]


def get_spot_by_id(spot_id: int) -> Optional[Dict[str, Any]]:
    """Получить место по ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM parking_spots WHERE id = ?', (spot_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_spots() -> List[Dict[str, Any]]:
    """Получить все места"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ps.*, u.full_name as supplier_name 
            FROM parking_spots ps
            JOIN users u ON ps.supplier_id = u.id
            WHERE ps.is_available = 1
            ORDER BY ps.created_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]


def delete_spot(spot_id: int) -> bool:
    """Удалить (скрыть) место"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE parking_spots SET is_available = 0 WHERE id = ?', (spot_id,))
        return cursor.rowcount > 0


# ==================== AVAILABILITY & SEARCH ====================

def get_available_slots(date_str: str = None, start_time: str = None, 
                        end_time: str = None) -> List[Dict[str, Any]]:
    """Найти свободные слоты"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT sa.*, ps.spot_number, ps.price_per_hour, ps.is_partial_allowed,
                   ps.address, ps.description, u.full_name as supplier_name,
                   u.card_number, u.bank
            FROM spot_availability sa
            JOIN parking_spots ps ON sa.spot_id = ps.id
            JOIN users u ON ps.supplier_id = u.id
            WHERE sa.is_booked = 0 AND ps.is_available = 1
        '''
        params = []
        
        if date_str:
            query += ' AND DATE(sa.start_time) = ?'
            params.append(date_str)
        
        query += ' AND sa.end_time > datetime("now")'
        query += ' ORDER BY sa.start_time ASC'
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_availability_by_id(availability_id: int) -> Optional[Dict[str, Any]]:
    """Получить слот доступности по ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sa.*, ps.spot_number, ps.price_per_hour, ps.is_partial_allowed,
                   ps.address, ps.supplier_id, u.full_name as supplier_name,
                   u.card_number, u.bank, u.telegram_id as supplier_telegram_id
            FROM spot_availability sa
            JOIN parking_spots ps ON sa.spot_id = ps.id
            JOIN users u ON ps.supplier_id = u.id
            WHERE sa.id = ?
        ''', (availability_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_spot_availabilities(spot_id: int) -> List[Dict[str, Any]]:
    """Получить все слоты доступности для места"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM spot_availability 
            WHERE spot_id = ? AND is_booked = 0 AND end_time > datetime("now")
            ORDER BY start_time ASC
        ''', (spot_id,))
        return [dict(row) for row in cursor.fetchall()]


# ==================== BOOKING OPERATIONS ====================

def create_booking(customer_id: int, spot_id: int, availability_id: int,
                   start_time: datetime, end_time: datetime, total_price: float) -> int:
    """Создать бронирование"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Создаём бронирование
        cursor.execute('''
            INSERT INTO bookings 
            (customer_id, spot_id, availability_id, start_time, end_time, total_price)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (customer_id, spot_id, availability_id,
              start_time.strftime("%Y-%m-%d %H:%M:%S"),
              end_time.strftime("%Y-%m-%d %H:%M:%S"), total_price))
        booking_id = cursor.lastrowid
        
        # Обновляем статус слота
        cursor.execute('''
            UPDATE spot_availability 
            SET is_booked = 1, booked_by = ?, booking_id = ?
            WHERE id = ?
        ''', (customer_id, booking_id, availability_id))
        
        # Логируем действие
        log_admin_action('booking_created', booking_id=booking_id, user_id=customer_id,
                        spot_id=spot_id, details=json.dumps({'total_price': total_price}))
        
        return booking_id


def get_booking_by_id(booking_id: int) -> Optional[Dict[str, Any]]:
    """Получить бронирование по ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, ps.spot_number, ps.price_per_hour,
                   u.full_name as customer_name, u.phone as customer_phone,
                   supplier.full_name as supplier_name, supplier.card_number,
                   supplier.bank, supplier.telegram_id as supplier_telegram_id
            FROM bookings b
            JOIN parking_spots ps ON b.spot_id = ps.id
            JOIN users u ON b.customer_id = u.id
            JOIN users supplier ON ps.supplier_id = supplier.id
            WHERE b.id = ?
        ''', (booking_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_bookings(user_id: int, status: str = None) -> List[Dict[str, Any]]:
    """Получить бронирования пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT b.*, ps.spot_number, ps.address,
                   supplier.full_name as supplier_name, supplier.card_number, supplier.bank
            FROM bookings b
            JOIN parking_spots ps ON b.spot_id = ps.id
            JOIN users supplier ON ps.supplier_id = supplier.id
            WHERE b.customer_id = ?
        '''
        params = [user_id]
        
        if status:
            query += ' AND b.status = ?'
            params.append(status)
        
        query += ' ORDER BY b.created_at DESC'
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_supplier_bookings(supplier_id: int) -> List[Dict[str, Any]]:
    """Получить бронирования мест поставщика"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, ps.spot_number, u.full_name as customer_name, u.phone as customer_phone
            FROM bookings b
            JOIN parking_spots ps ON b.spot_id = ps.id
            JOIN users u ON b.customer_id = u.id
            WHERE ps.supplier_id = ? AND b.status IN ('pending', 'confirmed')
            ORDER BY b.start_time ASC
        ''', (supplier_id,))
        return [dict(row) for row in cursor.fetchall()]


def cancel_booking(booking_id: int) -> bool:
    """Отменить бронирование"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем бронирование
        cursor.execute('SELECT availability_id FROM bookings WHERE id = ?', (booking_id,))
        row = cursor.fetchone()
        if not row:
            return False
        
        availability_id = row[0]
        
        # Обновляем статус бронирования
        cursor.execute('''
            UPDATE bookings SET status = 'cancelled' WHERE id = ?
        ''', (booking_id,))
        
        # Освобождаем слот
        cursor.execute('''
            UPDATE spot_availability 
            SET is_booked = 0, booked_by = NULL, booking_id = NULL
            WHERE id = ?
        ''', (availability_id,))
        
        log_admin_action('booking_cancelled', booking_id=booking_id)
        
        return True


def get_active_bookings_count(user_id: int) -> int:
    """Получить количество активных бронирований пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM bookings 
            WHERE customer_id = ? AND status IN ('pending', 'confirmed')
        ''', (user_id,))
        return cursor.fetchone()[0]


# ==================== NOTIFICATIONS ====================

def create_spot_notification(user_id: int, desired_date: str = None,
                            start_time: str = None, end_time: str = None,
                            spot_id: int = None, notify_any: bool = True) -> int:
    """Создать подписку на уведомление о свободном месте"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO spot_notifications 
            (user_id, spot_id, desired_date, start_time, end_time, notify_any)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, spot_id, desired_date, start_time, end_time, int(notify_any)))
        return cursor.lastrowid


def get_active_notifications() -> List[Dict[str, Any]]:
    """Получить все активные подписки на уведомления"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sn.*, u.telegram_id
            FROM spot_notifications sn
            JOIN users u ON sn.user_id = u.id
            WHERE sn.is_active = 1
        ''')
        return [dict(row) for row in cursor.fetchall()]


def get_matching_notifications(spot_id: int, start_time: datetime, 
                              end_time: datetime) -> List[Dict[str, Any]]:
    """Найти подписки, соответствующие новому слоту"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        date_str = start_time.strftime("%Y-%m-%d")
        start_time_str = start_time.strftime("%H:%M:%S")
        end_time_str = end_time.strftime("%H:%M:%S")
        
        cursor.execute('''
            SELECT sn.*, u.telegram_id
            FROM spot_notifications sn
            JOIN users u ON sn.user_id = u.id
            WHERE sn.is_active = 1
            AND (sn.notify_any = 1 OR sn.spot_id = ?)
            AND (sn.desired_date IS NULL OR sn.desired_date = ?)
            AND (sn.start_time IS NULL OR sn.start_time <= ?)
            AND (sn.end_time IS NULL OR sn.end_time >= ?)
        ''', (spot_id, date_str, end_time_str, start_time_str))
        return [dict(row) for row in cursor.fetchall()]


def deactivate_notification(notification_id: int) -> bool:
    """Деактивировать подписку"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE spot_notifications SET is_active = 0 WHERE id = ?
        ''', (notification_id,))
        return cursor.rowcount > 0


def get_user_notifications(user_id: int) -> List[Dict[str, Any]]:
    """Получить активные подписки пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM spot_notifications 
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
        ''', (user_id,))
        return [dict(row) for row in cursor.fetchall()]


# ==================== ADMIN OPERATIONS ====================

def create_admin_session(user_id: int, telegram_id: int) -> int:
    """Создать сессию администратора"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Удаляем старые сессии этого пользователя
        cursor.execute('DELETE FROM admin_sessions WHERE telegram_id = ?', (telegram_id,))
        
        cursor.execute('''
            INSERT INTO admin_sessions (user_id, telegram_id)
            VALUES (?, ?)
        ''', (user_id, telegram_id))
        return cursor.lastrowid


def get_admin_session(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Получить сессию администратора"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM admin_sessions WHERE telegram_id = ?
        ''', (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_admin_session_activity(telegram_id: int) -> bool:
    """Обновить время последней активности"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE admin_sessions SET last_activity = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
        ''', (telegram_id,))
        return cursor.rowcount > 0


def delete_admin_session(telegram_id: int) -> bool:
    """Удалить сессию администратора"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM admin_sessions WHERE telegram_id = ?', (telegram_id,))
        return cursor.rowcount > 0


def get_active_admin_sessions() -> List[Dict[str, Any]]:
    """Получить все активные сессии админов"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT as_s.*, u.full_name, u.telegram_id
            FROM admin_sessions as_s
            JOIN users u ON as_s.user_id = u.id
            WHERE datetime(as_s.last_activity, '+24 hours') > datetime('now')
        ''')
        return [dict(row) for row in cursor.fetchall()]


def log_admin_action(action_type: str, user_id: int = None, spot_id: int = None,
                     booking_id: int = None, details: str = None):
    """Записать действие в лог"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_logs (action_type, user_id, spot_id, booking_id, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (action_type, user_id, spot_id, booking_id, details))


def get_admin_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Получить логи действий"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]


# ==================== STATISTICS ====================

def get_statistics() -> Dict[str, Any]:
    """Получить общую статистику"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        stats = {}
        
        cursor.execute('SELECT COUNT(*) FROM users')
        stats['total_users'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
        stats['total_admins'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM parking_spots WHERE is_available = 1')
        stats['total_spots'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM bookings')
        stats['total_bookings'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM bookings WHERE status = "pending"')
        stats['pending_bookings'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM bookings WHERE status = "confirmed"')
        stats['confirmed_bookings'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COALESCE(SUM(total_price), 0) FROM bookings WHERE status = "confirmed"')
        stats['total_revenue'] = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM users 
            WHERE DATE(created_at) = DATE("now")
        ''')
        stats['today_registrations'] = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM bookings 
            WHERE DATE(created_at) = DATE("now")
        ''')
        stats['today_bookings'] = cursor.fetchone()[0]
        
        return stats


def get_user_statistics(user_id: int) -> Dict[str, Any]:
    """Получить статистику пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        stats = {}
        
        cursor.execute('SELECT COUNT(*) FROM bookings WHERE customer_id = ?', (user_id,))
        stats['total_bookings'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM parking_spots WHERE supplier_id = ? AND is_available = 1', (user_id,))
        stats['total_spots'] = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COALESCE(SUM(total_price), 0) FROM bookings 
            WHERE customer_id = ? AND status = "confirmed"
        ''', (user_id,))
        stats['total_spent'] = cursor.fetchone()[0]
        
        # Доход как поставщик
        cursor.execute('''
            SELECT COALESCE(SUM(b.total_price), 0) 
            FROM bookings b
            JOIN parking_spots ps ON b.spot_id = ps.id
            WHERE ps.supplier_id = ? AND b.status = "confirmed"
        ''', (user_id,))
        stats['total_earned'] = cursor.fetchone()[0]
        
        return stats
