import requests
import time
import urllib3
from config import Config
from database.db import Database

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MarzbanService:
    def __init__(self):
        self.url = Config.MARZBAN_URL.strip().rstrip('/')
        self.token = None

    def _auth(self):
        try:
            res = requests.post(
                f"{self.url}/api/admin/token",
                data={"username": Config.MARZBAN_LOGIN, "password": Config.MARZBAN_PASSWORD},
                verify=False, timeout=10
            )
            if res.status_code == 200:
                self.token = res.json().get("access_token")
                return True
        except Exception as e:
            print(f"Marzban auth error: {e}")
        return False

    def _headers(self):
        if not self.token:
            self._auth()
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _request_with_retry(self, method, path, **kwargs):
        """Выполняет запрос к Marzban API с авто-ре-авторизацией при 401"""
        headers = self._headers()
        res = method(f"{self.url}{path}", headers=headers, verify=False, **kwargs)
        if res.status_code == 401:
            self._auth()
            headers = self._headers()
            res = method(f"{self.url}{path}", headers=headers, verify=False, **kwargs)
        return res

    def get_vless_inbounds(self):
        """Получает список VLESS inbound тегов"""
        try:
            res = self._request_with_retry(requests.get, "/api/inbounds", timeout=5)
            if res.status_code == 200:
                data = res.json()
                if "vless" in data:
                    return [i["tag"] for i in data["vless"] if "tag" in i]
        except Exception as e:
            print(f"Error fetching inbounds: {e}")
        return []

    def _build_subscription_link(self, data):
        """Собирает ссылку подписки из ответа API"""
        link = data.get('subscription_url', '')
        if link and not link.startswith('http'):
            link = link.lstrip('/')
            link = f"{self.url}/{link}"
        if not link and 'token' in data:
            link = f"{self.url}/sub/{data['token']}"
        return link or None

    def get_user_link(self, user_id):
        """Возвращает ссылку на подписку (если пользователь существует), не изменяя сроки."""
        username = f"user_{user_id}"
        try:
            res = self._request_with_retry(requests.get, f"/api/user/{username}")
            if res.status_code == 200:
                return self._build_subscription_link(res.json())
        except Exception as e:
            print(f"Error fetching Marzban link: {e}")
        return None

    def add_days(self, user_id, days, cluster_tag=None):
        username = f"user_{user_id}"

        try:
            res = self._request_with_retry(requests.get, f"/api/user/{username}")
            now = int(time.time())

            if res.status_code == 200:
                # Юзер существует — продлеваем
                user_data = res.json()
                current_expire = user_data.get('expire', 0) or 0
                
                if days > 0:
                    user_data['expire'] = Database.calc_expiry(max(current_expire, now), days)
                    user_data['status'] = "active"
                    self._request_with_retry(
                        requests.put, f"/api/user/{username}",
                        json=user_data
                    )
                elif days == 0 and current_expire != 0:
                    # Навсегда: expire=0
                    user_data['expire'] = 0
                    user_data['status'] = "active"
                    self._request_with_retry(
                        requests.put, f"/api/user/{username}",
                        json=user_data
                    )

            elif days >= 0:
                # Юзер не существует — создаём
                new_expire = 0 if days == 0 else Database.calc_expiry(now, days)
                if cluster_tag:
                    vless_inbounds = [cluster_tag]
                else:
                    vless_inbounds = self.get_vless_inbounds()
                payload = {
                    "username": username,
                    "proxies": {"vless": {"flow": "xtls-rprx-vision"}},
                    "inbounds": {"vless": vless_inbounds} if vless_inbounds else {},
                    "expire": new_expire,
                    "data_limit": 0,
                    "status": "active"
                }
                self._request_with_retry(requests.post, "/api/user", json=payload)

            # Финальный запрос ссылки
            final_res = self._request_with_retry(requests.get, f"/api/user/{username}")
            if final_res.status_code == 200:
                return self._build_subscription_link(final_res.json())

        except Exception as e:
            print(f"Error Marzban: {e}")
        return None

    def delete_user(self, user_id):
        """Удаляет пользователя из Marzban"""
        username = f"user_{user_id}"
        try:
            res = self._request_with_retry(requests.delete, f"/api/user/{username}")
            if res.status_code in (200, 204, 404):
                return True
        except Exception as e:
            print(f"Error deleting user from Marzban: {e}")
        return False