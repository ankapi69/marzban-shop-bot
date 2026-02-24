import threading
import time
import signal
import sys
from loader import bot, db, marzban
from utils import keyboards
import handlers.user
import handlers.admin
from config import Config

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
                db.set_notified_expiry(u['user_id'], 1)
                try:
                    text = (
                        f"⏳ Ваша подписка истекает менее чем через сутки!\n\n"
                        f"💰 Ваш баланс: {u['balance']}₽"
                    )
                    bot.send_message(u['user_id'], text, reply_markup=keyboards.expiry_notification_menu())
                except Exception:
                    pass

            # 2. Подписка уже истекла
            for u in db.get_expired_users():
                user_id = u['user_id']
                
                cluster = db.get_user_cluster(user_id)
                if cluster:
                    db.change_cluster_users_count(cluster, -1)
                    db.set_user_cluster(user_id, None)
                    
                marzban.delete_user(user_id)
                db.set_notified_expiry(user_id, 2)
                
                try:
                    text = (
                        f"❌ Ваша подписка закончилась!\n\n"
                        f"💰 Ваш баланс: {u['balance']}₽"
                    )
                    bot.send_message(user_id, text, reply_markup=keyboards.expiry_notification_menu())
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ Ошибка проверки подписок: {e}")


def graceful_shutdown(signum, frame):
    print("\n🛑 Получен сигнал завершения. Сохраняем базу данных...")
    try:
        if db and db.conn:
            # Принудительно сбрасываем WAL журнал в основную БД перед закрытием
            db.cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            db.conn.commit()
            db.conn.close()
            print("✅ База данных успешно сохранена и закрыта.")
    except Exception as e:
        print(f"⚠️ Ошибка при закрытии БД: {e}")
    sys.exit(0)

if __name__ == "__main__":
    print("🚀 Запуск системы...")

    # Перехватываем сигналы остановки контейнера/скрипта (Ctrl+C, kill)
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Получаем юзернейм бота один раз при старте
    try:
        bot_info = bot.get_me()
        Config.BOT_USERNAME = bot_info.username
        print(f"🤖 Имя бота: @{Config.BOT_USERNAME}")
    except Exception as e:
        print(f"⚠️ Ошибка получения юзернейма бота: {e}")

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