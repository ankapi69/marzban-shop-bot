import requests
from config import Config

class CryptoBot:
    def __init__(self):
        self.base_url = "https://pay.crypt.bot/api"
        self.headers = {"Crypto-Pay-API-Token": Config.CRYPTO_BOT_TOKEN}

    def create_invoice(self, amount):
        """
        Создает счет в CryptoBot.
        Вход: сумма в рублях (amount).
        Бот сам предложит оплатить в USDT, TON, BTC и сконвертирует по курсу.
        """
        url = f"{self.base_url}/createInvoice"
        data = {
            "amount": str(amount),
            "currency_type": "fiat",
            "fiat": "RUB",
            # Какие монеты принимать (можно добавить ETH, LTC, BNB)
            "accepted_assets": "USDT,TON,BTC,ETH,LTC,TRX" 
        }
        try:
            response = requests.post(url, json=data, headers=self.headers)
            res = response.json()
            
            if res.get('ok'):
                # Возвращаем ссылку на оплату и ID счета
                return res['result']['pay_url'], res['result']['invoice_id']
            else:
                print(f"❌ Ошибка CryptoBot Create: {res}")
        except Exception as e:
            print(f"❌ Ошибка запроса CryptoBot: {e}")
        return None, None

    def check_invoice(self, invoice_id):
        """
        Проверяет статус счета по его ID.
        Возвращает True, если оплачено.
        """
        url = f"{self.base_url}/getInvoices"
        try:
            response = requests.get(url, params={"invoice_ids": invoice_id}, headers=self.headers)
            res = response.json()
            
            if res.get('ok') and res['result']['items']:
                status = res['result']['items'][0]['status']
                # Статусы бывают: active, paid, expired
                return status == 'paid'
        except Exception as e:
            print(f"❌ Ошибка проверки CryptoBot: {e}")
        return False