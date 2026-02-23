from loader import bot
from config import Config
from datetime import datetime


def notify_payment(user_id, amount, method, username=None):
    """
    Отправляет уведомление об успешном пополнении в канал постбэков.
    Тихо игнорирует ошибки, чтобы не ломать основной флоу.
    """
    chat_id = Config.POSTBACK_CHAT_ID
    if not chat_id:
        return

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    user_tag = f"@{username}" if username else "—"

    text = (
        "💰 <b>Пополнение баланса</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Пользователь: {user_tag} (ID: <code>{user_id}</code>)\n"
        f"💳 Способ: <b>{method}</b>\n"
        f"💵 Сумма: <b>{amount}₽</b>\n"
        f"🕐 Время: {now}\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    try:
        bot.send_message(int(chat_id), text, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Не удалось отправить постбэк: {e}")
