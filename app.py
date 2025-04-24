from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv
import os
import asyncio

# Загрузка .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Flask app
app = Flask(__name__)

# Telegram Application
application = Application.builder().token(TOKEN).build()

# Настройка хендлеров
from LumaMapBot import configure_handlers
configure_handlers(application)

# Запускаем Application и ставим Webhook
async def run_app():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
    print("✅ Webhook автоматически установлен!")

asyncio.get_event_loop().create_task(run_app())

# Webhook обработчик
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Корневая страница
@app.route("/", methods=["GET"])
def home():
    return "✅ LumaMapBot запущен через Render!"

# (опционально) ручная установка webhook
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    async def setup():
        await application.bot.set_webhook(url=f"https://assem-7duv.onrender.com/{TOKEN}")
        return True
    success = asyncio.get_event_loop().run_until_complete(setup())
    return f"Webhook установлен: {success}"

if __name__ == "__main__":
    app.run()
