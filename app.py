from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio

# Загрузка токена
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# Настройка хендлеров
from LumaMapBot import configure_handlers
configure_handlers(application)

# Webhook настройка
async def startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
    print("✅ Webhook установлен и бот запущен")

# Flask хук для запуска при первом HTTP-запросе
@app.before_first_request
def before_first_request():
    asyncio.run(startup())

# Webhook обработчик
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)

    async def handle():
        await application.process_update(update)

    asyncio.run(handle())  # безопасно и стабильно
    return "ok"

@app.route("/")
def home():
    return "✅ LumaMapBot работает!"

if __name__ == "__main__":
    app.run()
