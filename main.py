import telebot
from telebot import apihelper
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_ID
import database as db

apihelper.ENABLE_MIDDLEWARE = True
bot = telebot.TeleBot(TOKEN)
db.init_db()


class PersistentDict:
    """Словарь, прозрачно сохраняющий состояния в SQLite (таблица sessions).
    При перезапуске бота данные не теряются.
    """
    def __init__(self, key_prefix: str):
        self._prefix = key_prefix

    def __setitem__(self, chat_id, value):
        db.set_session(chat_id, self._prefix, value)

    def __getitem__(self, chat_id):
        val = db.get_session(chat_id, self._prefix)
        if val is None:
            raise KeyError(chat_id)
        return val

    def __contains__(self, chat_id):
        return db.has_session(chat_id, self._prefix)

    def get(self, chat_id, default=None):
        return db.get_session(chat_id, self._prefix, default)

    def pop(self, chat_id, *args):
        val = db.get_session(chat_id, self._prefix)
        if val is None:
            if args:
                return args[0]
            raise KeyError(chat_id)
        db.del_session(chat_id, self._prefix)
        return val

    def setdefault(self, chat_id, default=None):
        val = db.get_session(chat_id, self._prefix)
        if val is None:
            db.set_session(chat_id, self._prefix, default)
            return default
        return val


# Состояния диалогов — хранятся в SQLite (таблица sessions), не теряются при перезапуске
user_states = PersistentDict('user_states')      # chat_id -> шаг анкеты работника (int)
user_temp = PersistentDict('user_temp')          # chat_id -> dict с данными анкеты в процессе
vacancy_states = PersistentDict('vacancy_states')  # chat_id -> шаг создания вакансии (int)
vacancy_temp = PersistentDict('vacancy_temp')    # chat_id -> dict с данными новой вакансии
review_states = PersistentDict('review_states')  # chat_id -> {'employer_id', 'vac_id', 'rating'}
search_states = PersistentDict('search_states')  # chat_id -> {'step': ..., 'profession': ...}
search_results = PersistentDict('search_results')  # chat_id -> {'vacancies': [...], 'index': int}
sub_states = PersistentDict('sub_states')        # chat_id -> {'step': ..., 'profession': ...}

STATUS_EMOJI = {'active': '🟢', 'closed': '🔴'}
STATUS_LABEL = {'active': 'Активна', 'closed': 'Закрыта'}

ANY_CITY = '🌍 Любой город'

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

VAC_STEPS = ['profession', 'city', 'company', 'inn', 'salary', 'schedule', 'contact']
VAC_QUESTIONS = {
    'profession': "1️⃣ Название профессии:",
    'city':       "2️⃣ Город:",
    'company':    "3️⃣ Компания / объект:",
    'inn':        "4️⃣ ИНН организации (10 или 12 цифр):",
    'salary':     "5️⃣ Зарплата (руб/мес):",
    'schedule':   "6️⃣ График вахты (например: 30/30, 60/30):",
    'contact':    "7️⃣ Контакт для связи (телефон или @username):",
}
VAC_LABELS = {
    'profession': 'Профессия',
    'city':       'Город',
    'company':    'Компания/объект',
    'inn':        'ИНН',
    'salary':     'Зарплата',
    'schedule':   'График',
    'contact':    'Контакт',
}

# ── Клавиатуры ────────────────────────────────────────────────

def worker_menu_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('👤 Мои данные'), KeyboardButton('⛺ Моя вахта'))
    markup.add(KeyboardButton('💰 Зарплата'), KeyboardButton('💸 Расходы'))
    markup.add(KeyboardButton('🔍 Найти работу'), KeyboardButton('🔔 Подписка'))
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

def _vacancy_card(vac, index, total):
    """Формирует текст карточки вакансии."""
    avg, cnt = db.get_employer_rating(vac['employer_id'])
    rating_str = f"⭐ {avg} ({cnt} отз.)" if avg else "нет отзывов"
    lines = [
        f"🏢 *{vac.get('company', '—')}*\n",
        f"👷 Профессия: {vac.get('profession', '—')}",
        f"📍 Город: {vac.get('city', '—')}",
        f"💰 Зарплата: {vac.get('salary', '—')}",
        f"⛺ График: {vac.get('schedule', '—')}",
        f"📞 Контакт: {vac.get('contact', '—')}",
        f"⭐ Рейтинг работодателя: {rating_str}",
        f"\n_Вакансия {index} из {total}_",
    ]
    return "\n".join(lines)

def _vacancy_inline(vac, index, total):
    """Формирует inline-кнопки для карточки вакансии."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📩 Откликнуться",   callback_data=f"apply:{vac['employer_id']}:{vac['id']}"),
        InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f"review:{vac['employer_id']}:{vac['id']}"),
    )
    markup.add(InlineKeyboardButton("🏢 Работодатель", callback_data=f"employer_card:{vac['employer_id']}"))
    if index < total:
        markup.add(InlineKeyboardButton("➡ Следующая вакансия", callback_data="next_vac"))
    return markup

@bot.message_handler(func=lambda m: m.text == '🔍 Найти работу')
def find_job(message):
    cid = message.chat.id
    # Сбрасываем предыдущий поиск
    search_states.pop(cid, None)
    search_results.pop(cid, None)
    search_states[cid] = {'step': 'profession'}
    bot.send_message(cid,
        "🔍 *Поиск вакансий*\n\nВведите название профессии (например: сварщик, электрик):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.chat.id in search_states)
def handle_search_input(message):
    cid = message.chat.id
    state = search_states[cid]
    text = message.text.strip()

    if state['step'] == 'profession':
        search_states[cid] = {'step': 'city', 'profession': text}
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton(ANY_CITY))
        bot.send_message(cid,
            f"👷 Профессия: *{text}*\n\nТеперь введите город или нажмите «{ANY_CITY}»:",
            parse_mode="Markdown",
            reply_markup=markup)

    elif state['step'] == 'city':
        profession = state['profession']
        city = None if text == ANY_CITY else text
        search_states.pop(cid)

        found = db.search_vacancies(profession=profession, city=city)
        if not found:
            city_label = city if city else "любой город"
            bot.send_message(cid,
                f"😔 По запросу *{profession}* / {city_label} вакансий пока нет.",
                parse_mode="Markdown",
                reply_markup=worker_menu_markup())
            return

        search_results[cid] = {'vacancies': found, 'index': 0}
        vac = found[0]
        bot.send_message(cid,
            f"✅ Найдено вакансий: {len(found)}",
            reply_markup=worker_menu_markup())
        bot.send_message(cid,
            _vacancy_card(vac, 1, len(found)),
            parse_mode="Markdown",
            reply_markup=_vacancy_inline(vac, 1, len(found)))

# ── Подписки на вакансии ──────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '🔔 Подписка')
def subscription_menu(message):
    cid = message.chat.id
    subs = db.get_subscriptions(cid)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton('➕ Новая подписка'), KeyboardButton('📋 Мои подписки'))
    markup.add(KeyboardButton('🏠 Главное меню'))
    count = f"У вас {len(subs)} подпис." if subs else "У вас пока нет подписок."
    bot.send_message(cid,
        f"🔔 *Подписки на вакансии*\n{count}\n\n"
        "Вы будете получать уведомления, когда появятся подходящие вакансии.",
        parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '➕ Новая подписка')
def new_subscription(message):
    cid = message.chat.id
    sub_states[cid] = {'step': 'profession'}
    bot.send_message(cid,
        "🔔 *Новая подписка*\n\nВведите профессию, за вакансиями которой хотите следить:",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.chat.id in sub_states)
def handle_sub_input(message):
    cid = message.chat.id
    state = sub_states[cid]
    text = message.text.strip()

    if state['step'] == 'profession':
        sub_states[cid] = {'step': 'city', 'profession': text}
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton(ANY_CITY))
        bot.send_message(cid,
            f"👷 Профессия: *{text}*\n\nТеперь укажите город или нажмите «{ANY_CITY}»:",
            parse_mode="Markdown", reply_markup=markup)

    elif state['step'] == 'city':
        profession = state['profession']
        city = None if text == ANY_CITY else text
        sub_states.pop(cid)

        sub_id = db.add_subscription(cid, profession, city)
        city_label = city if city else "любой город"
        if sub_id:
            bot.send_message(cid,
                f"✅ *Подписка создана!*\n\n"
                f"👷 Профессия: {profession}\n"
                f"📍 Город: {city_label}\n\n"
                "Вы получите уведомление, как только появится подходящая вакансия.",
                parse_mode="Markdown", reply_markup=worker_menu_markup())
        else:
            bot.send_message(cid,
                f"ℹ️ Такая подписка уже существует ({profession} / {city_label}).",
                reply_markup=worker_menu_markup())

@bot.message_handler(func=lambda m: m.text == '📋 Мои подписки')
def my_subscriptions(message):
    cid = message.chat.id
    subs = db.get_subscriptions(cid)
    if not subs:
        bot.send_message(cid, "У вас пока нет подписок.",
                         reply_markup=worker_menu_markup())
        return
    bot.send_message(cid, f"📋 *Ваши подписки* ({len(subs)}):",
                     parse_mode="Markdown")
    for sub in subs:
        city_label = sub['city'] if sub['city'] else "Любой город"
        inline = InlineKeyboardMarkup()
        inline.add(InlineKeyboardButton(
            "🗑 Удалить", callback_data=f"del_sub:{sub['id']}"))
        bot.send_message(cid,
            f"👷 {sub['profession']}  📍 {city_label}",
            reply_markup=inline)
    inline_all = InlineKeyboardMarkup()
    inline_all.add(InlineKeyboardButton(
        "❌ Отключить все подписки", callback_data="del_all_subs"))
    bot.send_message(cid, "Управление всеми подписками:",
                     reply_markup=inline_all)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_sub:'))
def handle_del_sub(call):
    cid = call.message.chat.id
    sub_id = int(call.data.split(':')[1])
    db.delete_subscription(sub_id, cid)
    bot.answer_callback_query(call.id, "🗑 Подписка удалена.")
    bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=None)
    bot.edit_message_text(
        f"~~{call.message.text}~~ _(удалена)_",
        cid, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'del_all_subs')
def handle_del_all_subs(call):
    cid = call.message.chat.id
    db.delete_all_subscriptions(cid)
    bot.answer_callback_query(call.id, "❌ Все подписки удалены.")
    bot.edit_message_text("❌ Все подписки отключены.", cid, call.message.message_id)

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
        user_temp.pop(cid, None)
        bot.send_message(cid, "❌ Заполнение анкеты отменено.", reply_markup=worker_menu_markup())
    elif cid in vacancy_states:
        vacancy_states.pop(cid)
        vacancy_temp.pop(cid, None)
        bot.send_message(cid, "❌ Создание вакансии отменено.", reply_markup=employer_menu_markup())
    elif cid in review_states:
        review_states.pop(cid)
        bot.send_message(cid, "❌ Отзыв отменён.", reply_markup=worker_menu_markup())
    elif cid in search_states:
        search_states.pop(cid)
        search_results.pop(cid, None)
        bot.send_message(cid, "❌ Поиск отменён.", reply_markup=worker_menu_markup())
    elif cid in sub_states:
        sub_states.pop(cid)
        bot.send_message(cid, "❌ Создание подписки отменено.", reply_markup=worker_menu_markup())
    else:
        bot.send_message(cid, "Нечего отменять.", reply_markup=main_menu_markup())

@bot.message_handler(func=lambda m: m.chat.id in user_states)
def handle_questionnaire(message):
    cid = message.chat.id
    step_index = user_states[cid]
    step_key = STEPS[step_index]

    tmp = user_temp.get(cid, {})
    tmp[step_key] = message.text
    user_temp[cid] = tmp

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
    tmp = vacancy_temp[cid]
    tmp[step_key] = message.text
    vacancy_temp[cid] = tmp

    next_index = step_index + 1
    if next_index < len(VAC_STEPS):
        vacancy_states[cid] = next_index
        bot.send_message(cid, VAC_QUESTIONS[VAC_STEPS[next_index]])
    else:
        vacancy_states.pop(cid)
        data = vacancy_temp.pop(cid)
        vac_id = db.add_vacancy(cid, data)
        lines = ["✅ *Вакансия создана!*\n"]
        for key in VAC_STEPS:
            lines.append(f"• {VAC_LABELS[key]}: {data.get(key, '—')}")
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown", reply_markup=employer_menu_markup())

        # Уведомляем подписчиков
        subscribers = db.find_matching_subscribers(
            profession=data.get('profession', ''),
            city=data.get('city', '')
        )
        if subscribers:
            notify_text = (
                "🔔 *Найдена новая вакансия!*\n\n"
                f"🏢 Компания: {data.get('company', '—')}\n"
                f"👷 Профессия: {data.get('profession', '—')}\n"
                f"📍 Город: {data.get('city', '—')}\n"
                f"💰 Зарплата: {data.get('salary', '—')}\n"
                f"⛺ График: {data.get('schedule', '—')}"
            )
            notify_inline = InlineKeyboardMarkup(row_width=2)
            notify_inline.add(
                InlineKeyboardButton("📩 Откликнуться",   callback_data=f"apply:{cid}:{vac_id}"),
                InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f"review:{cid}:{vac_id}"),
            )
            for sub_uid in subscribers:
                if sub_uid == cid:   # работодатель сам себе не шлёт
                    continue
                try:
                    bot.send_message(sub_uid, notify_text,
                                     parse_mode="Markdown", reply_markup=notify_inline)
                except Exception:
                    pass

@bot.message_handler(func=lambda m: m.text == '📋 Мои вакансии')
def my_vacancies(message):
    cid = message.chat.id
    vac_list = db.get_vacancies(cid)
    if not vac_list:
        bot.send_message(cid, "📋 У вас пока нет размещённых вакансий.")
        return
    for i, vac in enumerate(vac_list, start=1):
        status = vac.get('status', 'active')
        emoji = STATUS_EMOJI[status]
        label = STATUS_LABEL[status]
        lines = [f"📋 *Вакансия #{i}* {emoji} {label}\n"]
        for key in VAC_STEPS:
            lines.append(f"• {VAC_LABELS[key]}: {vac.get(key, '—')}")
        toggle_label = "🔴 Закрыть" if status == 'active' else "🟢 Открыть"
        inline = InlineKeyboardMarkup()
        inline.add(InlineKeyboardButton(toggle_label, callback_data=f"toggle_vac:{vac['id']}"))
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown", reply_markup=inline)
    bot.send_message(cid, f"Всего вакансий: {len(vac_list)}", reply_markup=employer_menu_markup())

def _employer_card_text(card):
    """Формирует текст карточки работодателя."""
    avg = card["avg_rating"]
    rating_str = f"⭐ {avg}" if avg else "нет отзывов"
    lines = [
        "🏢 *Карточка работодателя*\n",
        f"🏢 Компания: *{card['company']}*",
        f"🆔 ИНН: {card['inn'] or '—'}",
        f"⭐ Средний рейтинг: {rating_str}",
        f"💬 Отзывов: {card['review_count']}",
        f"📋 Вакансий: {card['vacancy_count']}",
        f"👥 Сотрудников оставили отзыв: {card['unique_workers']}",
    ]
    if avg is not None:
        if avg < 3.5:
            lines.append(
                "\n⚠️ *У работодателя низкий рейтинг.*\n"
                "Перед трудоустройством рекомендуем ознакомиться с отзывами."
            )
        elif avg >= 4.5:
            lines.append("\n🟢 *Проверенный работодатель*")
    return "\n".join(lines)

@bot.callback_query_handler(func=lambda call: call.data.startswith('employer_card:'))
def handle_employer_card(call):
    cid = call.message.chat.id
    employer_id = int(call.data.split(':')[1])
    bot.answer_callback_query(call.id)
    card = db.get_employer_card(employer_id)
    text = _employer_card_text(card)
    inline = InlineKeyboardMarkup()
    if card['review_count'] > 0:
        inline.add(InlineKeyboardButton(
            "📖 Все отзывы", callback_data=f"emp_reviews:{employer_id}:0"))
    bot.send_message(cid, text, parse_mode="Markdown", reply_markup=inline)

REVIEWS_PER_PAGE = 5

@bot.callback_query_handler(func=lambda call: call.data.startswith('emp_reviews:'))
def handle_emp_reviews(call):
    cid = call.message.chat.id
    _, employer_id_str, page_str = call.data.split(':')
    employer_id = int(employer_id_str)
    page = int(page_str)
    bot.answer_callback_query(call.id)

    reviews, total = db.get_employer_reviews_paged(employer_id, page, REVIEWS_PER_PAGE)
    if not reviews:
        bot.send_message(cid, "Отзывов пока нет.")
        return

    total_pages = (total + REVIEWS_PER_PAGE - 1) // REVIEWS_PER_PAGE
    lines = [f"📖 *Отзывы о работодателе* (стр. {page + 1}/{total_pages})\n"]
    for r in reviews:
        stars = '⭐' * r['rating']
        worker_name = r.get('worker_name') or 'Аноним'
        review_text = r.get('text') or '_без текста_'
        date = (r.get('created_at') or '')[:10]
        lines.append(f"{stars} — *{worker_name}* ({date})\n{review_text}\n")

    inline = InlineKeyboardMarkup(row_width=2)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            "← Назад", callback_data=f"emp_reviews:{employer_id}:{page - 1}"))
    if (page + 1) < total_pages:
        nav.append(InlineKeyboardButton(
            "Вперёд →", callback_data=f"emp_reviews:{employer_id}:{page + 1}"))
    if nav:
        inline.add(*nav)

    bot.send_message(cid, "\n".join(lines), parse_mode="Markdown", reply_markup=inline)

@bot.callback_query_handler(func=lambda call: call.data == 'next_vac')
def handle_next_vac(call):
    cid = call.message.chat.id
    state = search_results.get(cid)
    if not state:
        bot.answer_callback_query(call.id, "Сессия поиска устарела. Запустите поиск заново.")
        return
    state['index'] += 1
    search_results[cid] = state
    idx = state['index']
    vacancies_list = state['vacancies']
    if idx >= len(vacancies_list):
        bot.answer_callback_query(call.id, "Это последняя вакансия.")
        return
    bot.answer_callback_query(call.id)
    vac = vacancies_list[idx]
    total = len(vacancies_list)
    bot.send_message(cid,
        _vacancy_card(vac, idx + 1, total),
        parse_mode="Markdown",
        reply_markup=_vacancy_inline(vac, idx + 1, total))

@bot.callback_query_handler(func=lambda call: call.data.startswith('apply:'))
def handle_apply(call):
    worker_id = call.message.chat.id
    _, employer_id_str, vac_id_str = call.data.split(':')
    employer_id = int(employer_id_str)
    vac_id = int(vac_id_str)

    # Проверяем анкету работника
    profile = db.get_profile(worker_id)
    if not profile or not profile.get('name'):
        bot.answer_callback_query(call.id, "⚠️ Сначала заполните анкету!")
        bot.send_message(worker_id,
            "⚠️ Чтобы откликнуться на вакансию, сначала заполните анкету.\n"
            "Перейдите в раздел 🔍 Ищу работу → 👤 Мои данные.")
        return

    # Проверяем повторный отклик
    added = db.add_response(worker_id, employer_id, vac_id)
    if not added:
        bot.answer_callback_query(call.id, "Вы уже откликались на эту вакансию.")
        bot.send_message(worker_id, "ℹ️ Вы уже откликались на эту вакансию.")
        return

    bot.answer_callback_query(call.id, "✅ Отклик отправлен!")

    # Сообщение работнику
    bot.send_message(worker_id,
        "✅ Ваш отклик успешно отправлен работодателю.\n"
        "Ожидайте — работодатель свяжется с вами.")

    # Получаем данные вакансии
    vac = db.get_vacancy_by_id(vac_id) or {}

    # Уведомление работодателю
    lines = [
        "📩 *Новый отклик!*\n",
        f"📌 Вакансия: *{vac.get('profession', '—')}* ({vac.get('company', '—')})\n",
        "👤 *Кандидат:*",
        f"• Имя: {profile.get('name', '—')}",
        f"• 📞 Телефон: {profile.get('phone', '—')}",
        f"• 📍 Город: {profile.get('city', '—')}",
        f"• 🔧 Профессия: {profile.get('profession', '—')}",
        f"• 📋 Опыт: {profile.get('experience', '—')} лет",
        f"• 💰 Желаемая зарплата: {profile.get('salary', '—')}",
        f"• ⛺ Желаемая вахта: {profile.get('shift', '—')}",
    ]
    inline = InlineKeyboardMarkup(row_width=2)
    inline.add(
        InlineKeyboardButton("👤 Открыть профиль", callback_data=f"view_profile:{worker_id}"),
        InlineKeyboardButton("📞 Связаться",        callback_data=f"contact:{worker_id}"),
    )
    try:
        bot.send_message(employer_id, "\n".join(lines), parse_mode="Markdown", reply_markup=inline)
    except Exception:
        pass  # работодатель мог не запустить бота

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_profile:'))
def handle_view_profile(call):
    employer_id = call.message.chat.id
    worker_id = int(call.data.split(':')[1])
    profile = db.get_profile(worker_id)
    bot.answer_callback_query(call.id)
    if not profile:
        bot.send_message(employer_id, "⚠️ Анкета кандидата не найдена.")
        return
    lines = [
        "👤 *Профиль кандидата*\n",
        f"• Имя: {profile.get('name', '—')}",
        f"• 📞 Телефон: {profile.get('phone', '—')}",
        f"• 📍 Город: {profile.get('city', '—')}",
        f"• 🔧 Профессия: {profile.get('profession', '—')}",
        f"• 📋 Опыт: {profile.get('experience', '—')} лет",
        f"• 💰 Желаемая зарплата: {profile.get('salary', '—')}",
        f"• ⛺ Желаемая вахта: {profile.get('shift', '—')}",
    ]
    bot.send_message(employer_id, "\n".join(lines), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('contact:'))
def handle_contact(call):
    employer_id = call.message.chat.id
    worker_id = int(call.data.split(':')[1])
    profile = db.get_profile(worker_id)
    bot.answer_callback_query(call.id)
    if not profile:
        bot.send_message(employer_id, "⚠️ Кандидат не найден.")
        return
    name  = profile.get('name', '—')
    phone = profile.get('phone', '—')
    bot.send_message(employer_id,
        f"📞 *Контакт кандидата*\n\n"
        f"👤 {name}\n"
        f"📞 {phone}",
        parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == '📩 Отклики')
def employer_responses(message):
    cid = message.chat.id
    vac_list = db.get_vacancies(cid)
    if not vac_list:
        bot.send_message(cid, "У вас нет вакансий.")
        return

    resp_rows = db.get_responses_for_employer(cid)
    # Группируем отклики по vac_id
    resp_map: dict[int, list[int]] = {}
    for r in resp_rows:
        resp_map.setdefault(r['vac_id'], []).append(r['worker_id'])

    has_any = False
    for vac in vac_list:
        worker_ids = resp_map.get(vac['id'], [])
        if not worker_ids:
            continue
        has_any = True
        status_emoji = STATUS_EMOJI.get(vac.get('status', 'active'), '🟢')
        header = (
            f"📋 *{vac.get('profession', '—')}* — {vac.get('company', '—')} "
            f"({vac.get('city', '—')}) {status_emoji}\n"
            f"👥 Откликнулись: {len(worker_ids)}\n"
        )
        bot.send_message(cid, header, parse_mode="Markdown")

        for w_id in worker_ids:
            profile = db.get_profile(w_id) or {}
            card = (
                f"👤 *{profile.get('name', '—')}*\n"
                f"• 📞 {profile.get('phone', '—')}\n"
                f"• 📍 {profile.get('city', '—')}\n"
                f"• 🔧 {profile.get('profession', '—')}\n"
                f"• 📋 Опыт: {profile.get('experience', '—')} лет\n"
                f"• 💰 {profile.get('salary', '—')}\n"
                f"• ⛺ {profile.get('shift', '—')}"
            )
            inline = InlineKeyboardMarkup(row_width=2)
            inline.add(
                InlineKeyboardButton("👤 Открыть профиль", callback_data=f"view_profile:{w_id}"),
                InlineKeyboardButton("📞 Связаться",        callback_data=f"contact:{w_id}"),
            )
            bot.send_message(cid, card, parse_mode="Markdown", reply_markup=inline)

    if not has_any:
        bot.send_message(cid, "📩 Откликов пока нет.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('review:'))
def handle_review_start(call):
    worker_id = call.message.chat.id
    _, employer_id_str, vac_id_str = call.data.split(':')
    employer_id = int(employer_id_str)
    vac_id = int(vac_id_str)
    if db.has_reviewed(worker_id, vac_id):
        bot.answer_callback_query(call.id, "Вы уже оставляли отзыв на эту вакансию.")
        return
    bot.answer_callback_query(call.id)
    inline = InlineKeyboardMarkup(row_width=5)
    inline.add(*[
        InlineKeyboardButton(f"{'⭐' * n}", callback_data=f"rate:{employer_id}:{vac_id}:{n}")
        for n in range(1, 6)
    ])
    bot.send_message(worker_id, "⭐ Оцените работодателя от 1 до 5 звёзд:", reply_markup=inline)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rate:'))
def handle_review_rating(call):
    worker_id = call.message.chat.id
    _, employer_id_str, vac_id_str, rating_str = call.data.split(':')
    review_states[worker_id] = {
        'employer_id': int(employer_id_str),
        'vac_id': int(vac_id_str),
        'rating': int(rating_str),
    }
    bot.answer_callback_query(call.id, f"Выбрано: {'⭐' * int(rating_str)}")
    bot.send_message(worker_id, "✏️ Напишите текстовый отзыв (или отправьте /skip, чтобы пропустить):")

@bot.message_handler(commands=['skip'])
def review_skip(message):
    cid = message.chat.id
    if cid not in review_states:
        return
    state = review_states.pop(cid)
    saved = db.add_review(cid, state['employer_id'], state['vac_id'], state['rating'], text=None)
    if saved:
        bot.send_message(cid, f"✅ Отзыв сохранён! Оценка: {'⭐' * state['rating']}")
    else:
        bot.send_message(cid, "Вы уже оставляли отзыв на эту вакансию.")

@bot.message_handler(func=lambda m: m.chat.id in review_states)
def handle_review_text(message):
    cid = message.chat.id
    state = review_states.pop(cid)
    saved = db.add_review(cid, state['employer_id'], state['vac_id'], state['rating'], text=message.text)
    if saved:
        bot.send_message(cid,
            f"✅ Отзыв сохранён!\n"
            f"Оценка: {'⭐' * state['rating']}\n"
            f"Текст: {message.text}")
    else:
        bot.send_message(cid, "Вы уже оставляли отзыв на эту вакансию.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_vac:'))
def handle_toggle_vac(call):
    employer_id = call.message.chat.id
    vac_id = int(call.data.split(':')[1])
    vac = db.get_vacancy_by_id(vac_id)
    if not vac or vac['employer_id'] != employer_id:
        bot.answer_callback_query(call.id, "Вакансия не найдена.")
        return
    new_status = 'closed' if vac.get('status', 'active') == 'active' else 'active'
    db.set_vacancy_status(vac_id, new_status)
    emoji = STATUS_EMOJI[new_status]
    label = STATUS_LABEL[new_status]
    bot.answer_callback_query(call.id, f"Статус изменён: {emoji} {label}")
    # Обновляем кнопку на месте
    toggle_label = "🔴 Закрыть" if new_status == 'active' else "🟢 Открыть"
    new_inline = InlineKeyboardMarkup()
    new_inline.add(InlineKeyboardButton(toggle_label, callback_data=f"toggle_vac:{vac_id}"))
    bot.edit_message_reply_markup(employer_id, call.message.message_id, reply_markup=new_inline)
    bot.send_message(employer_id, f"Вакансия #{vac_id} теперь: {emoji} {label}")

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
