from telebot import types
from loader import bot, db, marzban, crypto
from utils import keyboards
from config import Config
from services.lava import create_invoice, check_status
from utils.notifications import notify_payment
import time
import uuid
import urllib.parse
from datetime import datetime
import telebot.apihelper

def _safe_edit(text, chat_id, message_id, **kwargs):
    """edit_message_text с игнорированием 'message is not modified'"""
    try:
        bot.edit_message_text(text, chat_id, message_id, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
            raise


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def _process_payment(call, order_id, amount, method):
    """
    Общая логика зачисления оплаты: проверка дубля, начисление баланса,
    реферальное вознаграждение, уведомление.
    Возвращает True если платёж зачислен, False если дубль.
    """
    amount = int(amount)
    if db.check_and_mark_invoice(order_id, call.from_user.id, amount):
        db.update_balance(call.from_user.id, amount)
        ref_result = db.reward_referrer(call.from_user.id, amount)
        if ref_result:
            referrer_id, reward = ref_result
            try:
                bot.send_message(referrer_id, f"💸 Вам начислено {reward}₽ — реферальное вознаграждение!")
            except Exception:
                pass
        notify_payment(call.from_user.id, amount, method, call.from_user.username)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, f"✅ Оплата {method} подтверждена! +{amount}₽")
        return True
    else:
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, "⚠️ Этот счет уже был оплачен и зачислен ранее.")
        return False
def get_sub_status(user_id):
    user = db.get_user(user_id)
    if not user: return "Ошибка"
    now = int(time.time())
    # sub_end == -1 означает «навсегда», sub_end == 0 означает «нет подписки»
    # sub_end == -1 означает «навсегда», sub_end == 0 означает «нет подписки»
    if user['sub_end'] == -1:
        link = marzban.get_user_link(user_id)
        if link:
            return f"♾️ Активна навсегда\n\n🔗 Твоя ссылка:\n`{link}`"
        return "❌ Не активна"
    if user['sub_end'] > now:
        date_str = datetime.fromtimestamp(user['sub_end']).strftime('%d.%m.%Y %H:%M')
        link = marzban.get_user_link(user_id)
        return f"✅ Активна до: `{date_str}`\n\n🔗 Твоя ссылка:\n`{link}`"
    return "❌ Не активна"

# --- START ---
@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()
    referrer_id = None
    gift_code = None
    
    if len(args) > 1:
        arg = args[1]
        if arg.isdigit():
            referrer_id = int(arg)
            if referrer_id == message.from_user.id:
                referrer_id = None
        elif arg.startswith("gift_"):
            gift_code = arg
            
    if not db.get_user(message.from_user.id):
        # Новый пользователь
        db.add_user(message.from_user.id, message.from_user.username, referred_by=referrer_id)
        
        # --- ЛОГИКА ТРИАЛА ---
        trial_days = int(db.get_setting("trial_days", "0"))
        if trial_days > 0:
            cluster = db.allocate_cluster()
            if not cluster:
                bot.send_message(message.chat.id, "❌ Извините, сейчас нет свободных серверов для тестового периода. Специалисты уже решают проблему!")
            else:
                db.set_user_cluster(message.from_user.id, cluster)
                db.change_cluster_users_count(cluster, 1)
                
                db.add_subscription(message.from_user.id, trial_days)
                db.set_trial_used(message.from_user.id)
                
                marzban.add_days(message.from_user.id, trial_days, cluster_tag=cluster)
                bot.send_message(message.chat.id, f"🎁 **Сюрприз!** Вам автоматически начислен бесплатный тестовый период на {trial_days} дн.!", parse_mode="Markdown")
        # ----------------------
        
    if gift_code:
        cluster = db.get_user_cluster(message.from_user.id)
        is_new_cluster = False
        if not cluster:
            cluster = db.allocate_cluster()
            if not cluster:
                bot.send_message(message.chat.id, "❌ Извините, сейчас нет свободных серверов для активации подарка. Специалисты уже решают проблему!", reply_markup=keyboards.main_menu())
                return
            is_new_cluster = True
            
        res = db.activate_gift(gift_code, message.from_user.id)
        if isinstance(res, int):
            if is_new_cluster:
                db.set_user_cluster(message.from_user.id, cluster)
                db.change_cluster_users_count(cluster, 1)
            marzban.add_days(message.from_user.id, res, cluster_tag=cluster)
            bot.send_message(message.chat.id, f"🎉 Поздравляем! Вы успешно активировали подарочную подписку на {res} дней!", reply_markup=keyboards.main_menu())
            return
        elif res == "already_activated":
            bot.send_message(message.chat.id, "❌ Этот подарок уже был кем-то активирован.", reply_markup=keyboards.main_menu())
            return
        elif res == "self_activation":
            bot.send_message(message.chat.id, "❌ Вы не можете активировать свой же подарок.", reply_markup=keyboards.main_menu())
            return
        elif res == "not_found":
            bot.send_message(message.chat.id, "❌ Подарок не найден.", reply_markup=keyboards.main_menu())
            return
            
    bot.send_message(message.chat.id, "👋 Привет! Безопасный интернет через зарубежные сервера — быстро, надёжно и просто.", reply_markup=keyboards.main_menu())

# --- КАБИНЕТ ---
@bot.message_handler(func=lambda message: message.text == "👤 Кабинет")
def cabinet(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    status_text = get_sub_status(user_id)
    
    text = f"👤 **Ваш Кабинет**\n\n💰 Баланс: {user['balance']}₽\n\n**СТАТУС ПОДПИСКИ**\n\n{status_text}"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboards.cabinet_menu())

@bot.callback_query_handler(func=lambda c: c.data == "cabinet_buy_balance")
def cabinet_buy_balance_handler(call):
    if db.get_setting("sell_lava", "1") == "0" and db.get_setting("sell_crypto", "1") == "0":
        bot.answer_callback_query(call.id, "❌ Пополнение временно недоступно!", show_alert=True)
        return
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                          text="Выберите способ пополнения:", reply_markup=keyboards.pay_menu())

# --- РЕФЕРАЛЬНАЯ СИСТЕМА ---
@bot.message_handler(func=lambda m: m.text == "🤝 Реферальная система")
def referral_system(message):
    user = db.get_user(message.from_user.id)
    ref_link = f"https://t.me/{Config.BOT_USERNAME}?start={message.from_user.id}"
    ref_percent = int(db.get_setting("ref_percent", "20"))
    
    text = (
        f"🤝 **Реферальная система**\n\n"
        f"Приглашайте друзей и получайте {ref_percent}% от каждого пополнения баланса приглашённым!\n\n"
        f"👥 Приглашено: {user.get('referrals_count', 0)} чел.\n"
        f"💸 Заработано: {user.get('referral_earned', 0)}₽\n\n"
        f"🔗 Ваша ссылка для приглашений:\n`{ref_link}`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ==========================================
#        ОПЛАТА LAVA (RUB)
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data == "top_up")
def pay_rub_step1(call):
    if db.get_setting("sell_lava", "1") == "0":
        bot.answer_callback_query(call.id, "❌ Оплата через Lava временно недоступна!", show_alert=True)
        return
    bot.edit_message_text(
        "💰 Выберите сумму пополнения:",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboards.quick_amount_menu("lava")
    )

def pay_rub_step2(message, bot_msg_id):
    try:
        min_topup = int(db.get_setting("min_topup", "10"))

        if not message.text or not message.text.isdigit():
            _safe_edit(
                f"❌ «{message.text or ''}» — не число. Введите сумму (мин. {min_topup}₽):",
                message.chat.id, bot_msg_id,
                reply_markup=keyboards.cancel_action_menu()
            )
            bot.register_next_step_handler(message, lambda m: pay_rub_step2(m, bot_msg_id))
            return

        amount = int(message.text)
        if amount < min_topup:
            _safe_edit(
                f"❌ {amount}₽ — мало. Минимум {min_topup}₽. Введите другую сумму:",
                message.chat.id, bot_msg_id,
                reply_markup=keyboards.cancel_action_menu()
            )
            bot.register_next_step_handler(message, lambda m: pay_rub_step2(m, bot_msg_id))
            return

        bot.edit_message_text("⏳ Создаю счет Lava...", message.chat.id, bot_msg_id)
        pay_url, order_id = create_invoice(amount, message.from_user.id)

        if pay_url:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"💳 Оплатить {amount}₽", url=pay_url))
            kb.add(types.InlineKeyboardButton("🔄 Я оплатил", callback_data=f"chk_lv|{order_id}|{amount}"))
            bot.edit_message_text(f"🧾 Lava: Счет на {amount}₽ создан.", message.chat.id, bot_msg_id, reply_markup=kb)
        else:
            bot.edit_message_text("❌ Ошибка при создании счета Lava.", message.chat.id, bot_msg_id)
    except Exception as e:
        print(f"Error Lava: {e}")

# Хендлер проверки Lava
@bot.callback_query_handler(func=lambda c: c.data.startswith("chk_lv|"))
def check_lava_handler(call):
    try:
        parts = call.data.split("|", 2)
        order_id = parts[1]
        amount = int(parts[2])

        if check_status(order_id):
            _process_payment(call, order_id, amount, "Lava")
        else:
            bot.answer_callback_query(call.id, "❌ Оплата еще не поступила. Нажмите позже.", show_alert=True)
    except Exception as e:
        print(f"Error checking Lava: {e}")
        bot.answer_callback_query(call.id, "Ошибка проверки", show_alert=True)

# ==========================================
#        ОПЛАТА CRYPTOBOT
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data == "pay_crypto")
def pay_crypto_step1(call):
    if db.get_setting("sell_crypto", "1") == "0":
        bot.answer_callback_query(call.id, "❌ Оплата через CryptoBot временно недоступна!", show_alert=True)
        return
    bot.edit_message_text(
        "💎 Выберите сумму пополнения:",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboards.quick_amount_menu("crypto")
    )

# --- БЫСТРЫЙ ВЫБОР СУММЫ ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("qamt_"))
def quick_amount_handler(call):
    """Быстрый выбор суммы: qamt_lava_100 или qamt_crypto_200"""
    parts = call.data.split("_")
    method = parts[1]  # 'lava' или 'crypto'
    amount = int(parts[2])

    if method == "lava":
        _create_lava_invoice(call, amount)
    elif method == "crypto":
        _create_crypto_invoice(call, amount)

@bot.callback_query_handler(func=lambda c: c.data.startswith("custom_amt_"))
def custom_amount_handler(call):
    """Ручной ввод суммы"""
    method = call.data.split("_")[2]  # 'lava' или 'crypto'
    min_topup = int(db.get_setting("min_topup", "10"))
    bot.edit_message_text(
        f"✏️ Введите сумму пополнения (мин. {min_topup}₽):",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboards.cancel_action_menu()
    )
    bot_msg_id = call.message.message_id
    if method == "lava":
        bot.register_next_step_handler(call.message, lambda m: pay_rub_step2(m, bot_msg_id))
    else:
        bot.register_next_step_handler(call.message, lambda m: pay_crypto_step2(m, bot_msg_id))

def _create_lava_invoice(call, amount):
    """Создаёт Lava-счёт на указанную сумму"""
    try:
        bot.edit_message_text("⏳ Создаю счет Lava...", call.message.chat.id, call.message.message_id)
        pay_url, order_id = create_invoice(amount, call.from_user.id)
        if pay_url:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"💳 Оплатить {amount}₽", url=pay_url))
            kb.add(types.InlineKeyboardButton("🔄 Я оплатил", callback_data=f"chk_lv|{order_id}|{amount}"))
            bot.edit_message_text(f"🧁 Lava: Счет на {amount}₽ создан.", call.message.chat.id, call.message.message_id, reply_markup=kb)
        else:
            bot.edit_message_text("❌ Ошибка при создании счета Lava.", call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"Error Lava quick: {e}")

def _create_crypto_invoice(call, amount):
    """Создаёт CryptoBot-счёт на указанную сумму"""
    try:
        bot.edit_message_text("⏳ Создаю счет CryptoBot...", call.message.chat.id, call.message.message_id)
        pay_url, invoice_id = crypto.create_invoice(amount)
        if pay_url:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"💎 Оплатить {amount}₽", url=pay_url))
            kb.add(types.InlineKeyboardButton("🔄 Я оплатил", callback_data=f"chk_cr|{invoice_id}|{amount}"))
            bot.edit_message_text(f"🧁 CryptoBot: Счет на {amount}₽ создан.", call.message.chat.id, call.message.message_id, reply_markup=kb)
        else:
            bot.edit_message_text("❌ Ошибка CryptoBot.", call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"Error Crypto quick: {e}")

def pay_crypto_step2(message, bot_msg_id):
    try:
        min_topup = int(db.get_setting("min_topup", "10"))

        if not message.text or not message.text.isdigit():
            _safe_edit(
                f"❌ «{message.text or ''}» — не число. Введите сумму (мин. {min_topup}₽):",
                message.chat.id, bot_msg_id,
                reply_markup=keyboards.cancel_action_menu()
            )
            bot.register_next_step_handler(message, lambda m: pay_crypto_step2(m, bot_msg_id))
            return

        amount = int(message.text)
        if amount < min_topup:
            _safe_edit(
                f"❌ {amount}₽ — мало. Минимум {min_topup}₽. Введите другую сумму:",
                message.chat.id, bot_msg_id,
                reply_markup=keyboards.cancel_action_menu()
            )
            bot.register_next_step_handler(message, lambda m: pay_crypto_step2(m, bot_msg_id))
            return

        bot.edit_message_text("⏳ Создаю счет CryptoBot...", message.chat.id, bot_msg_id)
        pay_url, invoice_id = crypto.create_invoice(amount)

        if pay_url:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"💎 Оплатить {amount}₽", url=pay_url))
            kb.add(types.InlineKeyboardButton("🔄 Я оплатил", callback_data=f"chk_cr|{invoice_id}|{amount}"))
            bot.edit_message_text(f"🧾 CryptoBot: Счет на {amount}₽ создан.", message.chat.id, bot_msg_id, reply_markup=kb)
        else:
            bot.edit_message_text("❌ Ошибка CryptoBot.", message.chat.id, bot_msg_id)
    except Exception as e:
        print(f"Error Crypto: {e}")

# Хендлер проверки CryptoBot
@bot.callback_query_handler(func=lambda c: c.data.startswith("chk_cr|"))
def check_crypto_handler(call):
    try:
        parts = call.data.split("|", 2)
        invoice_id = str(parts[1])
        amount = int(parts[2])

        if crypto.check_invoice(invoice_id):
            db_order_id = f"cr_{invoice_id}"
            _process_payment(call, db_order_id, amount, "CryptoBot")
        else:
            bot.answer_callback_query(call.id, "❌ Еще не оплачено.", show_alert=True)
    except Exception as e:
        print(f"Check Crypto Error: {e}")

# --- ПОКУПКА И ИНФО ---
@bot.callback_query_handler(func=lambda c: c.data == "choose_tariff")
def choose_tariff(call):
    """Показывает список тарифов для покупки"""
    if db.get_setting("sell_subs", "1") == "0":
        bot.answer_callback_query(call.id, "❌ Продажа подписок временно остановлена!", show_alert=True)
        return
    tariffs = db.get_tariffs()
    bot.edit_message_text(
        "📋 Выберите тариф:",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboards.tariff_select_menu(tariffs, mode="buy")
    )

@bot.callback_query_handler(func=lambda c: c.data == "choose_gift_tariff")
def choose_gift_tariff(call):
    """Показывает список тарифов для подарка"""
    if db.get_setting("sell_gifts", "1") == "0":
        bot.answer_callback_query(call.id, "❌ Подарочные подписки временно недоступны!", show_alert=True)
        return
    tariffs = db.get_tariffs()
    bot.edit_message_text(
        "🎁 Выберите тариф для подарка:",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboards.tariff_select_menu(tariffs, mode="gift")
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("tbuy_"))
def confirm_tariff_buy(call):
    """Подтверждение покупки выбранного тарифа"""
    days = int(call.data.split("_")[1])
    tariffs = db.get_tariffs()
    price = tariffs.get(days)
    if not price:
        bot.answer_callback_query(call.id, "❌ Тариф не найден!", show_alert=True)
        return
    label = keyboards.format_days(days)
    bot.edit_message_text(
        f"❓ Купить подписку на {label} за {price}₽?",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboards.confirm_buy_menu(days, price)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("tgift_"))
def confirm_tariff_gift(call):
    """Подтверждение подарка выбранного тарифа"""
    days = int(call.data.split("_")[1])
    tariffs = db.get_tariffs()
    price = tariffs.get(days)
    if not price:
        bot.answer_callback_query(call.id, "❌ Тариф не найден!", show_alert=True)
        return
    label = keyboards.format_days(days)
    bot.edit_message_text(
        f"❓ Подарить подписку на {label} за {price}₽?",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboards.confirm_gift_menu(days, price)
    )

@bot.callback_query_handler(func=lambda c: c.data in ["cancel_pay", "cancel_buy"])
def return_to_cabinet(call):
    """Общая функция отмены действий и возврата в кабинет (с очисткой step-обработчиков)"""
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    user_id = call.from_user.id
    user = db.get_user(user_id)
    status_text = get_sub_status(user_id)

    text = f"👤 **Ваш Кабинет**\n\n💰 Баланс: {user['balance']}₽\n\n**СТАТУС ПОДПИСКИ**\n\n{status_text}"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboards.cabinet_menu()
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy_sub(call):
    """Покупка подписки на N дней"""
    days = int(call.data.split("_")[1])
    tariffs = db.get_tariffs()
    price = tariffs.get(days)
    
    if not price:
        bot.answer_callback_query(call.id, "❌ Тариф не найден!", show_alert=True)
        return
    if db.get_setting("sell_subs", "1") == "0":
        bot.answer_callback_query(call.id, "❌ Продажа подписок временно остановлена!", show_alert=True)
        return
        
    user_id = call.from_user.id
    user = db.get_user(user_id)
    
    if user['balance'] >= price:
        db.update_balance(user_id, -price)
        
        cluster = db.get_user_cluster(user_id)
        if not cluster:
            cluster = db.allocate_cluster()
            if not cluster:
                db.update_balance(user_id, price) # Возврат средств
                bot.answer_callback_query(call.id, "❌ Извините, сейчас нет свободных серверов. Админ уже решает проблему!", show_alert=True)
                return
            db.set_user_cluster(user_id, cluster)
            db.change_cluster_users_count(cluster, 1)
                
        db.add_subscription(user_id, days)
        marzban.add_days(user_id, days, cluster_tag=cluster)
        
        label = keyboards.format_days(days)
        bot.send_message(call.message.chat.id, f"✅ Подписка на {label} оформлена!", reply_markup=keyboards.cabinet_menu())
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
    else:
        bot.answer_callback_query(call.id, f"❌ Не хватает денег! Нужно {price}₽.", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("gift_"))
def buy_gift_sub(call):
    """Покупка подарочной подписки на N дней"""
    days = int(call.data.split("_")[1])
    tariffs = db.get_tariffs()
    price = tariffs.get(days)
    
    if not price:
        bot.answer_callback_query(call.id, "❌ Тариф не найден!", show_alert=True)
        return
    if db.get_setting("sell_gifts", "1") == "0":
        bot.answer_callback_query(call.id, "❌ Подарочные подписки временно недоступны!", show_alert=True)
        return
        
    user_id = call.from_user.id
    user = db.get_user(user_id)
    
    if user['balance'] >= price:
        db.update_balance(user_id, -price)
        
        unique_id = str(uuid.uuid4()).split('-')[0]
        gift_code = f"gift_{unique_id}"
        
        db.create_gift(gift_code, user_id, days)
        
        gift_link = f"https://t.me/{Config.BOT_USERNAME}?start={gift_code}"
        
        label = keyboards.format_days(days)
        share_text = f"🎁 Держи подарок! Я дарю тебе подписку на {label}! 🚀 Забирай по ссылке ниже 👇\n\n{gift_link}"
        encoded_text = urllib.parse.quote(share_text)
        share_url = f"https://t.me/share/url?url={encoded_text}"
        
        bot.send_message(
            call.message.chat.id, 
            f"✅ Вы успешно купили подарочную подписку на {label}!\n\n"
            f"Нажмите кнопку ниже, чтобы отправить подарок другу 🎁",
            reply_markup=keyboards.gift_share_menu(share_url)
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
    else:
        bot.answer_callback_query(call.id, f"❌ Не хватает денег! Нужно {price}₽.", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Информация")
def show_info(message):
    bot.send_message(message.chat.id, f"ℹ️ Безопасный интернет через зарубежные сервера.\nПоддержка: @{Config.SUPPORT_USERNAME}", reply_markup=keyboards.info_links())

@bot.message_handler(func=lambda m: m.text == "🎁 Промокод")
def ask_promo(message):
    msg = bot.send_message(message.chat.id, "Введите промокод:")
    bot.register_next_step_handler(msg, activate_promo_step)

def activate_promo_step(message):
    res = db.activate_promo(message.from_user.id, message.text.upper().strip())
    if res == "not_found": bot.send_message(message.chat.id, "❌ Неверный код")
    elif isinstance(res, (int, float)): bot.send_message(message.chat.id, f"✅ +{res}₽")
    else: bot.send_message(message.chat.id, "❌ Ошибка")

# ==========================================
#        ИНСТРУКЦИИ ПО ПОДКЛЮЧЕНИЮ
# ==========================================

# Тексты инструкций для каждого устройства (легко редактировать)
INSTRUCTIONS = {
    "ios": {
        "title": "📱 Подключение на iPhone / iPad",
        "steps": (
            "1️⃣ Скачайте приложение <b>V2Box</b>, <b>V2RayTun</b> или <b>Streisand</b> из App Store\n"
            "2️⃣ Скопируйте ссылку подписки ниже\n"
            "3️⃣ В приложении нажмите \"+\" → \"Импорт из буфера обмена\"\n"
            "4️⃣ Подключитесь ✅\n\n"
            f"💡 Если не работает — напишите @{Config.SUPPORT_USERNAME}"
        )
    },
    "android": {
        "title": "🤖 Подключение на Android",
        "steps": (
            "1️⃣ Скачайте приложение <b>V2RayTun</b> или <b>Streisand</b> из Google Play\n"
            "2️⃣ Скопируйте ссылку подписки ниже\n"
            "3️⃣ В приложении нажмите \"+\" → \"Импорт из буфера обмена\"\n"
            "4️⃣ Включите VPN ✅\n\n"
            f"💡 Если не работает — напишите @{Config.SUPPORT_USERNAME}"
        )
    },
    "windows": {
        "title": "💻 Подключение на Windows",
        "steps": (
            "1️⃣ Скачайте приложение <b>Happ</b> или <b>Nekobox</b>\n"
            "2️⃣ Скопируйте ссылку подписки ниже\n"
            "3️⃣ В приложении импортируйте ссылку\n"
            "4️⃣ Включите VPN ✅\n\n"
            f"💡 Если не работает — напишите @{Config.SUPPORT_USERNAME}"
        )
    },
    "macos": {
        "title": "🍎 Подключение на macOS",
        "steps": (
            "1️⃣ Скачайте приложение <b>V2Box</b>, <b>V2RayTun</b> или <b>FoXray</b> из App Store\n"
            "2️⃣ Скопируйте ссылку подписки ниже\n"
            "3️⃣ В приложении импортируйте ссылку\n"
            "4️⃣ Включите VPN ✅\n\n"
            f"💡 Если не работает — напишите @{Config.SUPPORT_USERNAME}"
        )
    },
}

@bot.message_handler(func=lambda m: m.text == "📱 Как подключить?")
def how_to_connect(message):
    """Показывает выбор устройства"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📱 iPhone/iPad", callback_data="connect_ios"),
        types.InlineKeyboardButton("🤖 Android", callback_data="connect_android"),
    )
    kb.add(
        types.InlineKeyboardButton("💻 Windows", callback_data="connect_windows"),
        types.InlineKeyboardButton("🍎 macOS", callback_data="connect_macos"),
    )
    bot.send_message(message.chat.id, "📱 Выберите ваше устройство:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("connect_") and c.data != "connect_back")
def show_connect_instructions(call):
    """Показывает инструкцию + ссылки импорта как гиперссылки"""
    device = call.data.split("_")[1]
    info = INSTRUCTIONS.get(device)
    if not info:
        bot.answer_callback_query(call.id, "❌ Неизвестное устройство", show_alert=True)
        return

    sub_link = marzban.get_user_link(call.from_user.id)
    
    text = f"<b>{info['title']}</b>\n\n{info['steps']}"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    if sub_link:
        text += f"\n\n🔗 <b>Ваша ссылка подписки</b> (нажмите чтобы скопировать):\n<code>{sub_link}</code>"
    else:
        text += "\n\n⚠️ У вас нет активной подписки — купите её в кабинете, чтобы появились ссылки импорта."
    
    kb.add(types.InlineKeyboardButton("🔙 Выбрать другое устройство", callback_data="connect_back"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "connect_back")
def connect_back(call):
    """Возврат к выбору устройства"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📱 iPhone/iPad", callback_data="connect_ios"),
        types.InlineKeyboardButton("🤖 Android", callback_data="connect_android"),
    )
    kb.add(
        types.InlineKeyboardButton("💻 Windows", callback_data="connect_windows"),
        types.InlineKeyboardButton("🍎 macOS", callback_data="connect_macos"),
    )
    bot.edit_message_text("📱 Выберите ваше устройство:", call.message.chat.id, 
                         call.message.message_id, reply_markup=kb)