from telebot import TeleBot
from config import Config
from database.db import Database
from services.marzban import MarzbanService
from services.cryptobot import CryptoBot

bot = TeleBot(Config.BOT_TOKEN)
db = Database(Config.DB_PATH)
marzban = MarzbanService()
crypto = CryptoBot()