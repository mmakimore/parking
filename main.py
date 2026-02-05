"""
ParkingBot - Telegram-бот для аренды парковочных мест
Точка входа приложения
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, DATABASE_PATH
from database import Database
import user_handlers
import admin_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальная переменная для бота (для фоновых задач)
bot_instance: Bot = None
db_instance = None


async def set_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🚀 Начать работу / Регистрация"),
        BotCommand(command="admin", description="👑 Админ-панель"),
        BotCommand(command="help", description="❓ Помощь"),
    ]
    await bot.set_my_commands(commands)


async def cleanup_old_data():
    """Очистка старых данных"""
    try:
        if not db_instance:
            return
            
        # Помечаем старые бронирования как завершённые
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Используем существующие методы базы данных
        all_bookings = db_instance.get_all_bookings(limit=1000)
        for booking in all_bookings:
            if booking['status'] == 'confirmed':
                try:
                    booking_time = datetime.fromisoformat(booking['end_time'])
                    if booking_time < datetime.now() - timedelta(days=30):
                        db_instance.update_booking_status(booking['id'], 'completed')
                except Exception as e:
                    logger.error(f"Error processing booking {booking['id']}: {e}")
        
        logger.info("Old data cleanup completed")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


async def check_pending_bookings():
    """Проверка просроченных бронирований"""
    try:
        if not db_instance or not bot_instance:
            return
        
        # Находим бронирования старше 24 часов в статусе pending
        all_bookings = db_instance.get_all_bookings(status='pending', limit=1000)
        
        cancelled_count = 0
        for booking in all_bookings:
            try:
                created_time = datetime.fromisoformat(booking['created_at'])
                if created_time < datetime.now() - timedelta(hours=24):
                    # Отменяем бронирование
                    db_instance.update_booking_status(booking['id'], 'cancelled')
                    cancelled_count += 1
                    
                    # Получаем пользователя для уведомления
                    booking_details = db_instance.get_booking(booking['id'])
                    if booking_details:
                        user = db_instance.get_user_by_id(booking_details['customer_id'])
                        if user:
                            try:
                                await bot_instance.send_message(
                                    user['telegram_id'],
                                    f"❌ <b>Бронирование отменено</b>\n\n"
                                    f"Бронирование #{booking['id']} отменено из-за отсутствия оплаты в течение 24 часов.",
                                    parse_mode="HTML"
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify user {user['telegram_id']}: {e}")
            except Exception as e:
                logger.error(f"Error processing booking {booking.get('id', 'unknown')}: {e}")
        
        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} expired bookings")
                
    except Exception as e:
        logger.error(f"Pending bookings check error: {e}")


async def background_tasks():
    """Фоновые задачи"""
    while True:
        try:
            await asyncio.sleep(300)  # Каждые 5 минут
            
            await cleanup_old_data()
            await check_pending_bookings()
            
        except asyncio.CancelledError:
            logger.info("Background tasks cancelled")
            break
        except Exception as e:
            logger.error(f"Background task error: {e}")
            await asyncio.sleep(60)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    global bot_instance, db_instance
    bot_instance = bot
    
    logger.info("Bot is starting...")
    
    # Инициализация БД
    db_instance = Database(DATABASE_PATH)
    db_instance.init_database()  # Синхронный метод
    logger.info("Database initialized")
    
    # Установка команд бота
    await set_bot_commands(bot)
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")
    
    # Запускаем фоновые задачи
    asyncio.create_task(background_tasks())
    logger.info("Background tasks started")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Bot is shutting down...")
    global bot_instance, db_instance
    bot_instance = None
    db_instance = None


async def main():
    """Главная функция запуска бота"""
    
    # Проверяем токен
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Bot token is not set! Please set BOT_TOKEN in .env file")
        print("❌ ОШИБКА: Токен бота не установлен!")
        print("👉 Проверьте файл .env или переменные окружения BotHost")
        print(f"👉 Текущий токен: {BOT_TOKEN[:10]}...")
        sys.exit(1)
    
    # Создаём бота и диспетчер
    try:
        bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
        logger.info("Bot instance created successfully")
    except Exception as e:
        logger.error(f"Failed to create bot instance: {e}")
        print(f"❌ ОШИБКА создания бота: {e}")
        sys.exit(1)
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    
    # Регистрируем хуки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        # Удаляем вебхук если был
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем polling
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
        print(f"❌ ОШИБКА polling: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"Bot startup error: {e}")
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
