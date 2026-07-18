import telebot
from telebot import apihelper
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import TOKEN, ADMIN_ID

apihelper.ENABLE_MIDDLEWARE = True
bot = telebot.TeleBot(TOKEN)

# Хранилище данных пользователей в памяти
user_profiles = {}   # chat_id -> dict с данными анкеты
user_states = {}     # chat_id -> текущий шаг анкеты

# Хранилище вакансий работодателей
vacancies = {}        # chat_id -> list of vacancy dicts
vacancy_states = {}   # chat_id -> текущий шаг создания вакансии

VAC_STEPS = ['profession', 'city', 'company', 'salary', 'schedule', 'contact']
VAC_QUESTIONS = {
    'profession': "1️⃣ Название профессии:",
    'city':       "2️⃣ Город:",
    'company':    "3️⃣ Компания / объект:",
    'salary':     "4️⃣ Зарплата (руб/мес):",
    'schedule':   "5️⃣ График вахты (например: 30/30, 60/30):",
    'contact':    "6️⃣ Контакт для связи (телефон или @username):",
}
VAC_LABELS = {
    'profession': 'Профессия',
    'city':       'Город',
    'company':    'Компания/объект',
    'salary':     'Зарплата',
    'schedule':   'График',
    'contact':    'Контакт',
}

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
    markup.add(KeyboardButton('📊 Отчёт'), KeyboardButton('❓ Помощь'))
    markup.add(KeyboardButton('🏠 Главное меню'))
    return markup

def employer_menu_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('➕ Добавить вакансию'), KeyboardButton('📋 Мои вакансии'))
    markup.add(KeyboardButton('👥 Найти работников'))
    markup.add(KeyboardButton('🏠 Главное меню'))
    return markup

def main_menu_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        KeyboardButton('🔍 Ищу работу'),
        KeyboardButton('🏢 Работодатель'),
        KeyboardButton('ℹ️ О проекте')
    )
    markup.add(KeyboardButton('👨‍💼 Админ панель'))
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

@bot.message_handler(commands=['shift'])
@bot.message_handler(func=lambda m: m.text == '⛺ Моя вахта')
def my_shift(message):
    bot.send_message(message.chat.id, "⛺ Информация о текущей вахте")

@bot.message_handler(commands=['salary'])
@bot.message_handler(func=lambda m: m.text == '💰 Зарплата')
def salary(message):
    bot.send_message(message.chat.id, "💰 Раздел зарплаты")

@bot.message_handler(commands=['expenses'])
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
    elif cid in vacancy_states:
        vacancy_states.pop(cid)
        if vacancies.get(cid):
            vacancies[cid].pop()
        bot.send_message(cid, "❌ Создание вакансии отменено.", reply_markup=employer_menu_markup())
    else:
        bot.send_message(cid, "Нечего отменять.", reply_markup=main_menu_markup())

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

# ── Отчёт и помощь ───────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '📊 Отчёт')
def report(message):
    bot.send_message(message.chat.id,
        "📊 Ваш отчёт:\n\n"
        "💰 Доходы: 0\n"
        "💸 Расходы: 0\n"
        "📈 Баланс: 0")

@bot.message_handler(func=lambda m: m.text == '❓ Помощь')
def help_info(message):
    bot.send_message(message.chat.id,
        "❓ *Помощь по боту Вахта PRO*\n\n"
        "🔍 *Ищу работу* — меню работника\n"
        "👤 *Мои данные* — заполнить или просмотреть анкету\n"
        "⛺ *Моя вахта* — информация о текущей вахте\n"
        "💰 *Зарплата* — раздел учёта зарплаты\n"
        "💸 *Расходы* — раздел учёта расходов\n"
        "🔍 *Найти работу* — поиск вакансий\n"
        "📊 *Отчёт* — финансовый отчёт\n"
        "🗑 *Удалить анкету* — удалить сохранённый профиль\n"
        "🏠 *Главное меню* — вернуться в начало\n\n"
        "Команды:\n"
        "/start — запустить бота\n"
        "/shift — раздел вахты\n"
        "/salary — раздел зарплаты\n"
        "/expenses — раздел расходов\n"
        "/cancel — отменить заполнение анкеты",
        parse_mode="Markdown")

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

# ── Админ панель ─────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '👨‍💼 Админ панель')
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 Нет доступа.")
        return
    total_users = len(set(list(user_profiles.keys()) + list(user_states.keys())))
    filled_profiles = sum(1 for p in user_profiles.values() if len(p) == len(STEPS))
    bot.send_message(message.chat.id,
        f"👨‍💼 *Админ панель*\n\n"
        f"👥 Пользователей в памяти: {total_users}\n"
        f"📋 Заполненных анкет: {filled_profiles}",
        parse_mode="Markdown")

# ── Прочие разделы ────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '🏢 Работодатель')
def employer(message):
    bot.send_message(message.chat.id, "🏢 Меню работодателя:", reply_markup=employer_menu_markup())

@bot.message_handler(func=lambda m: m.text == '➕ Добавить вакансию')
def add_vacancy(message):
    cid = message.chat.id
    vacancy_states[cid] = 0
    vacancies.setdefault(cid, [])
    vacancies[cid].append({})
    bot.send_message(cid,
        "📝 Создание вакансии. Можно отменить командой /cancel\n\n" + VAC_QUESTIONS['profession'],
        reply_markup=ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.chat.id in vacancy_states)
def handle_vacancy(message):
    cid = message.chat.id
    step_index = vacancy_states[cid]
    step_key = VAC_STEPS[step_index]

    vacancies[cid][-1][step_key] = message.text

    next_index = step_index + 1
    if next_index < len(VAC_STEPS):
        vacancy_states[cid] = next_index
        bot.send_message(cid, VAC_QUESTIONS[VAC_STEPS[next_index]])
    else:
        vacancy_states.pop(cid)
        vac = vacancies[cid][-1]
        lines = ["✅ *Вакансия создана!*\n"]
        for key in VAC_STEPS:
            lines.append(f"• {VAC_LABELS[key]}: {vac.get(key, '—')}")
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown",
                         reply_markup=employer_menu_markup())

@bot.message_handler(func=lambda m: m.text == '📋 Мои вакансии')
def my_vacancies(message):
    bot.send_message(message.chat.id, "📋 У вас пока нет размещённых вакансий.")

@bot.message_handler(func=lambda m: m.text == '👥 Найти работников')
def find_workers(message):
    bot.send_message(message.chat.id, "👥 Раздел поиска работников — скоро будет доступен.")

@bot.message_handler(func=lambda m: m.text == 'ℹ️ О проекте')
def about(message):
    bot.send_message(message.chat.id,
        "ℹ️ О проекте\n\n"
        "Vahta-bot — платформа для поиска работы и сотрудников.\n"
        "Мы помогаем соискателям и работодателям найти друг друга быстро и удобно.")

print("Бот запущен")

bot.infinity_polling()
