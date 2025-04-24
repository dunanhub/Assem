from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio

# Загрузка токена
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Flask-приложение
app = Flask(__name__)

# Telegram-приложение
application = Application.builder().token(TOKEN).build()

# Хендлеры
from LumaMapBot import configure_handlers
configure_handlers(application)

# Асинхронный запуск бота (и webhook)
async def startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
    print("✅ Webhook установлен и бот запущен")

# Выполняем startup перед первым запросом
@app.before_first_request
def before_first_request():
    asyncio.run(startup())

# Обработка webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)

    async def process():
        await application.process_update(update)

    # Безопасный вызов из sync контекста
    return asyncio.run(process())

# Корневая страница
@app.route("/")
def home():
    return "✅ LumaMapBot запущен на Render!"

# Запуск
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
