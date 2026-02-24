from telebot import types
from config import Config

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("👤 Кабинет"), types.KeyboardButton("📱 Как подключить?"))
    kb.add(types.KeyboardButton("🤝 Реферальная система"), types.KeyboardButton("🎁 Промокод"))
    kb.add(types.KeyboardButton("ℹ️ Информация"))
    return kb

# --- МЕНЮ КАБИНЕТА ---
def cabinet_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="cabinet_buy_balance"))
    kb.add(types.InlineKeyboardButton("⚡️ Купить подписку", callback_data="choose_tariff"))
    kb.add(types.InlineKeyboardButton("🎁 Подарить подписку", callback_data="choose_gift_tariff"))
    return kb

# --- ВЫБОР ТАРИФА ---
def tariff_select_menu(tariffs, mode="buy"):
    """
    Генерирует кнопки выбора тарифа.
    mode='buy' — покупка, mode='gift' — подарок.
    tariffs: {days: price, ...}
    """
    kb = types.InlineKeyboardMarkup(row_width=1)
    prefix = "tbuy" if mode == "buy" else "tgift"
    for days, price in tariffs.items():
        label = format_days(days)
        kb.add(types.InlineKeyboardButton(f"⚡ {label} — {price}₽", callback_data=f"{prefix}_{days}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="cancel_buy"))
    return kb

def format_days(days):
    """Красиво форматирует количество дней"""
    days = int(days)
    if days == 365:
        return "1 год"
    elif days == 30:
        return "1 месяц"
    elif days == 90:
        return "3 месяца"
    elif days == 180:
        return "6 месяцев"
    elif days == 7:
        return "7 дней"
    elif days == 14:
        return "14 дней"
    else:
        return f"{days} дн."

# --- ПОДТВЕРЖДЕНИЕ ПОКУПКИ ---
def confirm_buy_menu(days, price):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Да, купить", callback_data=f"buy_{days}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_buy")
    )
    return kb

# --- ПОДТВЕРЖДЕНИЕ ПОДАРКА ---
def confirm_gift_menu(days, price):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Да, подарить", callback_data=f"gift_{days}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_buy")
    )
    return kb

# --- МЕНЮ ПОДАРКА ---
def gift_share_menu(share_url):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📤 Отправить другу", url=share_url))
    return kb

# --- МЕНЮ ОПЛАТЫ ---
def pay_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💳 Карты РФ (Lava)", callback_data="top_up"))
    kb.add(types.InlineKeyboardButton("💎 CryptoBot (USDT/TON/BTC)", callback_data="pay_crypto"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="cancel_buy"))
    return kb

def cancel_action_menu():
    """Инлайн-кнопка отмены для пользовательских действий (оплата и т.д.)"""
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_pay"))
    return kb

# --- ИНФО ССЫЛКИ ---

def info_links():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📜 Пользовательское соглашение", url="https://telegra.ph/Polzovatelskoe-soglashenie-02-16-25"),
        types.InlineKeyboardButton("🔒 Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-08-15-17"),
        types.InlineKeyboardButton("👨‍💻 Связь с поддержкой", url=f"https://t.me/{Config.SUPPORT_USERNAME}")
    )
    return kb

# --- АДМИНСКОЕ МЕНЮ ---
def admin_menu(current_price=150, trial_days=0, ref_percent=20, min_topup=10):
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    # === БЛОК 0: Дашборд ===
    kb.add(types.InlineKeyboardButton("📊 Статистика", callback_data="admin_dashboard"))
    
    # === БЛОК 1: Управление продажами & Кластеры ===
    kb.add(
        types.InlineKeyboardButton("🔧 Управление продажами", callback_data="admin_sales_menu"),
        types.InlineKeyboardButton("🌐 Кластеры", callback_data="admin_cluster_menu")
    )
    
    kb.add(
        types.InlineKeyboardButton("📋 Тарифы", callback_data="admin_tariffs"),
        types.InlineKeyboardButton(f"💸 Реф. процент ({ref_percent}%)", callback_data="admin_change_ref_percent")
    )
    
    kb.add(
        types.InlineKeyboardButton(f"🎁 Триал ({trial_days} дн.)", callback_data="admin_change_trial"),
        types.InlineKeyboardButton(f"💵 Мин. пополнение ({min_topup}₽)", callback_data="admin_change_min_topup")
    )
    
    # === БЛОК 2: Управление Пользователями ===
    kb.add(types.InlineKeyboardButton("💰 Выдать баланс", callback_data="admin_give_balance"))
    kb.add(types.InlineKeyboardButton("🎫 Выдать подписку", callback_data="admin_grant_sub"))
    
    # === БЛОК 3: Промокоды ===
    kb.add(types.InlineKeyboardButton("🎫 Промокоды", callback_data="admin_promo_menu"))
    
    # === БЛОК 4: Рассылка ===
    kb.add(types.InlineKeyboardButton("📢 Сделать рассылку всем", callback_data="admin_broadcast"))
    
    # === БЛОК 5: Экспорт ===
    kb.add(
        types.InlineKeyboardButton("📥 Excel", callback_data="admin_export_db"),
        types.InlineKeyboardButton("📥 .db файл", callback_data="admin_export_raw")
    )
    
    return kb

def admin_promo_menu():
    """Отдельное меню управления промокодами"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎫 Создать", callback_data="admin_create_promo"),
        types.InlineKeyboardButton("📋 Список", callback_data="admin_list_promo")
    )
    kb.add(
        types.InlineKeyboardButton("❌ Удалить код", callback_data="admin_del_one_promo"),
        types.InlineKeyboardButton("🗑 Очистить неактивные", callback_data="admin_clear_inactive_promos")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_back"))
    return kb

# Ключи настроек продаж и их отображаемые названия
SALES_TOGGLES = {
    "sell_subs":   "⚡ Подписки",
    "sell_gifts":  "🎁 Подарки",
    "sell_lava":   "💳 Lava (RUB)",
    "sell_crypto": "💎 CryptoBot",
}

def sales_control_menu(db_ref):
    """Меню управления продажами с индивидуальными переключателями"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for key, label in SALES_TOGGLES.items():
        is_on = db_ref.get_setting(key, "1") == "1"
        status = "✅" if is_on else "❌"
        kb.add(types.InlineKeyboardButton(f"{status} {label}", callback_data=f"toggle_{key}"))
    
    kb.add(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back"))
    return kb

def cancel_admin_action():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_cancel"))
    return kb

def confirm_broadcast_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Отправить", callback_data="admin_confirm_broadcast"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")
    )
    return kb

# --- БЫСТРЫЕ СУММЫ ПОПОЛНЕНИЯ ---
QUICK_AMOUNTS = [50, 100, 200, 500]

def quick_amount_menu(method):
    """Кнопки быстрого выбора суммы + ручной ввод. method: 'lava' или 'crypto'"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    for amt in QUICK_AMOUNTS:
        kb.add(types.InlineKeyboardButton(f"{amt}₽", callback_data=f"qamt_{method}_{amt}"))
    kb.add(types.InlineKeyboardButton("✏️ Своя сумма", callback_data=f"custom_amt_{method}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="cancel_pay"))
    return kb

# --- ВЫДАЧА ПОДПИСКИ АДМИНОМ ---
def admin_grant_sub_menu(user_id):
    """Выбор срока подписки для выдачи. 0 = навсегда. -2 = забрать подписку."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    options = [(7, "7 дней"), (30, "1 месяц"), (90, "3 месяца"), (365, "1 год"), (0, "♾️ Навсегда")]
    for days, label in options:
        kb.add(types.InlineKeyboardButton(label, callback_data=f"agrant_{user_id}_{days}"))
    
    # Кнопка для удаления подписки
    kb.add(types.InlineKeyboardButton("❌ Забрать подписку", callback_data=f"agrant_{user_id}_-2"))
    # Тестовая кнопка на 1 минуту
    kb.add(types.InlineKeyboardButton("⏳ Тест 1 мин", callback_data=f"agrant_{user_id}_-3"))
    kb.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="admin_cancel"))
    return kb

# --- УВЕДОМЛЕНИЕ ОБ ИСТЕЧЕНИИ ---
def expiry_notification_menu():
    """Кнопки для уведомления об истечении подписки"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("⚡ Продлить подписку", callback_data="choose_tariff"))
    kb.add(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="cabinet_buy_balance"))
    return kb

# --- КЛАСТЕРЫ ---
def admin_cluster_menu(mode, sales_cluster):
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    mode_text = "Авто" if mode == "auto" else "Ручной"
    kb.add(types.InlineKeyboardButton(f"🔁 Режим: {mode_text}", callback_data="admin_cluster_toggle_mode"))
    
    if mode == "manual":
        curr_sales = sales_cluster if sales_cluster else "Не выбран"
        kb.add(types.InlineKeyboardButton(f"🎯 Выбран для продажи: {curr_sales}", callback_data="admin_cluster_select_sales"))
        
    kb.add(types.InlineKeyboardButton("📋 Список кластеров", callback_data="admin_cluster_list"))
    kb.add(types.InlineKeyboardButton("🔄 Обновить из Marzban", callback_data="admin_cluster_sync"))
    kb.add(types.InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back"))
    return kb

def admin_cluster_list_menu(clusters):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c in clusters:
        status = "🟢" if c['is_active'] else "🔴"
        text = f"{status} {c['inbound_tag']} ({c['users_count']}/{c['max_users']})"
        kb.add(types.InlineKeyboardButton(text, callback_data=f"admin_cluster_edit_{c['inbound_tag']}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_cluster_menu"))
    return kb

def admin_cluster_edit_menu(cluster):
    kb = types.InlineKeyboardMarkup(row_width=1)
    tag = cluster['inbound_tag']
    is_active = cluster['is_active']
    
    status_btn = "🔴 Выключить" if is_active else "🟢 Включить"
    kb.add(types.InlineKeyboardButton(status_btn, callback_data=f"admin_cluster_toggle_{tag}"))
    kb.add(types.InlineKeyboardButton(f"⚙️ Изменить лимит ({cluster['max_users']})", callback_data=f"admin_cluster_setlimit_{tag}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_cluster_list"))
    return kb

def admin_cluster_select_menu(clusters):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c in clusters:
        status = "🟢" if c['is_active'] else "🔴"
        text = f"{status} {c['inbound_tag']} ({c['users_count']}/{c['max_users']})"
        kb.add(types.InlineKeyboardButton(text, callback_data=f"admin_cluster_setsales_{c['inbound_tag']}"))
    kb.add(types.InlineKeyboardButton("❌ Очистить выбор", callback_data="admin_cluster_setsales_NONE"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_cluster_menu"))
    return kb