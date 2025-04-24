from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Flask приложение
app = Flask(__name__)
bot = Bot(token=TOKEN)

# Создаем Telegram-приложение
application = Application.builder().token(TOKEN).build()

# Импортируем функцию настройки бота
from LumaMapBot import configure_handlers
application = configure_handlers(application)

# Webhook для Telegram
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.process_update(update)
    return "ok"

# Корневая страница (проверка)
@app.route("/", methods=["GET"])
def home():
    return "✅ Бот работает на Render!"

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    webhook_url = f"https://assem-7duv.onrender.com/{TOKEN}"
    success = application.bot.set_webhook(url=webhook_url)
    return f"Webhook установлен: {success}, URL: {webhook_url}"

if __name__ == "__main__":
    app.run()