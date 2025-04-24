from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Flask приложение
app = Flask(__name__)
bot = Bot(token=TOKEN)

# Создание Telegram-приложения
application = Application.builder().token(TOKEN).build()

# Импорт и настройка хендлеров
from LumaMapBot import configure_handlers
application = configure_handlers(application)

# Webhook обработчик
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot)

    async def process():
        await application.initialize()
        await application.process_update(update)

    asyncio.run(process())
    return "ok"

# Корневая страница
@app.route("/", methods=["GET"])
def home():
    return "✅ Бот работает на Render!"

# Установка webhook
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    webhook_url = f"https://assem-7duv.onrender.com/{TOKEN}"

    async def set_hook():
        await application.initialize()
        return await application.bot.set_webhook(url=webhook_url)

    success = asyncio.run(set_hook())
    return f"Webhook установлен: {success}, URL: {webhook_url}"

if __name__ == "__main__":
    app.run()
