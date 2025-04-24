from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio

# Загрузка токена из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Flask-приложение
app = Flask(__name__)

# Создаём объект Telegram-приложения глобально
application = Application.builder().token(TOKEN).build()

# Настройка хендлеров
from LumaMapBot import configure_handlers
configure_handlers(application)

# Webhook обработчик
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)

    # Используем create_task — не блокирует основной поток
    asyncio.create_task(application.process_update(update))
    return "ok"

# Корневая страница
@app.route("/")
def home():
    return "✅ LumaMapBot работает!"

# Главная функция запуска
async def main():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
    print("✅ Webhook установлен и бот запущен")
    app.run(host="0.0.0.0", port=10000)

# Запуск
if __name__ == "__main__":
    asyncio.run(main())
