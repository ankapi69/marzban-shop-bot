import hmac
import hashlib
import json
import requests
import time
from config import Config


def _sign_and_send(url, payload):
    """Подписывает payload HMAC-SHA256 и отправляет POST-запрос к Lava API"""
    json_str = json.dumps(payload, separators=(',', ':'))
    signature = hmac.new(
        Config.LAVA_SECRET_KEY.encode('utf-8'),
        json_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Signature": signature
    }

    response = requests.post(url, data=json_str, headers=headers)
    result = response.json()

    if response.status_code == 200 and result.get('status') == 200:
        return result.get('data')
    return None


def create_invoice(amount, user_id):
    """Создает ссылку на оплату через Lava"""
    order_id = f"ord{user_id}t{int(time.time())}"

    payload = {
        "shopId": Config.LAVA_PROJECT_ID,
        "sum": float(amount),
        "orderId": order_id,
        "expire": 300,
        "comment": f"Pay: {user_id}",
        "hookUrl": f"{Config.BASE_URL}/webhook",
        "failUrl": f"https://t.me/{Config.BOT_USERNAME}",
        "successUrl": f"https://t.me/{Config.BOT_USERNAME}"
    }

    try:
        data = _sign_and_send("https://api.lava.ru/business/invoice/create", payload)
        if data:
            return data['url'], order_id
        print(f"❌ Ошибка создания Lava invoice")
    except Exception as e:
        print(f"❌ Критическая ошибка Lava: {e}")
    return None, None


def check_status(order_id):
    """Проверяет статус оплаты по order_id"""
    payload = {
        "shopId": Config.LAVA_PROJECT_ID,
        "orderId": order_id
    }

    try:
        data = _sign_and_send("https://api.lava.ru/business/invoice/status", payload)
        if isinstance(data, dict):
            return data.get('status') in ('success', 'completed')
    except Exception as e:
        print(f"❌ Ошибка проверки статуса Lava: {e}")
    return False
