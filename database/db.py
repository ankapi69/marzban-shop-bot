import json
import sqlite3
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Включаем режим WAL для многопоточности бота
        self.cursor.execute("PRAGMA journal_mode=WAL;")
        self.cursor.execute("PRAGMA synchronous=NORMAL;")
        
        self.create_table()

    def create_table(self):
        with self.conn:
            # Таблица пользователей
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    sub_end INTEGER DEFAULT 0,
                    signup_date INTEGER
                )
            """)
            # Таблица промокодов
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    code TEXT PRIMARY KEY,
                    amount INTEGER,
                    activations_left INTEGER,
                    activations_total INTEGER
                )
            """)
            # Таблица использованных промокодов (кто какой код вводил)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS used_promos (
                    user_id INTEGER,
                    code TEXT,
                    UNIQUE(user_id, code)
                )
            """)
            # Миграция: добавляем колонки, если их ещё нет
            for col in [
                "referred_by INTEGER",
                "referrals_count INTEGER DEFAULT 0",
                "referral_earned INTEGER DEFAULT 0",
                "trial_used INTEGER DEFAULT 0",
                "notified_expiry INTEGER DEFAULT 0",
                "cluster TEXT",
            ]:
                try:
                    with self.conn:
                        self.cursor.execute(f"ALTER TABLE users ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass  # Колонка уже существует
            
            # Таблица кластеров
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS clusters (
                    inbound_tag TEXT PRIMARY KEY,
                    users_count INTEGER DEFAULT 0,
                    max_users INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 0
                )
            """)

            # Таблица подарков
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS gifts (
                    code TEXT PRIMARY KEY,
                    creator_id INTEGER,
                    days INTEGER,
                    is_activated INTEGER DEFAULT 0,
                    activated_by INTEGER
                )
            """)

            # Таблица оплаченных инвойсов
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    order_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    amount REAL,
                    date INTEGER
                )
            """)

            # Таблица настроек (Key-Value)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Добавляем настройки по умолчанию, если их нет
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sales_active', '1')")
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sub_price', '150')")
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('trial_days', '0')")
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_percent', '20')")
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('min_topup', '10')")
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cluster_mode', 'auto')")
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sales_cluster', '')")
            # Тарифы: JSON словарь {"дни": цена}
            default_tariffs = json.dumps({"7": 50, "30": 150, "90": 400})
            self.cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('tariffs', ?)", (default_tariffs,))

    # --- НАСТРОЙКИ ---
    def get_setting(self, key, default_value=None):
        self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        res = self.cursor.fetchone()
        return res[0] if res else default_value

    def set_setting(self, key, value):
        with self.conn:
            self.cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?", 
                                (key, str(value), str(value)))

    # --- ТАРИФЫ ---
    def get_tariffs(self):
        """Возвращает словарь тарифов {дни(int): цена(int)}, отсортированный по дням"""
        raw = self.get_setting("tariffs", '{"30": 150}')
        data = json.loads(raw)
        return dict(sorted({int(k): int(v) for k, v in data.items()}.items()))

    def save_tariffs(self, tariffs_dict):
        """Сохраняет словарь тарифов в БД"""
        self.set_setting("tariffs", json.dumps({str(k): v for k, v in tariffs_dict.items()}))

    def add_tariff(self, days, price):
        """Добавляет тариф. Если такой срок уже есть — перезаписывает цену"""
        tariffs = self.get_tariffs()
        tariffs[int(days)] = int(price)
        self.save_tariffs(tariffs)

    def remove_tariff(self, days):
        """Удаляет тариф по количеству дней"""
        tariffs = self.get_tariffs()
        removed = tariffs.pop(int(days), None)
        self.save_tariffs(tariffs)
        return removed is not None

    # --- ПОЛЬЗОВАТЕЛИ ---
    def set_trial_used(self, user_id):
        """Отмечает, что пользователь использовал бесплатный триал"""
        with self.conn:
            self.cursor.execute("UPDATE users SET trial_used = 1 WHERE user_id = ?", (user_id,))

    def add_user(self, user_id, username, referred_by=None):
        with self.conn:
            self.cursor.execute("INSERT OR IGNORE INTO users (user_id, username, signup_date, referred_by) VALUES (?, ?, ?, ?)", 
                                (user_id, username, int(time.time()), referred_by))
            if referred_by:
                # Увеличиваем счетчик приглашенных у рефера
                self.cursor.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referred_by,))

    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        res = self.cursor.fetchone()
        if res:
            # Получаем имена колонок
            col_names = [description[0] for description in self.cursor.description]
            return dict(zip(col_names, res))
        return None
    
    def get_all_users(self):
        """Возвращает ID всех пользователей для рассылки"""
        self.cursor.execute("SELECT user_id FROM users")
        return [row[0] for row in self.cursor.fetchall()]

    def update_balance(self, user_id, amount):
        with self.conn:
            self.cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))

    @staticmethod
    def calc_expiry(base_timestamp, days):
        """Рассчитывает timestamp окончания подписки с учётом календарных месяцев"""
        base_date = datetime.fromtimestamp(base_timestamp)
        if days == 30:
            new_date = base_date + relativedelta(months=1)
        elif days == 90:
            new_date = base_date + relativedelta(months=3)
        elif days == 365:
            new_date = base_date + relativedelta(years=1)
        else:
            new_date = base_date + relativedelta(days=days)
        return int(new_date.timestamp())

    def add_subscription(self, user_id, days):
        user = self.get_user(user_id)
        if not user:
            return None
        # days == 0 → подписка навсегда
        if days == 0:
            with self.conn:
                self.cursor.execute("UPDATE users SET sub_end = -1, notified_expiry = 0 WHERE user_id = ?", (user_id,))
            return -1
        # Если у пользователя уже есть бесконечная подписка, мы её не меняем при добавлении дней
        if user.get('sub_end') == -1:
            return -1
            
        base_ts = max(user.get('sub_end', 0), int(time.time()))
        new_end = self.calc_expiry(base_ts, days)
        with self.conn:
            self.cursor.execute("UPDATE users SET sub_end = ?, notified_expiry = 0 WHERE user_id = ?", (new_end, user_id))
        return new_end

    def revoke_subscription(self, user_id):
        """Полностью обнуляет подписку"""
        with self.conn:
            self.cursor.execute("UPDATE users SET sub_end = 0, notified_expiry = 0 WHERE user_id = ?", (user_id,))
            
    # --- УВЕДОМЛЕНИЯ ОБ ИСТЕЧЕНИИ ПОДПИСКИ ---
    def get_expiring_users(self, within_seconds=86400):
        """Пользователи, чья подписка истекает в пределах within_seconds и ещё не уведомлены (level < 1)"""
        now = int(time.time())
        deadline = now + within_seconds
        self.cursor.execute(
            "SELECT user_id, sub_end, balance FROM users WHERE sub_end > ? AND sub_end <= ? AND notified_expiry < 1 AND sub_end != -1",
            (now, deadline)
        )
        return [{'user_id': r[0], 'sub_end': r[1], 'balance': r[2]} for r in self.cursor.fetchall()]

    def get_expired_users(self):
        """Пользователи с истёкшей подпиской (sub_end > 0, sub_end < now), не уведомлены (level < 2)"""
        now = int(time.time())
        self.cursor.execute(
            "SELECT user_id, sub_end, balance FROM users WHERE sub_end > 0 AND sub_end < ? AND notified_expiry < 2",
            (now,)
        )
        return [{'user_id': r[0], 'sub_end': r[1], 'balance': r[2]} for r in self.cursor.fetchall()]

    def set_notified_expiry(self, user_id, level):
        """Обновляет уровень уведомления: 1 = за 1 день, 2 = при истечении"""
        with self.conn:
            self.cursor.execute("UPDATE users SET notified_expiry = ? WHERE user_id = ?", (level, user_id))

    def reward_referrer(self, user_id, amount):
        """Начисляет пригласившему процент от пополнения реферала"""
        user = self.get_user(user_id)
        if not user or not user.get('referred_by'):
            return False

        ref_percent = int(self.get_setting("ref_percent", "20"))
        if ref_percent <= 0:
            return False

        reward = round(amount * ref_percent / 100)
        if reward <= 0:
            return False

        referrer_id = user['referred_by']
        with self.conn:
            self.cursor.execute(
                "UPDATE users SET balance = balance + ?, referral_earned = referral_earned + ? WHERE user_id = ?",
                (reward, reward, referrer_id)
            )
        return (referrer_id, reward)

    # --- ПРОМОКОДЫ ---
    def create_promo(self, code, amount, activations):
        try:
            with self.conn:
                self.cursor.execute("INSERT INTO promocodes VALUES (?, ?, ?, ?)", 
                                    (code, amount, activations, activations))
            return True
        except Exception:
            return False

    def get_promos(self):
        """Список всех активных промокодов"""
        self.cursor.execute("SELECT * FROM promocodes")
        return self.cursor.fetchall()

    def activate_promo(self, user_id, code):
        """Попытка активации промокода"""
        # 1. Проверяем существование и лимит
        self.cursor.execute("SELECT amount, activations_left FROM promocodes WHERE code = ?", (code,))
        promo = self.cursor.fetchone()
        
        if not promo: return "not_found"
        amount, left = promo
        
        if left <= 0: return "ended"

        # 2. Проверяем, вводил ли юзер этот код
        self.cursor.execute("SELECT * FROM used_promos WHERE user_id = ? AND code = ?", (user_id, code))
        if self.cursor.fetchone(): return "already_used"

        # 3. АКТИВАЦИЯ (Транзакция)
        try:
            with self.conn:
                # Списываем использование
                self.cursor.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?", (code,))
                # Записываем юзера
                self.cursor.execute("INSERT INTO used_promos VALUES (?, ?)", (user_id, code))
                # Начисляем баланс
                self.cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            return amount # Возвращаем сумму пополнения
        except Exception:
            return "error"
    def delete_inactive_promos(self):
        """Удаляет все промокоды с 0 активаций"""
        with self.conn:
            self.conn.execute("DELETE FROM used_promos WHERE code IN (SELECT code FROM promocodes WHERE activations_left <= 0)")
            cursor = self.conn.execute("DELETE FROM promocodes WHERE activations_left <= 0")
            # Возвращаем количество удаленных строк
            return cursor.rowcount

    def delete_promo_by_name(self, code):
        """Удаляет конкретный промокод по имени"""
        with self.conn:
            self.conn.execute("DELETE FROM used_promos WHERE code = ?", (code,))
            cursor = self.conn.execute("DELETE FROM promocodes WHERE code = ?", (code,))
            return cursor.rowcount > 0

    # --- ПОДАРКИ ---
    def create_gift(self, code, creator_id, days):
        """Создает новый подарочный код"""
        try:
            with self.conn:
                self.cursor.execute("INSERT INTO gifts (code, creator_id, days) VALUES (?, ?, ?)", 
                                    (code, creator_id, days))
            return True
        except Exception:
            return False

    def activate_gift(self, code, user_id):
        """Активирует подарочный код для пользователя"""
        self.cursor.execute("SELECT days, is_activated, creator_id FROM gifts WHERE code = ?", (code,))
        gift = self.cursor.fetchone()
        
        if not gift:
            return "not_found"
            
        days, is_activated, creator_id = gift
        
        if is_activated == 1:
            return "already_activated"
            
        if creator_id == user_id:
            return "self_activation"
            
        # Активируем
        try:
            with self.conn:
                self.cursor.execute("UPDATE gifts SET is_activated = 1, activated_by = ? WHERE code = ?", (user_id, code))
            
            # Добавляем подписку
            self.add_subscription(user_id, days)
            return days
        except Exception:
            return "error"
            
    # --- ОПЛАТА / СЧЕТА ---
    def check_and_mark_invoice(self, order_id, user_id, amount):
        """
        Проверяет, был ли уже зачислен такой платеж.
        Если нет — записывает в базу и возвращает True.
        Если да (такой order_id уже есть) — возвращает False.
        """
        try:
            with self.conn:
                self.cursor.execute("INSERT INTO invoices (order_id, user_id, amount, date) VALUES (?, ?, ?, ?)",
                                    (order_id, user_id, amount, int(time.time())))
            return True
        except sqlite3.IntegrityError:
            # Срабатывает, если order_id уже существует (PRIMARY KEY constraint)
            return False

    # --- СТАТИСТИКА (ДАШБОРД) ---
    def get_stats(self):
        """Собирает статистику для админского дашборда"""
        now = int(time.time())
        today_start = now - (now % 86400)  # Начало текущих суток (UTC)
        week_start = now - 7 * 86400
        month_start = now - 30 * 86400
        
        # Всего пользователей
        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0]
        
        # Новые пользователи за сегодня
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE signup_date >= ?", (today_start,))
        new_today = self.cursor.fetchone()[0]
        
        # Активные подписки (sub_end > сейчас или -1)
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE sub_end > ? OR sub_end = -1", (now,))
        active_subs = self.cursor.fetchone()[0]
        
        # Выручка за сегодня / неделю / месяц / всего
        self.cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE date >= ?", (today_start,))
        revenue_today = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE date >= ?", (week_start,))
        revenue_week = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE date >= ?", (month_start,))
        revenue_month = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM invoices")
        revenue_total = self.cursor.fetchone()[0]
        
        # Всего оплаченных счетов
        self.cursor.execute("SELECT COUNT(*) FROM invoices")
        total_invoices = self.cursor.fetchone()[0]
        
        # Активных промокодов
        self.cursor.execute("SELECT COUNT(*) FROM promocodes WHERE activations_left > 0")
        active_promos = self.cursor.fetchone()[0]
        
        # Реферальная статистика
        self.cursor.execute("SELECT COALESCE(SUM(referral_earned), 0), COALESCE(SUM(referrals_count), 0) FROM users")
        ref_row = self.cursor.fetchone()
        total_ref_payouts = ref_row[0]
        total_referrals = ref_row[1]

        self.cursor.execute(
            "SELECT user_id, referrals_count, referral_earned FROM users "
            "WHERE referral_earned > 0 ORDER BY referral_earned DESC LIMIT 3"
        )
        top_referrers = [{'user_id': r[0], 'count': r[1], 'earned': r[2]} for r in self.cursor.fetchall()]

        return {
            "total_users": total_users,
            "new_today": new_today,
            "active_subs": active_subs,
            "revenue_today": revenue_today,
            "revenue_week": revenue_week,
            "revenue_month": revenue_month,
            "revenue_total": revenue_total,
            "total_invoices": total_invoices,
            "active_promos": active_promos,
            "total_ref_payouts": total_ref_payouts,
            "total_referrals": total_referrals,
            "top_referrers": top_referrers,
        }

    # --- КЛАСТЕРЫ ---
    def get_cluster(self, inbound_tag):
        self.cursor.execute("SELECT * FROM clusters WHERE inbound_tag = ?", (inbound_tag,))
        res = self.cursor.fetchone()
        if res:
            col_names = [description[0] for description in self.cursor.description]
            return dict(zip(col_names, res))
        return None

    def get_all_clusters(self):
        self.cursor.execute("SELECT * FROM clusters")
        res = self.cursor.fetchall()
        if res:
            col_names = [description[0] for description in self.cursor.description]
            return [dict(zip(col_names, row)) for row in res]
        return []

    def get_active_clusters(self):
        self.cursor.execute("SELECT * FROM clusters WHERE is_active = 1")
        res = self.cursor.fetchall()
        if res:
            col_names = [description[0] for description in self.cursor.description]
            return [dict(zip(col_names, row)) for row in res]
        return []

    def add_cluster(self, inbound_tag, max_users, is_active=1):
        with self.conn:
            self.cursor.execute("INSERT OR IGNORE INTO clusters (inbound_tag, max_users, is_active) VALUES (?, ?, ?)",
                                (inbound_tag, max_users, is_active))

    def update_cluster(self, inbound_tag, max_users, is_active):
        with self.conn:
            self.cursor.execute("UPDATE clusters SET max_users = ?, is_active = ? WHERE inbound_tag = ?",
                                (max_users, is_active, inbound_tag))

    def delete_cluster(self, inbound_tag):
        with self.conn:
            self.cursor.execute("DELETE FROM clusters WHERE inbound_tag = ?", (inbound_tag,))

    def change_cluster_users_count(self, inbound_tag, delta):
        with self.conn:
            self.cursor.execute("UPDATE clusters SET users_count = max(0, users_count + ?) WHERE inbound_tag = ?", (delta, inbound_tag))

    def set_user_cluster(self, user_id, cluster_tag):
        with self.conn:
            self.cursor.execute("UPDATE users SET cluster = ? WHERE user_id = ?", (cluster_tag, user_id))

    def get_user_cluster(self, user_id):
        self.cursor.execute("SELECT cluster FROM users WHERE user_id = ?", (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else None

    def allocate_cluster(self):
        """Возвращает тег кластера для нового пользователя в зависимости от режима"""
        mode = self.get_setting("cluster_mode", "auto")
        
        if mode == "manual":
            sales_cluster = self.get_setting("sales_cluster", "")
            if sales_cluster:
                return sales_cluster
            # Если не выбран, пробуем авто-режим
        
        # Авто-режим: ищем первый активный кластер, где users_count < max_users
        self.cursor.execute("SELECT inbound_tag FROM clusters WHERE is_active = 1 AND users_count < max_users LIMIT 1")
        res = self.cursor.fetchone()
        if res:
            return res[0]
            
        return None  # Нет доступных кластеров