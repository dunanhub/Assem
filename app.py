from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio
import threading

# Загрузка токена из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Flask-приложение
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# Настройка хендлеров
from LumaMapBot import configure_handlers
configure_handlers(application)

# Асинхронная инициализация и запуск Telegram-бота
async def startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
    print("✅ Webhook установлен и бот запущен")

# Запускаем startup в фоновом потоке (thread-safe для Flask + asyncio)
def run_bot():
    asyncio.run(startup())

threading.Thread(target=run_bot).start()

# Webhook обработчик
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)

    async def handle():
        await application.process_update(update)

    threading.Thread(target=lambda: asyncio.run(handle())).start()
    return "ok"

# Корневая страница
@app.route("/")
def home():
    return "✅ LumaMapBot работает!"

# Запуск Flask-приложения
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
