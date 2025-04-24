import os
import json
import hashlib
import re
import asyncio
import qrcode
import uuid
from io import BytesIO
from datetime import datetime
from types import SimpleNamespace
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
)
from telegram.ext import filters
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile,
)

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

FULLNAME, EMAIL, PHONE, PASSWORD, CONFIRM_PASSWORD = range(5)
LOGIN_EMAIL, LOGIN_PASSWORD = range(5, 7)
EDIT_FULLNAME, EDIT_EMAIL, EDIT_PHONE = range(7, 10)
CHANGE_PASSWORD = 10
EVENT_TITLE, EVENT_DESCRIPTION, EVENT_DATE, EVENT_LOCATION, EVENT_PRICE, EVENT_IMAGE = range(11, 17)
FILTER_PRICE = range(100)
CHOOSE_TICKET_QTY, CONFIRM_PAYMENT = range(200, 202)
NEWS_DESCRIPTION, NEWS_IMAGE = range(300, 302)


price_ranges = [
    (0, 0, "Бесплатно"),
    (1_000, 5_000, "от 1000 до 5000 тг"),
    (5_001, 10_000, "от 5000 до 10000 тг"),
    (10_001, 50_000, "от 10000 до 50000 тг"),
    (50_001, 100_000, "от 50000 до 100000 тг"),
    (100_001, 500_000, "от 100000 до 500000 тг")
]


class UserDatabase:
    def __init__(self, filename='users.json'):
        self.filename = filename
        self.data = self._load_data()
    
    def _load_data(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'users': []}
    
    def _save_data(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def user_exists(self, email=None, user_id=None):
        for user in self.data['users']:
            if user.get('email') == email or user.get('id') == user_id:
                return True
        return False
    
    def add_user(self, user_data):
        self.data['users'].append(user_data)
        self._save_data()

    def update_user(self, user_id, key, value):
        for user in self.data['users']:
            if user['id'] == user_id:
                user[key] = value
                self._save_data()
                return True
        return False
    
    def toggle_notifications(self, user_id):
        for user in self.data['users']:
            if user['id'] == user_id:
                current = user.get("notifications", True)
                user["notifications"] = not current
                self._save_data()
                return user["notifications"]
        return None

def load_news():
    try:
        with open("news.json", "r", encoding="utf-8") as f:
            return json.load(f).get("news", [])
    except:
        return []

def save_news(news_item):
    if not os.path.exists("news.json"):
        with open("news.json", "w", encoding="utf-8") as f:
            json.dump({"news": [news_item]}, f, indent=4, ensure_ascii=False)
    else:
        with open("news.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        data["news"].append(news_item)
        with open("news.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

user_db = UserDatabase()

def load_events(filename='events.json'):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('events', [])
    except Exception as e:
        print(f"Ошибка загрузки мероприятий: {e}")
        return []

def save_event(event, filename='events.json'):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {'events': []}
        data['events'].append(event)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения мероприятия: {e}")


async def delete_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'messages_to_delete' in context.user_data:
        for msg_id in context.user_data['messages_to_delete']:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=msg_id
                )
            except Exception as e:
                print(f"Ошибка при удалении сообщения {msg_id}: {e}")
        context.user_data['messages_to_delete'] = []

def get_price_filter_keyboard():
    keyboard = [[InlineKeyboardButton(label, callback_data=f"filter_{min}_{max}")]
                for min, max, label in price_ranges]
    keyboard.append([InlineKeyboardButton("♻️ Сбросить фильтр", callback_data="reset_filter")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    context.user_data['messages_to_delete'] = []
    
    user = update.effective_user
    keyboard = [
        [
            InlineKeyboardButton("Войти", callback_data='login'),
            InlineKeyboardButton("Регистрация", callback_data='register'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await update.message.reply_text(
        f"👋 Добро пожаловать в LumaMap, {user.first_name}!\n\n"
        "🚀 Для начала работы пройдите авторизацию:",
        reply_markup=reply_markup
    )
    context.user_data['start_message_id'] = message.message_id

async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['messages_to_delete'] = []

    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=context.user_data.get('start_message_id')
        )
    except Exception as e:
        print(f"Ошибка удаления стартового сообщения: {e}")

    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📧 Введите ваш email:"
    )

    context.user_data['messages_to_delete'].append(message.message_id)
    return LOGIN_EMAIL

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    context.user_data.setdefault('messages_to_delete', [])
    print(f"DEBUG: Начало регистрации. messages_to_delete: {context.user_data['messages_to_delete']}")
    
    await query.edit_message_text("📝 Введите ваше ФИО:")
    return FULLNAME

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_data = next((u for u in user_db.data['users'] if u['id'] == user.id), None)
    if not admin_data or not admin_data.get("is_admin"):
        await update.message.reply_text("🚫 Только администратор может подтверждать оплату.")
        return

    if not context.args or not context.args[0].startswith("@"):
        await update.message.reply_text("⚠️ Используйте: /confirm @username")
        return

    username = context.args[0][1:]
    buyer = next((u for u in user_db.data['users'] if u.get("username") == username), None)

    if not buyer:
        await update.message.reply_text("❌ Пользователь не найден.")
        return

    user_id = buyer['id']
    pending = [t for t in context.application.bot_data.get('pending_payments', []) if t['user_id'] == user_id]

    if not pending:
        await update.message.reply_text("❌ Нет ожидающих покупок у этого пользователя.")
        return

    os.makedirs("tickets", exist_ok=True)

    if not os.path.exists("tickets.json"):
        tickets_data = {"tickets": []}
    else:
        with open("tickets.json", "r", encoding="utf-8") as f:
            tickets_data = json.load(f)

    for ticket_data in pending:
        codes = []
        for i in range(ticket_data['qty']):
            code = f"{user_id}_{ticket_data['event_title']}_{i}_{datetime.now().timestamp()}"
            codes.append(code)
            qr_path = f"tickets/{code}.png"
            qrcode.make(code).save(qr_path)

            with open(qr_path, 'rb') as f:
                await context.bot.send_photo(chat_id=user_id, photo=f, caption=f"🎫 Билет #{i+1}")

        ticket_data['codes'] = codes
        ticket_data['datetime'] = datetime.now().isoformat()
        tickets_data["tickets"].append(ticket_data)

    with open("tickets.json", "w", encoding="utf-8") as f:
        json.dump(tickets_data, f, indent=4, ensure_ascii=False)

    context.application.bot_data['pending_payments'] = [
        t for t in context.application.bot_data.get('pending_payments', []) if t['user_id'] != user_id
    ]
    buyer['tickets_bought'] = buyer.get('tickets_bought', 0) + sum(p['qty'] for p in pending)
    user_db._save_data()

    await update.message.reply_text(f"✅ Покупка подтверждена. Пользователю @{username} отправлены билеты.")




def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🎭 Мероприятия в городе", callback_data="events")],
        [InlineKeyboardButton("🎫 Мои билеты", callback_data="tickets")],
        [InlineKeyboardButton("📰 Новости и анонсы", callback_data="news")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("🚪 Выйти из системы", callback_data="logout")]
    ]
    return InlineKeyboardMarkup(keyboard)



def get_settings_menu():
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data="settings_profile")],
        [InlineKeyboardButton("🔕 Отключить уведомления", callback_data="settings_notifications")],
        [InlineKeyboardButton("🔑 Сменить пароль", callback_data="settings_change_password")],
        [InlineKeyboardButton("📞 Тех. поддержка", callback_data="settings_support")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_edit_profile_menu():
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить ФИО", callback_data="edit_fullname")],
        [InlineKeyboardButton("📧 Изменить Email", callback_data="edit_email")],
        [InlineKeyboardButton("📱 Изменить Телефон", callback_data="edit_phone")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="settings_profile")],
        [InlineKeyboardButton("❌ Отменить", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def open_settings(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    message = await query.message.reply_text(
        "⚙️ Вы вошли в раздел *Настройки*.",
        parse_mode="Markdown",
        reply_markup=get_settings_menu()
    )
    context.user_data['messages_to_delete'] = [message.message_id]

async def settings_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    whatsapp_url = "https://wa.me/77059821077"

    keyboard = [
        [InlineKeyboardButton("📲 Перейти в WhatsApp", url=whatsapp_url)],
        [InlineKeyboardButton("⬅️ Назад", callback_data="settings")]
    ]

    message = await query.message.reply_text(
        "📞 Вы можете связаться с нашей тех. поддержкой по WhatsApp:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['messages_to_delete'] = [message.message_id]


async def back_to_main(update, context):
    await delete_previous_messages(update, context)

    context.user_data.pop("filter_min_price", None)
    context.user_data.pop("filter_max_price", None)

    message = await update.callback_query.message.reply_text(
        "🏠 Главное меню. Выберите действие:",
        reply_markup=get_main_menu()
    )
    context.user_data['messages_to_delete'] = [message.message_id]

async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    user_id = query.from_user.id
    new_status = user_db.toggle_notifications(user_id)

    status_text = "❌ Уведомления отключены." if new_status is False else "✅ Уведомления включены."

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="settings")]]
    
    message = await query.message.reply_text(
        f"{status_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['messages_to_delete'] = [message.message_id]

async def open_profile(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    user_id = query.from_user.id
    user = next((u for u in user_db.data['users'] if u['id'] == user_id), None)

    if not user:
        message = await query.message.reply_text("❌ Пользователь не найден.")
        context.user_data['messages_to_delete'] = [message.message_id]
        return

    user.setdefault('points', 0)
    user.setdefault('tickets_bought', 0)

    profile_text = (
        f"👤 *Ваш профиль:*\n"
        f"*ID:* `{user['id']}`\n"
        f"*ФИО:* {user['fullname']}\n"
        f"*Почта:* {user['email']}\n"
        f"*Телефон:* {user['phone']}\n"
        f"*Очки:* {user['points']}\n"
        f"*Билетов куплено:* {user['tickets_bought']}"
    )

    keyboard = [
        [InlineKeyboardButton("✏️ Изменить данные", callback_data="edit_profile")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="settings")]
    ]

    message = await query.message.reply_text(
        profile_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['messages_to_delete'] = [message.message_id]

async def edit_profile(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    message = await query.message.reply_text(
        "✏️ Что вы хотите изменить?",
        reply_markup=get_edit_profile_menu()
    )
    context.user_data['messages_to_delete'] = [message.message_id]

async def request_edit(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['edit_field'] = query.data.split('_')[-1]
    await delete_previous_messages(update, context)

    label = {
        'fullname': 'ФИО',
        'email': 'email',
        'phone': 'телефон'
    }[context.user_data['edit_field']]

    message = await query.message.reply_text(f"✏️ Введите новый {label}:")
    context.user_data['messages_to_delete'] = [message.message_id]

    if context.user_data['edit_field'] == 'fullname':
        return EDIT_FULLNAME
    elif context.user_data['edit_field'] == 'email':
        return EDIT_EMAIL
    elif context.user_data['edit_field'] == 'phone':
        return EDIT_PHONE

async def apply_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get('edit_field')
    user_id = update.effective_user.id
    new_value = update.message.text
    context.user_data['messages_to_delete'].append(update.message.message_id)

    if field == 'email' and not validate_email(new_value):
        msg = await update.message.reply_text("❌ Неверный формат email. Попробуйте снова:")
        context.user_data['messages_to_delete'].append(msg.message_id)
        return EDIT_EMAIL

    if field == 'phone' and not validate_phone(new_value):
        msg = await update.message.reply_text("❌ Неверный формат телефона. Попробуйте снова:")
        context.user_data['messages_to_delete'].append(msg.message_id)
        return EDIT_PHONE

    user_db.update_user(user_id, field, new_value)
    await delete_previous_messages(update, context)

    msg = await update.message.reply_text("✅ Данные обновлены. Возврат в профиль через 5 секунд...")
    await asyncio.sleep(5)

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
    except:
        pass

    class FakeCallbackQuery:
        def __init__(self, user, message):
            self.from_user = user
            self.message = message

        async def answer(self):
            pass

    fake_query_update = Update(
        update_id=update.update_id,
        callback_query=FakeCallbackQuery(update.effective_user, update.message)
    )

    await open_profile(fake_query_update, context)
    return ConversationHandler.END

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    keyboard = [
        [
            InlineKeyboardButton("Войти", callback_data='login'),
            InlineKeyboardButton("Регистрация", callback_data='register'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🚪 Вы вышли из системы.\n\n🔐 Чтобы продолжить, пожалуйста, войдите или зарегистрируйтесь:",
        reply_markup=reply_markup
    )


async def confirm_password_change(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="change_password_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="settings"),
        ]
    ]
    message = await query.message.reply_text(
        "Вы уверены, что хотите изменить пароль?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['messages_to_delete'] = [message.message_id]

async def request_new_password(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    message = await query.message.reply_text("🔑 Введите новый пароль:")
    context.user_data['messages_to_delete'] = [message.message_id]
    return CHANGE_PASSWORD

async def apply_new_password(update, context):
    new_password = update.message.text
    context.user_data['messages_to_delete'].append(update.message.message_id)

    user_id = update.effective_user.id
    hashed = hash_password(new_password)
    user_db.update_user(user_id, "password", hashed)

    await delete_previous_messages(update, context)
    confirm_message = await update.message.reply_text("✅ Пароль успешно изменён. Возврат через 5 секунд...")
    await asyncio.sleep(5)

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=confirm_message.message_id)
    except:
        pass

    class FakeCallbackQuery:
        def __init__(self, user, message):
            self.from_user = user
            self.message = message

        async def answer(self):
            pass

    fake_query_update = Update(
        update_id=update.update_id,
        callback_query=FakeCallbackQuery(update.effective_user, update.message)
    )

    await open_settings(fake_query_update, context)
    return ConversationHandler.END



async def login_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text
    context.user_data['messages_to_delete'].append(update.message.message_id)

    context.user_data['login_email'] = email
    message = await update.message.reply_text("🔑 Введите пароль:")
    context.user_data['messages_to_delete'].append(message.message_id)
    return LOGIN_PASSWORD

async def login_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    email = context.user_data['login_email']
    context.user_data['messages_to_delete'].append(update.message.message_id)

    for user in user_db.data['users']:
        if user['email'] == email and user['password'] == hash_password(password):
            await delete_previous_messages(update, context)
            msg = await update.message.reply_text(
                f"✅ Вы вошли как {user['fullname']}. Добро пожаловать в LumaMap!"
                "\n\nВыберите действие:",
                reply_markup=get_main_menu()
            )
            context.user_data['messages_to_delete'].append(msg.message_id)
            return ConversationHandler.END

    message = await update.message.reply_text("❌ Неверный email или пароль. Попробуйте снова.")
    context.user_data['messages_to_delete'].append(message.message_id)
    return LOGIN_EMAIL



async def fullname_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data.setdefault('messages_to_delete', [])
        
        print(f"DEBUG: Получено ФИО: {update.message.text}")
        
        context.user_data['messages_to_delete'].append(update.message.message_id)
        context.user_data['fullname'] = update.message.text
        
        message = await update.message.reply_text("📧 Введите ваш email:")
        context.user_data['messages_to_delete'].append(message.message_id)
        
        print(f"DEBUG: Переход к EMAIL. Сообщения для удаления: {context.user_data['messages_to_delete']}")
        return EMAIL
        
    except Exception as e:
        print(f"ERROR в fullname_input: {str(e)}")
        return ConversationHandler.END

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

async def email_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['messages_to_delete'].append(update.message.message_id)
    
    email = update.message.text
    if not validate_email(email):
        message = await update.message.reply_text("❌ Неверный формат email. Попробуйте снова:")
        context.user_data['messages_to_delete'].append(message.message_id)
        return EMAIL
    
    if user_db.user_exists(email=email):
        message = await update.message.reply_text("⚠️ Этот email уже зарегистрирован. Введите другой:")
        context.user_data['messages_to_delete'].append(message.message_id)
        return EMAIL
    
    context.user_data['email'] = email
    message = await update.message.reply_text("📱 Введите ваш телефон в формате +71234567890:")
    context.user_data['messages_to_delete'].append(message.message_id)
    return PHONE

def validate_phone(phone):
    return re.match(r"^\+7\d{10}$", phone)

async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['messages_to_delete'].append(update.message.message_id)
    
    phone = update.message.text
    if not validate_phone(phone):
        message = await update.message.reply_text("❌ Неверный формат телефона. Введите в формате +71234567890:")
        context.user_data['messages_to_delete'].append(message.message_id)
        return PHONE
    
    context.user_data['phone'] = phone
    message = await update.message.reply_text("🔑 Придумайте пароль:")
    context.user_data['messages_to_delete'].append(message.message_id)
    return PASSWORD

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

async def password_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['messages_to_delete'].append(update.message.message_id)
    
    context.user_data['password'] = update.message.text
    message = await update.message.reply_text("🔒 Повторите пароль для подтверждения:")
    context.user_data['messages_to_delete'].append(message.message_id)
    return CONFIRM_PASSWORD

async def confirm_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['messages_to_delete'].append(update.message.message_id)
    
    password = context.user_data['password']
    confirm = update.message.text
    
    if password != confirm:
        message = await update.message.reply_text("❌ Пароли не совпадают. Введите пароль еще раз:")
        context.user_data['messages_to_delete'].append(message.message_id)
        return PASSWORD
    
    context.user_data['password'] = hash_password(password)
    
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if user_db.user_exists(user_id=user_id):
        message = await update.message.reply_text("⚠️ Вы уже зарегистрированы!")
        context.user_data['messages_to_delete'].append(message.message_id)
        return ConversationHandler.END
    
    user_data = {
        'id': user_id,
        'username': username,
        'fullname': context.user_data['fullname'],
        'email': context.user_data['email'],
        'phone': context.user_data['phone'],
        'password': context.user_data['password'],
        'is_admin': False,
        'notifications': True
    }
    
    user_db.add_user(user_data)
    
    await delete_previous_messages(update, context)
    
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
    except Exception as e:
        print(f"Ошибка удаления: {e}")
    
    try:
        await context.bot.edit_message_text(
            text=f"🎉 Добро пожаловать в LumaMap, {context.user_data['fullname']}!\n\n"
                 "✅ Регистрация успешно завершена!",
            chat_id=update.effective_chat.id,
            message_id=context.user_data.get('start_message_id'),
            reply_markup=get_main_menu()
        )
    except Exception as e:
        print(f"Ошибка редактирования сообщения: {e}")
    
    return ConversationHandler.END

async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(update, context)

    events = load_events()
    today = datetime.today().date()

    upcoming = [event for event in events if datetime.strptime(event["date"], "%Y-%m-%d").date() >= today]

    filter_min = context.user_data.get("filter_min_price")
    filter_max = context.user_data.get("filter_max_price")

    if filter_min is not None and filter_max is not None:
        def parse_price(price_str):
            digits = re.findall(r"\d+", price_str)
            return int(digits[0]) if digits else 0

        upcoming = [e for e in upcoming if filter_min <= parse_price(e.get("price", "0")) <= filter_max]

    upcoming.sort(key=lambda e: e["date"])

    user_id = update.effective_user.id
    user = next((u for u in user_db.data['users'] if u['id'] == user_id), None)

    keyboard = [
        [InlineKeyboardButton("🔎 Фильтр по цене", callback_data="open_price_filter")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    if user and user.get('is_admin'):
        keyboard.insert(0, [InlineKeyboardButton("🎨 Создать постер", callback_data="create_event_poster")])

    context.user_data['messages_to_delete'] = []

    if not upcoming:
        text = "❌ Нет ближайших мероприятий."
        if filter_min is not None:
            text += f"\n🔍 Применён фильтр: от {filter_min} до {filter_max} тг"
        msg = await update.effective_chat.send_message(text, reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['messages_to_delete'].append(msg.message_id)
        return

    if filter_min is not None:
        filter_text = f"🔍 Фильтр по цене: от {filter_min} до {filter_max} тг"
        msg = await update.effective_chat.send_message(filter_text)
        context.user_data['messages_to_delete'].append(msg.message_id)

    for i, event in enumerate(upcoming):
        text = (
            f"*{event['title']}*\n"
            f"📅 Дата: {event['date']}\n"
            f"📍 Место: {event['location']}\n"
            f"💰 Цена: {event.get('price', 'Бесплатно')}\n"
            f"📝 Oписание: \n{event['description']}"
        )
     
        buttons = [
            [InlineKeyboardButton("🎟 Купить билет", callback_data=f"buy_ticket_id_{event['id']}")]
        ]

        if event.get("image") and os.path.exists(event["image"]):
            with open(event["image"], "rb") as img:
                msg = await update.effective_chat.send_photo(photo=img, caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            msg = await update.effective_chat.send_message(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

        context.user_data['messages_to_delete'].append(msg.message_id)

    menu_msg = await update.effective_chat.send_message("Меню опций:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['messages_to_delete'].append(menu_msg.message_id)

async def create_event_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    user_id = query.from_user.id
    user = next((u for u in user_db.data['users'] if u['id'] == user_id), None)

    if not user or not user.get('is_admin'):
        message = await query.message.reply_text("🚫 У вас нет прав для создания постера.")
        context.user_data['messages_to_delete'] = [message.message_id]
        return

    message = await query.message.reply_text(
        "🖼 Функция создания постера пока находится в разработке.\n"
        "Позже здесь будет интерфейс для выбора мероприятия и генерации постера.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data="events")]
        ])
    )
    context.user_data['messages_to_delete'] = [message.message_id]

async def start_create_event_poster(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    message = await query.message.reply_text("📝 Введите название мероприятия:")
    context.user_data['messages_to_delete'] = [message.message_id]
    return EVENT_TITLE

async def input_event_title(update, context):
    context.user_data['messages_to_delete'].append(update.message.message_id)
    context.user_data['event_title'] = update.message.text

    msg = await update.message.reply_text("📋 Введите описание мероприятия:")
    context.user_data['messages_to_delete'].append(msg.message_id)
    return EVENT_DESCRIPTION

async def input_event_description(update, context):
    context.user_data['messages_to_delete'].append(update.message.message_id)
    context.user_data['event_description'] = update.message.text

    msg = await update.message.reply_text("📅 Введите дату мероприятия в формате ГГГГ-ММ-ДД:")
    context.user_data['messages_to_delete'].append(msg.message_id)
    return EVENT_DATE

async def input_event_date(update, context):
    context.user_data['messages_to_delete'].append(update.message.message_id)
    date_text = update.message.text

    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        msg = await update.message.reply_text("❌ Неверный формат даты. Попробуйте снова (ГГГГ-ММ-ДД):")
        context.user_data['messages_to_delete'].append(msg.message_id)
        return EVENT_DATE

    context.user_data['event_date'] = date_text

    msg = await update.message.reply_text("📍 Введите локацию проведения мероприятия:")
    context.user_data['messages_to_delete'].append(msg.message_id)
    return EVENT_LOCATION

async def input_event_location(update, context):
    context.user_data['messages_to_delete'].append(update.message.message_id)
    context.user_data['event_location'] = update.message.text

    msg = await update.message.reply_text("💰 Введите цену мероприятия (например: 1500 тг или Бесплатно):")
    context.user_data['messages_to_delete'].append(msg.message_id)
    return EVENT_PRICE

async def input_event_price(update, context):
    context.user_data['messages_to_delete'].append(update.message.message_id)
    context.user_data['event_price'] = update.message.text.strip()

    keyboard = [[
        InlineKeyboardButton("📷 Загрузить изображение", callback_data="upload_image"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip_image")
    ]]
    msg = await update.message.reply_text(
        "Хотите загрузить изображение для постера?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['messages_to_delete'].append(msg.message_id)
    return EVENT_IMAGE

async def handle_event_image(update, context):
    photo = update.message.photo[-1] if update.message.photo else None
    context.user_data['messages_to_delete'].append(update.message.message_id)

    if photo:
        file = await context.bot.get_file(photo.file_id)

        os.makedirs("event_images", exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_id = update.message.from_user.id
        file_path = f"event_images/poster_{user_id}_{timestamp}.jpg"

        await file.download_to_drive(file_path)

        context.user_data['event_image'] = file_path

    await save_event_and_back(update, context)
    return ConversationHandler.END

async def prompt_upload_image(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    message = await query.message.reply_text("📤 Пожалуйста, отправьте изображение:")
    context.user_data['messages_to_delete'] = [message.message_id]
    return EVENT_IMAGE

async def skip_event_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    await save_event_and_back(update, context)
    return ConversationHandler.END

async def save_event_and_back(update, context):
    await delete_previous_messages(update, context)

    events = load_events()
    new_event = {
        "id": str(uuid.uuid4()),
        "title": context.user_data['event_title'],
        "description": context.user_data['event_description'],
        "date": context.user_data['event_date'],
        "location": context.user_data['event_location'],
        "image": context.user_data.get('event_image'),
        "price": context.user_data.get("event_price", "Бесплатно")
    }
    events.append(new_event)
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump({"events": events}, f, indent=4, ensure_ascii=False)

    context.user_data.clear()

    await show_events(update, context)

async def open_price_filter(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    msg = await query.message.reply_text("Выберите диапазон цен:", reply_markup=get_price_filter_keyboard())
    context.user_data['messages_to_delete'] = [msg.message_id]


async def apply_price_filter(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    _, min_price, max_price = query.data.split("_")
    context.user_data['filter_min_price'] = int(min_price)
    context.user_data['filter_max_price'] = int(max_price)

    label = next(label for minv, maxv, label in price_ranges if str(minv) == min_price and str(maxv) == max_price)
    msg = await query.message.reply_text(f"📌 Вы выбрали фильтр по цене: *{label}*", parse_mode="Markdown")
    context.user_data['messages_to_delete'] = [msg.message_id]

    await show_events(update, context)

async def reset_price_filter(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    context.user_data.pop("filter_min_price", None)
    context.user_data.pop("filter_max_price", None)

    msg = await query.message.reply_text("Фильтр сброшен.")
    context.user_data['messages_to_delete'] = [msg.message_id]

    await show_events(update, context)


async def start_ticket_purchase(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    event_id = query.data.split("_")[-1]
    context.user_data['selected_event_id'] = event_id

    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data="confirm_buy")],
        [InlineKeyboardButton("❌ Нет", callback_data="events")]
    ]

    msg = await query.message.reply_text("Вы уверены, что хотите купить билет на это мероприятие?", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['messages_to_delete'] = [msg.message_id]

async def ask_ticket_quantity(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    msg = await query.message.reply_text("Введите количество билетов:")
    context.user_data['messages_to_delete'] = [msg.message_id]
    return CHOOSE_TICKET_QTY

async def process_ticket_quantity(update, context):
    qty = int(update.message.text)
    context.user_data['messages_to_delete'].append(update.message.message_id)
    context.user_data['ticket_qty'] = qty

    events = load_events()
    event = next((e for e in events if e["id"] == context.user_data["selected_event_id"]), None)
    price_str = event.get("price", "0")
    price = int(re.findall(r"\d+", price_str)[0]) if re.findall(r"\d+", price_str) else 0
    total = qty * price
    context.user_data['ticket_total_price'] = total

    keyboard = [[
        InlineKeyboardButton("💬 Оплатить через WhatsApp", callback_data="pay_whatsapp")
    ]]
    msg = await update.message.reply_text(
        f"💸 Общая сумма: {total} тг\nНажмите \"Оплатить через WhatsApp\" для завершения.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['messages_to_delete'].append(msg.message_id)
    return CONFIRM_PAYMENT

async def start_whatsapp_payment(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    qty = context.user_data['ticket_qty']
    event_id = context.user_data['selected_event_id']
    event = next((e for e in load_events() if e['id'] == event_id), None)

    if not event:
        await query.message.reply_text("❌ Ошибка: мероприятие не найдено.")
        return

    fullname = update.effective_user.full_name
    message_text = f"Здравствуйте! Я хочу купить {qty} билет(ов) на '{event['title']}' от {fullname}."

    whatsapp_link = f"https://wa.me/77059821077?text={message_text.replace(' ', '%20')}"

    await query.message.reply_text(
        "📲 Нажмите кнопку ниже, чтобы перейти в WhatsApp. Вы будете перенаправлены обратно через 20 секунд.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Открыть WhatsApp", url=whatsapp_link)]])
    )

    context.application.bot_data.setdefault('pending_payments', []).append({
        "user_id": update.effective_user.id,
        "event_title": event['title'],
        "qty": qty,
        "total": context.user_data['ticket_total_price']
    })

    await asyncio.sleep(20)
    await back_to_main(update, context)

async def finalize_purchase(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    user_id = update.effective_user.id
    user = next((u for u in user_db.data['users'] if u['id'] == user_id), None)
    events = load_events()
    event = next((e for e in events if e["id"] == context.user_data["selected_event_id"]), None)
    qty = context.user_data['ticket_qty']
    total = context.user_data['ticket_total_price']

    os.makedirs("tickets", exist_ok=True)
    ticket_ids = []

    context.user_data.setdefault('messages_to_delete', [])

    for i in range(qty):
        ticket_code = f"{user_id}_{event['title']}_{i}_{datetime.now().timestamp()}"
        ticket_ids.append(ticket_code)
        qr = qrcode.make(ticket_code)
        path = f"tickets/{ticket_code}.png"
        qr.save(path)

        with open(path, 'rb') as f:
            photo_msg = await update.effective_chat.send_photo(photo=f, caption=f"🎫 Билет #{i+1}")
            context.user_data['messages_to_delete'].append(photo_msg.message_id)

    ticket_data = {
        "user_id": user_id,
        "event_title": event['title'],
        "qty": qty,
        "total": total,
        "codes": ticket_ids,
        "datetime": datetime.now().isoformat()
    }

    if not os.path.exists("tickets.json"):
        with open("tickets.json", "w", encoding="utf-8") as f:
            json.dump({"tickets": [ticket_data]}, f, indent=4, ensure_ascii=False)
    else:
        with open("tickets.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        data["tickets"].append(ticket_data)
        with open("tickets.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    user['tickets_bought'] = user.get('tickets_bought', 0) + qty
    user_db._save_data()

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]]
    text_msg = await update.effective_chat.send_message(
        f"✅ Вы успешно купили {qty} билет(ов) на *{event['title']}*.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['messages_to_delete'].append(text_msg.message_id)

    return ConversationHandler.END


async def show_my_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(update, context)

    user_id = update.effective_user.id
    today = datetime.today().date()

    tickets = []
    if os.path.exists("tickets.json"):
        with open("tickets.json", "r", encoding="utf-8") as f:
            tickets = json.load(f).get("tickets", [])

    events = load_events()
    future_events = {e['title']: e for e in events if datetime.strptime(e['date'], "%Y-%m-%d").date() >= today}

    user_events = sorted({t["event_title"] for t in tickets if t["user_id"] == user_id and t["event_title"] in future_events})

    if not user_events:
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]]
        msg = await update.callback_query.message.reply_text(
            "🎫 У вас нет активных билетов.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['messages_to_delete'] = [msg.message_id]
        return

    keyboard = [
        [InlineKeyboardButton(title, callback_data=f"tickets_event_{title}")] for title in user_events
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])

    msg = await update.callback_query.message.reply_text("🎟 Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['messages_to_delete'] = [msg.message_id]

async def show_tickets_for_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(update, context)

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    today = datetime.today().date()

    selected_event_title = query.data.replace("tickets_event_", "")

    with open("tickets.json", "r", encoding="utf-8") as f:
        all_tickets = json.load(f)["tickets"]

    events = load_events()
    event = next((e for e in events if e["title"] == selected_event_title), None)

    if not event or datetime.strptime(event["date"], "%Y-%m-%d").date() < today:
        msg = await query.message.reply_text("❌ Это мероприятие уже прошло.")
        context.user_data['messages_to_delete'] = [msg.message_id]
        return

    user_tickets = [
        t for t in all_tickets if t["user_id"] == user_id and t["event_title"] == selected_event_title
    ]

    if not user_tickets:
        msg = await query.message.reply_text("❌ У вас нет билетов на это мероприятие.")
        context.user_data['messages_to_delete'] = [msg.message_id]
        return

    context.user_data['messages_to_delete'] = []

    for ticket in user_tickets:
        for i, code in enumerate(ticket["codes"], 1):
            img_path = f"tickets/{code}.png"
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    msg = await update.effective_chat.send_photo(photo=f, caption=f"🎟 Билет #{i}")
                    context.user_data['messages_to_delete'].append(msg.message_id)

    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="tickets")]])
    msg = await update.effective_chat.send_message("↩️ Вернуться назад", reply_markup=back_button)
    context.user_data['messages_to_delete'].append(msg.message_id)

async def show_news(update, context):
    await delete_previous_messages(update, context)

    user_id = update.effective_user.id
    user = next((u for u in user_db.data['users'] if u['id'] == user_id), None)

    keyboard = []
    if user and user.get("is_admin"):
        keyboard.append([InlineKeyboardButton("✍️ Создать пост", callback_data="create_news_post")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])

    news_list = load_news()
    context.user_data['messages_to_delete'] = []

    if not news_list:
        msg = await update.effective_chat.send_message("❌ Пока нет новостей.", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['messages_to_delete'].append(msg.message_id)
        return

    for news in news_list[::-1]:
        caption = f"{news['description']}\n🕒 {news['datetime'][:16].replace('T', ' ')}"
        if "image" in news and os.path.exists(news["image"]):
            with open(news["image"], "rb") as img:
                msg = await update.effective_chat.send_photo(photo=img, caption=caption)
        else:
            msg = await update.effective_chat.send_message(caption)

        context.user_data['messages_to_delete'].append(msg.message_id)

    menu_msg = await update.effective_chat.send_message("Меню новостей:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['messages_to_delete'].append(menu_msg.message_id)

async def start_news_post(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)
    msg = await query.message.reply_text("📝 Введите текст новости:")
    context.user_data['messages_to_delete'] = [msg.message_id]
    return NEWS_DESCRIPTION

async def news_description_input(update, context):
    context.user_data['messages_to_delete'].append(update.message.message_id)
    context.user_data["news_description"] = update.message.text

    keyboard = [[
        InlineKeyboardButton("📷 Загрузить изображение", callback_data="upload_news_image"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip_news_image")
    ]]
    msg = await update.message.reply_text("Хотите загрузить изображение?", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['messages_to_delete'].append(msg.message_id)
    return NEWS_IMAGE

async def handle_news_image(update, context):
    photo = update.message.photo[-1] if update.message.photo else None
    context.user_data['messages_to_delete'].append(update.message.message_id)

    if photo:
        file = await context.bot.get_file(photo.file_id)
        os.makedirs("news_images", exist_ok=True)
        file_path = f"news_images/news_{update.message.from_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        await file.download_to_drive(file_path)
        context.user_data['news_image'] = file_path

    await finalize_news_post(update, context)
    return ConversationHandler.END

async def skip_news_image(update, context):
    query = update.callback_query
    await query.answer()
    await finalize_news_post(update, context)
    return ConversationHandler.END

async def prompt_news_image_upload(update, context):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)
    msg = await query.message.reply_text("📤 Пожалуйста, отправьте изображение для новости:")
    context.user_data['messages_to_delete'] = [msg.message_id]

async def finalize_news_post(update, context):
    await delete_previous_messages(update, context)

    description = context.user_data.get("news_description", "")
    image_path = context.user_data.get("news_image", None)

    if not description.strip():
        msg = await update.effective_chat.send_message("❌ Текст новости не может быть пустым.")
        context.user_data.setdefault('messages_to_delete', []).append(msg.message_id)
        return

    post = {
        "description": description,
        "datetime": datetime.now().isoformat()
    }
    if image_path:
        post["image"] = image_path

    save_news(post)

    temp_messages = context.user_data.get('messages_to_delete', [])

    context.user_data.clear()
    context.user_data['messages_to_delete'] = temp_messages

    await show_news(update, context)

async def start_create_news_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await delete_previous_messages(update, context)

    msg = await query.message.reply_text("📝 Введите текст новости:")
    context.user_data['messages_to_delete'] = [msg.message_id]
    return NEWS_DESCRIPTION

async def input_news_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['messages_to_delete'].append(update.message.message_id)
    context.user_data["news_description"] = update.message.text

    keyboard = [[
        InlineKeyboardButton("📷 Загрузить изображение", callback_data="upload_news_image"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip_news_image")
    ]]
    msg = await update.message.reply_text("Хотите загрузить изображение?", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['messages_to_delete'].append(msg.message_id)
    return NEWS_IMAGE




async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'messages_to_delete' in context.user_data:
        context.user_data['messages_to_delete'].append(update.message.message_id)
    
    await delete_previous_messages(update, context)
    await update.message.reply_text(
        "❌ Регистрация отменена.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"⚠️ Ошибка: {context.error}")
    if update and update.message:
        message = await update.message.reply_text("❌ Произошла ошибка. Пожалуйста, попробуйте снова.")
        context.user_data.setdefault('messages_to_delete', [])
        context.user_data['messages_to_delete'].append(message.message_id)




def configure_handlers(application):
    # application = Application.builder().token(TOKEN).build()

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler('start', start))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_registration, pattern='^register$')],
        states={
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname_input)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_input)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_input)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_input)],
            CONFIRM_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_password)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True
    )

    login_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_login, pattern='^login$')],
        states={
            LOGIN_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_email_input)],
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
    )

    edit_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(request_edit, pattern="^edit_fullname$|^edit_email$|^edit_phone$")
        ],
        states={
            EDIT_FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_edit)],
            EDIT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_edit)],
            EDIT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_edit)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True
    )

    change_password_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(request_new_password, pattern="^change_password_yes$")],
        states={
            CHANGE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_new_password)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
    )

    create_event_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create_event_poster, pattern="^create_event_poster$")],
        states={
            EVENT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_event_title)],
            EVENT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_event_description)],
            EVENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_event_date)],
            EVENT_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_event_location)],
            EVENT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_event_price)],
            EVENT_IMAGE: [
                MessageHandler(filters.PHOTO, handle_event_image),
                CallbackQueryHandler(skip_event_image, pattern="^skip_image$"),
                CallbackQueryHandler(prompt_upload_image, pattern="^upload_image$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True
    )

    ticket_purchase_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_ticket_quantity, pattern="^confirm_buy$")],
        states={
            CHOOSE_TICKET_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_ticket_quantity)],
            CONFIRM_PAYMENT: [CallbackQueryHandler(finalize_purchase, pattern="^finalize_purchase$")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )

    news_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create_news_post, pattern="^create_news_post$")],
        states={
            NEWS_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_news_description)],
            NEWS_IMAGE: [
                MessageHandler(filters.PHOTO, handle_news_image),
                CallbackQueryHandler(skip_news_image, pattern="^skip_news_image$"),
                CallbackQueryHandler(prompt_news_image_upload, pattern="^upload_news_image$")  # Не забудь!
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True
    )

    application.add_handler(login_handler)
    application.add_handler(conv_handler)
    application.add_handler(edit_conv)
    application.add_handler(change_password_conv)
    application.add_handler(create_event_handler)
    application.add_handler(ticket_purchase_handler)
    application.add_handler(news_conv)
    application.add_handler(CallbackQueryHandler(start, pattern='^login$'))
    application.add_handler(CallbackQueryHandler(logout, pattern='^logout$'))
    application.add_handler(CallbackQueryHandler(open_settings, pattern="^settings$"))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    application.add_handler(CallbackQueryHandler(open_profile, pattern="^settings_profile$"))
    application.add_handler(CallbackQueryHandler(edit_profile, pattern="^edit_profile$"))
    application.add_handler(CallbackQueryHandler(confirm_password_change, pattern="^settings_change_password$"))
    application.add_handler(CallbackQueryHandler(request_new_password, pattern="^change_password_yes$"))
    application.add_handler(CallbackQueryHandler(settings_support, pattern="^settings_support$"))
    application.add_handler(CallbackQueryHandler(toggle_notifications, pattern="^settings_notifications$"))
    application.add_handler(CallbackQueryHandler(show_events, pattern="^events$"))
    application.add_handler(CallbackQueryHandler(create_event_poster, pattern="^create_event_poster$"))
    application.add_handler(CallbackQueryHandler(open_price_filter, pattern="^open_price_filter$"))
    application.add_handler(CallbackQueryHandler(apply_price_filter, pattern="^filter_"))
    application.add_handler(CallbackQueryHandler(reset_price_filter, pattern="^reset_filter$"))
    application.add_handler(CallbackQueryHandler(start_ticket_purchase, pattern="^buy_ticket_"))
    application.add_handler(CallbackQueryHandler(ask_ticket_quantity, pattern="^confirm_buy$"))
    application.add_handler(CallbackQueryHandler(show_events, pattern="^events$"))
    application.add_handler(CallbackQueryHandler(finalize_purchase, pattern="^finalize_purchase$"))
    application.add_handler(CallbackQueryHandler(show_my_tickets, pattern="^tickets$"))
    application.add_handler(CallbackQueryHandler(show_tickets_for_event, pattern="^tickets_event_"))
    application.add_handler(CallbackQueryHandler(show_news, pattern="^news$"))
    application.add_handler(CallbackQueryHandler(prompt_news_image_upload, pattern="^upload_news_image$"))
    application.add_handler(CallbackQueryHandler(start_whatsapp_payment, pattern="^pay_whatsapp$"))
    application.add_handler(CommandHandler("confirm", confirm_payment))

    return application