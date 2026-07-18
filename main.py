import telebot
from telebot import apihelper
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import TOKEN

apihelper.ENABLE_MIDDLEWARE = True
bot = telebot.TeleBot(TOKEN)

# Хранилище данных пользователей в памяти
user_profiles = {}   # chat_id -> dict с данными анкеты
user_states = {}     # chat_id -> текущий шаг анкеты

STEPS = ['name', 'phone', 'city', 'profession', 'experience', 'salary', 'shift']
STEP_QUESTIONS = {
    'name':       "👤 Введите ваше имя:",
    'phone':      "📞 Введите номер телефона:",
    'city':       "🏙 Введите ваш город:",
    'profession': "🔧 Укажите вашу профессию:",
    'experience': "📋 Укажите опыт работы (лет):",
    'salary':     "💰 Желаемая зарплата (руб/мес):",
    'shift':      "⛺ Желаемый срок вахты (например: 30/30, 60/30):",
}
STEP_LABELS = {
    'name':       'Имя',
    'phone':      'Телефон',
    'city':       'Город',
    'profession': 'Профессия',
    'experience': 'Опыт',
    'salary':     'Зарплата',
    'shift':      'Срок вахты',
}

def worker_menu_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('👤 Мои данные'), KeyboardButton('⛺ Моя вахта'))
    markup.add(KeyboardButton('💰 Зарплата'), KeyboardButton('💸 Расходы'))
    markup.add(KeyboardButton('🔍 Найти работу'))
    markup.add(KeyboardButton('🗑 Удалить анкету'))
    markup.add(KeyboardButton('🏠 Главное меню'))
    return markup

def main_menu_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        KeyboardButton('🔍 Ищу работу'),
        KeyboardButton('🏢 Работодатель'),
        KeyboardButton('ℹ️ О проекте')
    )
    return markup

# ── Логирование входящих сообщений ───────────────────────────

@bot.middleware_handler(update_types=['message'])
def log_message(bot_instance, message):
    print(f"[LOG] chat_id={message.chat.id} | text={message.text!r}")

# ── Главное меню ──────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def start(message):
    user_states.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "Привет! Выбери нужный раздел:", reply_markup=main_menu_markup())

@bot.message_handler(func=lambda m: m.text == '🏠 Главное меню')
def main_menu(message):
    user_states.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu_markup())

# ── Меню работника ────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '🔍 Ищу работу')
def looking_for_job(message):
    user_states.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🔍 Меню работника:", reply_markup=worker_menu_markup())

@bot.message_handler(func=lambda m: m.text == '⛺ Моя вахта')
def my_shift(message):
    bot.send_message(message.chat.id, "⛺ Информация о текущей вахте")

@bot.message_handler(func=lambda m: m.text == '💰 Зарплата')
def salary(message):
    bot.send_message(message.chat.id, "💰 Раздел зарплаты")

@bot.message_handler(func=lambda m: m.text == '💸 Расходы')
def expenses(message):
    bot.send_message(message.chat.id, "💸 Раздел расходов")

@bot.message_handler(func=lambda m: m.text == '🔍 Найти работу')
def find_job(message):
    bot.send_message(message.chat.id, "🔍 Поиск вакансий")

# ── Анкета работника ──────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '👤 Мои данные')
def my_data(message):
    cid = message.chat.id
    profile = user_profiles.get(cid)
    if profile:
        # Показать заполненный профиль
        lines = [f"👤 *Ваш профиль:*"]
        for step in STEPS:
            lines.append(f"• {STEP_LABELS[step]}: {profile.get(step, '—')}")
        lines.append("\nНажмите *Изменить анкету*, чтобы заполнить заново.")
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton('✏️ Изменить анкету'))
        markup.add(KeyboardButton('🏠 Главное меню'))
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown", reply_markup=markup)
    else:
        start_questionnaire(cid)

@bot.message_handler(func=lambda m: m.text == '✏️ Изменить анкету')
def edit_profile(message):
    start_questionnaire(message.chat.id)

def start_questionnaire(cid):
    user_states[cid] = 0
    user_profiles[cid] = {}
    bot.send_message(cid, "📝 Заполним вашу анкету! Можно отменить командой /cancel\n\n" + STEP_QUESTIONS['name'],
                     reply_markup=ReplyKeyboardRemove())

@bot.message_handler(commands=['cancel'])
def cancel(message):
    cid = message.chat.id
    if cid in user_states:
        user_states.pop(cid)
        user_profiles.pop(cid, None)
        bot.send_message(cid, "❌ Заполнение анкеты отменено.", reply_markup=worker_menu_markup())
    else:
        bot.send_message(cid, "Нечего отменять.", reply_markup=worker_menu_markup())

@bot.message_handler(func=lambda m: m.chat.id in user_states)
def handle_questionnaire(message):
    cid = message.chat.id
    step_index = user_states[cid]
    step_key = STEPS[step_index]

    user_profiles[cid][step_key] = message.text

    next_index = step_index + 1
    if next_index < len(STEPS):
        user_states[cid] = next_index
        next_key = STEPS[next_index]
        bot.send_message(cid, STEP_QUESTIONS[next_key])
    else:
        # Анкета завершена
        user_states.pop(cid)
        profile = user_profiles[cid]
        lines = ["✅ *Анкета сохранена!*\n"]
        for step in STEPS:
            lines.append(f"• {STEP_LABELS[step]}: {profile.get(step, '—')}")
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown", reply_markup=worker_menu_markup())

# ── Удаление анкеты ──────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '🗑 Удалить анкету')
def delete_profile_confirm(message):
    cid = message.chat.id
    if not user_profiles.get(cid):
        bot.send_message(cid, "У вас нет сохранённой анкеты.")
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('✅ Да, удалить'), KeyboardButton('❌ Нет, оставить'))
    bot.send_message(cid, "⚠️ Вы уверены, что хотите удалить анкету?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '✅ Да, удалить')
def delete_profile_yes(message):
    cid = message.chat.id
    user_profiles.pop(cid, None)
    bot.send_message(cid, "🗑 Анкета удалена.", reply_markup=worker_menu_markup())

@bot.message_handler(func=lambda m: m.text == '❌ Нет, оставить')
def delete_profile_no(message):
    bot.send_message(message.chat.id, "Анкета сохранена.", reply_markup=worker_menu_markup())

# ── Прочие разделы ────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '🏢 Работодатель')
def employer(message):
    bot.send_message(message.chat.id,
        "🏢 Раздел «Работодатель»\n\n"
        "Здесь вы можете разместить вакансию и найти подходящих кандидатов.")

@bot.message_handler(func=lambda m: m.text == 'ℹ️ О проекте')
def about(message):
    bot.send_message(message.chat.id,
        "ℹ️ О проекте\n\n"
        "Vahta-bot — платформа для поиска работы и сотрудников.\n"
        "Мы помогаем соискателям и работодателям найти друг друга быстро и удобно.")

print("Бот запущен")

bot.infinity_polling()
