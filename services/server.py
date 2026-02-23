import re
import hmac
import hashlib
import json
from flask import Flask, request, jsonify
from config import Config
from loader import bot, db
from utils.notifications import notify_payment

app = Flask(__name__)


def verify_signature(body_bytes, signature_header):
    """Проверяет валидность Lava webhook по HMAC-SHA256 подписи"""
    try:
        parsed = json.loads(body_bytes)
        sorted_body = json.dumps(parsed, sort_keys=True, separators=(',', ':')).encode('utf-8')

        sig = hmac.new(
            Config.LAVA_ADDITIONAL_KEY.encode('utf-8'),
            sorted_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(sig, signature_header)
    except Exception as e:
        print(f"Ошибка проверки подписи: {e}")
        return False


def extract_user_id(order_id):
    """Извлекает user_id из order_id формата 'ord{user_id}t{ts}' или '{user_id}_{ts}'"""
    match = re.match(r'ord(\d+)t\d+', order_id)
    if match:
        return int(match.group(1))
    if '_' in order_id:
        return int(order_id.split('_')[0])
    raise ValueError(f"Неизвестный формат order_id: {order_id}")


@app.route('/webhook', methods=['POST'])
def lava_webhook():
    try:
        signature = request.headers.get('Authorization')
        raw_body = request.get_data()

        if not signature or not verify_signature(raw_body, signature):
            print("❌ ОШИБКА ПОДПИСИ!")
            return jsonify({"error": "Invalid signature"}), 400

        data = request.json
        if not data:
            return jsonify({"error": "No JSON payload"}), 400

        status = data.get('status')
        order_id = data.get('order_id')
        amount = float(data.get('amount', 0))

        print(f"📦 Webhook: order={order_id} status={status} amount={amount}")

        if status == 'success':
            try:
                user_id = extract_user_id(order_id)

                if db.check_and_mark_invoice(order_id, user_id, amount):
                    db.update_balance(user_id, amount)
                    # Начисляем реферальное вознаграждение
                    ref_result = db.reward_referrer(user_id, amount)
                    if ref_result:
                        referrer_id, reward = ref_result
                        try:
                            bot.send_message(referrer_id, f"💸 Вам начислено {reward}₽ — реферальное вознаграждение!")
                        except Exception:
                            pass
                    notify_payment(user_id, amount, "Lava (webhook)")
                    bot.send_message(user_id, f"✅ Оплата прошла! Баланс пополнен на {amount:.0f}₽")
                    print(f"💰 Баланс выдан пользователю {user_id}")
                else:
                    print(f"⚠️ Чек {order_id} уже обработан, игнорируем дубль.")

            except Exception as e:
                print(f"Ошибка начисления (webhook): {e}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Глобальная ошибка сервера: {e}")
        return jsonify({"error": str(e)}), 500


def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)