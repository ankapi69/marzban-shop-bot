import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "vpn_bot")
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
    
    # Marzban
    MARZBAN_URL = os.getenv("MARZBAN_URL", "").strip().rstrip('/')
    MARZBAN_LOGIN = os.getenv("MARZBAN_LOGIN")
    MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD")
    
    # Платежи
    CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
    
    # База данных
    DB_PATH = "vpn_bot.db"

    # Настройки LAVA
    LAVA_PROJECT_ID = os.getenv('LAVA_PROJECT_ID')
    LAVA_SECRET_KEY = os.getenv('LAVA_SECRET_KEY')          # Секретный (Верхний)
    LAVA_ADDITIONAL_KEY = os.getenv('LAVA_ADDITIONAL_KEY')  # Дополнительный (Нижний)
    
    # URL для вебхуков (ngrok или домен, обязательно https)
    BASE_URL = os.getenv("BASE_URL", "").strip().rstrip('/')
    
    # Канал для уведомлений о платежах (ID с минусом, например -1001234567890)
    POSTBACK_CHAT_ID = os.getenv('POSTBACK_CHAT_ID')
    SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', 'ankapi69')