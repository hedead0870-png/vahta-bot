import telebot
from telebot import apihelper
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_ID
import database as db

apihelper.ENABLE_MIDDLEWARE = True
bot = telebot.TeleBot(TOKEN)
db.init_db()

# Состояния (хранятся только в памяти — сбрасываются при рестарте)
user_states = {}     # chat_id -> шаг анкеты работника
user_temp = {}       # chat_id -> dict с данными анкеты в процессе заполнения
vacancy_states = {}  # chat_id -> шаг создания вакансии
vacancy_temp = {}    # chat_id -> dict с данными новой вакансии

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

# ── Клавиатуры ────────────────────────────────────────────────

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
    markup.add(KeyboardButton('👥 Найти работников'), KeyboardButton('📩 Отклики'))
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

# ── Логирование ───────────────────────────────────────────────

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
    cid = message.chat.id
    profile = db.get_profile(cid)
    if not profile or not profile.get('city'):
        bot.send_message(cid, "⚠️ Сначала заполните раздел 👤 Мои данные.")
        return
    worker_city = profile['city'].strip()
    found = db.get_vacancies_by_city(worker_city)
    if not found:
        bot.send_message(cid, f"🔍 Подходящих вакансий в городе «{worker_city}» пока нет.")
        return
    bot.send_message(cid, f"🔍 Найдено вакансий в городе «{worker_city}»: {len(found)}")
    for i, vac in enumerate(found, start=1):
        lines = [f"📌 *Вакансия #{i}*\n"]
        for key in VAC_STEPS:
            lines.append(f"• {VAC_LABELS[key]}: {vac.get(key, '—')}")
        inline = InlineKeyboardMarkup()
        inline.add(InlineKeyboardButton(
            "📩 Откликнуться",
            callback_data=f"apply:{vac['employer_id']}:{vac['id']}"
        ))
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown", reply_markup=inline)

# ── Анкета работника ──────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '👤 Мои данные')
def my_data(message):
    cid = message.chat.id
    profile = db.get_profile(cid)
    if profile:
        lines = ["👤 *Ваш профиль:*"]
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
    user_temp[cid] = {}
    bot.send_message(cid,
        "📝 Заполним вашу анкету! Можно отменить командой /cancel\n\n" + STEP_QUESTIONS['name'],
        reply_markup=ReplyKeyboardRemove())

@bot.message_handler(commands=['cancel'])
def cancel(message):
    cid = message.chat.id
    if cid in user_states:
        user_states.pop(cid)
        bot.send_message(cid, "❌ Заполнение анкеты отменено.", reply_markup=worker_menu_markup())
    elif cid in vacancy_states:
        vacancy_states.pop(cid)
        vacancy_temp.pop(cid, None)
        bot.send_message(cid, "❌ Создание вакансии отменено.", reply_markup=employer_menu_markup())
    else:
        bot.send_message(cid, "Нечего отменять.", reply_markup=main_menu_markup())

@bot.message_handler(func=lambda m: m.chat.id in user_states)
def handle_questionnaire(message):
    cid = message.chat.id
    step_index = user_states[cid]
    step_key = STEPS[step_index]

    user_temp.setdefault(cid, {})[step_key] = message.text

    next_index = step_index + 1
    if next_index < len(STEPS):
        user_states[cid] = next_index
        bot.send_message(cid, STEP_QUESTIONS[STEPS[next_index]])
    else:
        user_states.pop(cid)
        data = user_temp.pop(cid, {})
        db.save_profile(cid, data)
        lines = ["✅ *Анкета сохранена!*\n"]
        for step in STEPS:
            lines.append(f"• {STEP_LABELS[step]}: {data.get(step, '—')}")
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
    if not db.get_profile(cid):
        bot.send_message(cid, "У вас нет сохранённой анкеты.")
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('✅ Да, удалить'), KeyboardButton('❌ Нет, оставить'))
    bot.send_message(cid, "⚠️ Вы уверены, что хотите удалить анкету?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '✅ Да, удалить')
def delete_profile_yes(message):
    cid = message.chat.id
    db.delete_profile(cid)
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
    bot.send_message(message.chat.id,
        f"👨‍💼 *Админ панель*\n\n"
        f"👥 Пользователей в БД: {db.count_users()}\n"
        f"📋 Заполненных анкет: {db.count_filled_profiles()}\n"
        f"📌 Вакансий: {db.count_vacancies()}",
        parse_mode="Markdown")

# ── Меню работодателя ─────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '🏢 Работодатель')
def employer(message):
    bot.send_message(message.chat.id, "🏢 Меню работодателя:", reply_markup=employer_menu_markup())

@bot.message_handler(func=lambda m: m.text == '➕ Добавить вакансию')
def add_vacancy(message):
    cid = message.chat.id
    vacancy_states[cid] = 0
    vacancy_temp[cid] = {}
    bot.send_message(cid,
        "📝 Создание вакансии. Можно отменить командой /cancel\n\n" + VAC_QUESTIONS['profession'],
        reply_markup=ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.chat.id in vacancy_states)
def handle_vacancy(message):
    cid = message.chat.id
    step_index = vacancy_states[cid]
    step_key = VAC_STEPS[step_index]
    vacancy_temp[cid][step_key] = message.text

    next_index = step_index + 1
    if next_index < len(VAC_STEPS):
        vacancy_states[cid] = next_index
        bot.send_message(cid, VAC_QUESTIONS[VAC_STEPS[next_index]])
    else:
        vacancy_states.pop(cid)
        data = vacancy_temp.pop(cid)
        db.add_vacancy(cid, data)
        lines = ["✅ *Вакансия создана!*\n"]
        for key in VAC_STEPS:
            lines.append(f"• {VAC_LABELS[key]}: {data.get(key, '—')}")
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown", reply_markup=employer_menu_markup())

@bot.message_handler(func=lambda m: m.text == '📋 Мои вакансии')
def my_vacancies(message):
    cid = message.chat.id
    vac_list = db.get_vacancies(cid)
    if not vac_list:
        bot.send_message(cid, "📋 У вас пока нет размещённых вакансий.")
        return
    for i, vac in enumerate(vac_list, start=1):
        lines = [f"📋 *Вакансия #{i}*\n"]
        for key in VAC_STEPS:
            lines.append(f"• {VAC_LABELS[key]}: {vac.get(key, '—')}")
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
    bot.send_message(cid, f"Всего вакансий: {len(vac_list)}", reply_markup=employer_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith('apply:'))
def handle_apply(call):
    worker_id = call.message.chat.id
    _, employer_id_str, vac_id_str = call.data.split(':')
    employer_id = int(employer_id_str)
    vac_id = int(vac_id_str)

    added = db.add_response(worker_id, employer_id, vac_id)
    if added:
        bot.answer_callback_query(call.id, "✅ Отклик отправлен!")
        bot.send_message(worker_id, "📩 Ваш отклик отправлен работодателю.")
    else:
        bot.answer_callback_query(call.id, "Вы уже откликались на эту вакансию.")

@bot.message_handler(func=lambda m: m.text == '📩 Отклики')
def employer_responses(message):
    cid = message.chat.id
    vac_list = db.get_vacancies(cid)
    if not vac_list:
        bot.send_message(cid, "У вас нет вакансий.")
        return
    resp_rows = db.get_responses_for_employer(cid)
    # Группируем отклики по vac_id
    resp_map = {}
    for r in resp_rows:
        resp_map.setdefault(r['vac_id'], []).append(r['worker_id'])

    has_any = False
    for vac in vac_list:
        worker_ids = resp_map.get(vac['id'], [])
        if not worker_ids:
            continue
        has_any = True
        lines = [f"📋 *{vac.get('profession', '—')}* ({vac.get('city', '—')}) — откликнулись: {len(worker_ids)}\n"]
        for w_id in worker_ids:
            profile = db.get_profile(w_id) or {}
            lines.append(
                f"👤 {profile.get('name', '—')} | "
                f"{profile.get('profession', '—')} | "
                f"📞 {profile.get('phone', '—')}"
            )
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
    if not has_any:
        bot.send_message(cid, "📩 Откликов пока нет.")

@bot.message_handler(func=lambda m: m.text == '👥 Найти работников')
def find_workers(message):
    bot.send_message(message.chat.id, "👥 Раздел поиска работников — скоро будет доступен.")

# ── Прочие разделы ────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == 'ℹ️ О проекте')
def about(message):
    bot.send_message(message.chat.id,
        "ℹ️ О проекте\n\n"
        "Vahta-bot — платформа для поиска работы и сотрудников.\n"
        "Мы помогаем соискателям и работодателям найти друг друга быстро и удобно.")

print("Бот запущен")

bot.infinity_polling()
