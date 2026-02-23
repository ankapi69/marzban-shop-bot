import threading
import time
from loader import bot, db
from utils import keyboards
import handlers.user
import handlers.admin

from services.server import run_server

# Интервал проверки подписок (в секундах): 4 часа
SUB_CHECK_INTERVAL = 4 * 3600

def subscription_checker():
    """Фоновый поток: уведомляет пользователей об истечении подписки"""
    while True:
        time.sleep(SUB_CHECK_INTERVAL)
        try:
            # 1. Подписка истекает в течение 24 часов
            for u in db.get_expiring_users(86400):
                try:
                    text = (
                        f"⏳ Ваша подписка истекает менее чем через сутки!\n\n"
                        f"💰 Ваш баланс: {u['balance']}₽"
                    )
                    bot.send_message(u['user_id'], text, reply_markup=keyboards.expiry_notification_menu())
                    db.set_notified_expiry(u['user_id'], 1)
                except Exception:
                    pass

            # 2. Подписка уже истекла
            for u in db.get_expired_users():
                try:
                    text = (
                        f"❌ Ваша подписка закончилась!\n\n"
                        f"💰 Ваш баланс: {u['balance']}₽"
                    )
                    bot.send_message(u['user_id'], text, reply_markup=keyboards.expiry_notification_menu())
                    db.set_notified_expiry(u['user_id'], 2)
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ Ошибка проверки подписок: {e}")


if __name__ == "__main__":
    print("🚀 Запуск системы...")

    # Запускаем Flask-сервер для вебхуков Lava в фоне
    flask_thread = threading.Thread(target=run_server, daemon=True)
    flask_thread.start()
    print("🌍 Webhook-сервер запущен (фоном)")

    # Запускаем проверку подписок в фоне
    sub_thread = threading.Thread(target=subscription_checker, daemon=True)
    sub_thread.start()
    print("🔔 Проверка подписок запущена (каждые 4ч)")

    # Запускаем бота
    print("🤖 Бот запущен и слушает сообщения...")
    bot.infinity_polling()