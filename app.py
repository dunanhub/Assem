from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio

# Загружаем токен
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Flask приложение
app = Flask(__name__)

# Telegram Application
application = Application.builder().token(TOKEN).build()

# Импорт хендлеров
from LumaMapBot import configure_handlers
configure_handlers(application)

# Асинхронный запуск и установка webhook
async def startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
    print("✅ Webhook установлен и бот запущен")

@app.before_first_request
def before_first_request():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(startup())

# Webhook обработка
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)

    async def handle():
        await application.process_update(update)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(handle())

    return "ok"

# Корневая страница
@app.route("/")
def home():
    return "✅ LumaMapBot работает!"

# Запуск Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
