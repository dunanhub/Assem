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
application = Application.builder().token(TOKEN).build()

# Настройка хендлеров
from LumaMapBot import configure_handlers
configure_handlers(application)

# Запускаем Telegram-приложение и обновляем webhook
async def startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
    print("✅ Webhook установлен и приложение запущено")

# Запускаем startup сразу при запуске приложения
asyncio.get_event_loop().create_task(startup())

# Webhook обработчик
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Корневая страница
@app.route("/")
def home():
    return "✅ LumaMapBot работает автоматически!"

if __name__ == "__main__":
    app.run()
