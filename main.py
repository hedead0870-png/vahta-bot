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
complaint_states = PersistentDict('complaint_states')  # chat_id -> {'employer_id', 'reason'}
chat_states = PersistentDict('chat_states')          # chat_id -> {'app_id', 'receiver_id', 'my_role'}

STATUS_EMOJI = {'active': '🟢', 'closed': '🔴'}
STATUS_LABEL = {'active': 'Активна', 'closed': 'Закрыта'}

# Статусы работодателей
EMP_STATUS_LINE = {
    'new':        '🟡 Новый работодатель',
    'verified':   '🟢 Проверенный работодатель',
    'complaints': '🔴 Есть жалобы',
}
EMP_STATUS_LABEL = {
    'new':        '🟡 Новый',
    'verified':   '🟢 Проверенный',
    'complaints': '🔴 Есть жалобы',
}
EMP_STATUS_WARNING = {
    'complaints': '⚠️ Перед трудоустройством изучите отзывы.',
}

COMPLAINT_REASONS = {
    'salary':     '💰 Задержка зарплаты',
    'mismatch':   '❌ Вакансия не соответствует описанию',
    'conditions': '🏚 Плохие условия труда',
    'other':      '📉 Другая проблема',
}

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
    markup.add(KeyboardButton('📬 Мои отклики'), KeyboardButton('🗑 Удалить анкету'))
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
    emp_st = db.get_employer_status(vac['employer_id'])
    status_line = EMP_STATUS_LINE.get(emp_st['status'], '🟡 Новый работодатель')
    lines = [
        f"🏢 *{vac.get('company', '—')}*",
        f"{status_line}",
        f"⭐ Рейтинг: {avg}  💬 Отзывов: {cnt}" if avg else "💬 Отзывов пока нет",
        "",
        f"👷 Профессия: {vac.get('profession', '—')}",
        f"📍 Город: {vac.get('city', '—')}",
        f"💰 Зарплата: {vac.get('salary', '—')}",
        f"⛺ График: {vac.get('schedule', '—')}",
        f"📞 Контакт: {vac.get('contact', '—')}",
    ]
    if emp_st['status'] == 'complaints':
        lines.append("\n⚠️ Перед трудоустройством изучите отзывы.")
    lines.append(f"\n_Вакансия {index} из {total}_")
    return "\n".join(lines)

def _vacancy_inline(vac, index, total):
    """Формирует inline-кнопки для карточки вакансии."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📩 Откликнуться",   callback_data=f"apply:{vac['employer_id']}:{vac['id']}"),
        InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f"review:{vac['employer_id']}:{vac['id']}"),
    )
    markup.add(InlineKeyboardButton("🏢 О работодателе", callback_data=f"employer_card:{vac['employer_id']}"))
    if index < total:
        markup.add(InlineKeyboardButton("➡ Следующая вакансия", callback_data="next_vac"))
    return markup

def _official_vacancy_card(vac, index, total):
    """Формирует текст карточки официальной вакансии."""
    lines = [
        "🟢 *Вакансия с официального сайта*",
        "",
        f"🏢 Компания: {vac.get('company_name', '—')}",
        f"👷 Профессия: {vac.get('profession', '—')}",
        f"📍 Город: {vac.get('city', '—')}",
        f"💰 Зарплата: {vac.get('salary') or '—'}",
        f"⛺ График: {vac.get('schedule') or '—'}",
        "",
        f"_Вакансия {index} из {total}_",
    ]
    return "\n".join(lines)


def _official_vacancy_inline(vac, index, total):
    """Формирует inline-кнопки для карточки официальной вакансии."""
    markup = InlineKeyboardMarkup(row_width=1)
    if vac.get('source_url'):
        markup.add(InlineKeyboardButton("🌐 Открыть оригинал", url=vac['source_url']))
    if index < total:
        markup.add(InlineKeyboardButton("➡ Следующая вакансия", callback_data="next_vac"))
    return markup


def _send_vac_card(cid, vac, index, total):
    """Отправляет карточку вакансии нужного типа."""
    if vac.get('_vac_type') == 'official':
        bot.send_message(cid,
            _official_vacancy_card(vac, index, total),
            parse_mode="Markdown",
            reply_markup=_official_vacancy_inline(vac, index, total))
    else:
        bot.send_message(cid,
            _vacancy_card(vac, index, total),
            parse_mode="Markdown",
            reply_markup=_vacancy_inline(vac, index, total))


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

        # Обычные вакансии работодателей
        regular = db.search_vacancies(profession=profession, city=city)
        for v in regular:
            v['_vac_type'] = 'regular'

        # Официальные вакансии
        official = db.get_official_vacancies(profession=profession, city=city, limit=50)
        for v in official:
            v['_vac_type'] = 'official'

        found = regular + official

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
        _send_vac_card(cid, vac, 1, len(found))

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
    elif cid in complaint_states:
        complaint_states.pop(cid)
        bot.send_message(cid, "❌ Жалоба отменена.", reply_markup=worker_menu_markup())
    elif cid in chat_states:
        chat_states.pop(cid)
        bot.send_message(cid, "❌ Отправка сообщения отменена.", reply_markup=main_menu_markup())
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
    pending = db.count_pending_complaints()
    complaints_label = f"📋 Жалобы ({pending} новых)" if pending else "📋 Жалобы"
    inline = InlineKeyboardMarkup(row_width=1)
    inline.add(InlineKeyboardButton("👷 Статусы работодателей", callback_data="admin_emp_list"))
    inline.add(InlineKeyboardButton(complaints_label, callback_data="admin_complaints"))
    bot.send_message(message.chat.id,
        f"👨‍💼 *Админ панель*\n\n"
        f"👥 Пользователей в БД: {db.count_users()}\n"
        f"📋 Заполненных анкет: {db.count_filled_profiles()}\n"
        f"📌 Вакансий: {db.count_vacancies()}\n"
        f"⚠️ Жалоб на рассмотрении: {pending}",
        parse_mode="Markdown",
        reply_markup=inline)

# ── Админ: управление статусами работодателей ─────────────────

def _is_admin(chat_id):
    return chat_id == ADMIN_ID

@bot.callback_query_handler(func=lambda call: call.data == 'admin_emp_list')
def admin_emp_list(call):
    if not _is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "🚫 Нет доступа.")
        return
    bot.answer_callback_query(call.id)
    employers = db.get_all_employers_for_admin()
    if not employers:
        bot.send_message(call.message.chat.id, "👷 Работодателей пока нет.")
        return
    bot.send_message(call.message.chat.id, f"👷 *Работодатели* ({len(employers)}):", parse_mode="Markdown")
    for emp in employers:
        status_label = EMP_STATUS_LABEL.get(emp['status'], '🟡 Новый')
        manual_mark = " _(вручную)_" if emp['is_manual'] else ""
        text = f"🏢 *{emp['company'] or '—'}*\nСтатус: {status_label}{manual_mark}"
        inline = InlineKeyboardMarkup()
        inline.add(InlineKeyboardButton(
            "✏️ Изменить статус", callback_data=f"admin_emp_info:{emp['employer_id']}"))
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=inline)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_emp_info:'))
def admin_emp_info(call):
    if not _is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "🚫 Нет доступа.")
        return
    bot.answer_callback_query(call.id)
    employer_id = int(call.data.split(':')[1])
    card = db.get_employer_card(employer_id)
    emp_st = db.get_employer_status(employer_id)
    current = EMP_STATUS_LABEL.get(emp_st['status'], '🟡 Новый')
    avg = card['avg_rating']
    text = (
        f"🏢 *{card['company']}*\n"
        f"⭐ Рейтинг: {avg if avg else '—'}  💬 Отзывов: {card['review_count']}\n"
        f"Текущий статус: {current}\n\n"
        f"Выберите новый статус:"
    )
    inline = InlineKeyboardMarkup(row_width=3)
    inline.add(
        InlineKeyboardButton("🟢 Проверенный", callback_data=f"admin_emp_set:{employer_id}:verified"),
        InlineKeyboardButton("🟡 Новый",        callback_data=f"admin_emp_set:{employer_id}:new"),
        InlineKeyboardButton("🔴 Есть жалобы",  callback_data=f"admin_emp_set:{employer_id}:complaints"),
    )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=inline)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_emp_set:'))
def admin_emp_set(call):
    if not _is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "🚫 Нет доступа.")
        return
    _, employer_id_str, status = call.data.split(':')
    employer_id = int(employer_id_str)
    if status not in db.EMPLOYER_STATUSES:
        bot.answer_callback_query(call.id, "Неверный статус.")
        return
    db.set_employer_status(employer_id, status, is_manual=True)
    label = EMP_STATUS_LABEL.get(status, status)
    bot.answer_callback_query(call.id, f"✅ Статус установлен: {label}")
    bot.edit_message_text(
        f"✅ Статус работодателя обновлён:\n{label}",
        call.message.chat.id, call.message.message_id
    )

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
    emp_st = db.get_employer_status(card['employer_id'])
    status_label = EMP_STATUS_LABEL.get(emp_st['status'], '🟡 Новый')
    manual_mark = " _(вручную)_" if emp_st['is_manual'] else ""
    cities_str = ", ".join(card.get('cities', [])) or "—"
    lines = [
        "🏢 *Карточка работодателя*\n",
        f"🏢 Компания: *{card['company']}*",
        f"🆔 ИНН: {card['inn'] or '—'}",
        f"📍 Города/объекты: {cities_str}",
        f"📊 Статус: {status_label}{manual_mark}",
        f"⭐ Средний рейтинг: {rating_str}",
        f"💬 Отзывов: {card['review_count']}",
        f"📋 Активных вакансий: {card.get('active_vac_count', 0)} / всего {card['vacancy_count']}",
        f"👥 Сотрудников оставили отзыв: {card['unique_workers']}",
    ]
    if card.get('complaint_count', 0) > 0:
        lines.append(f"⚠️ Жалоб на рассмотрении: {card['complaint_count']}")
    if emp_st['status'] == 'complaints':
        lines.append(
            "\n⚠️ *У работодателя есть жалобы.*\n"
            "Перед трудоустройством рекомендуем ознакомиться с отзывами."
        )
    elif emp_st['status'] == 'verified':
        lines.append("\n🟢 *Проверенный работодатель*")
    return "\n".join(lines)

@bot.callback_query_handler(func=lambda call: call.data.startswith('employer_card:'))
def handle_employer_card(call):
    cid = call.message.chat.id
    employer_id = int(call.data.split(':')[1])
    bot.answer_callback_query(call.id)
    card = db.get_employer_card(employer_id)
    text = _employer_card_text(card)
    inline = InlineKeyboardMarkup(row_width=1)
    if card['review_count'] > 0:
        inline.add(InlineKeyboardButton(
            "📖 Все отзывы", callback_data=f"emp_reviews:{employer_id}:0"))
    inline.add(InlineKeyboardButton(
        "⚠️ Пожаловаться на работодателя", callback_data=f"complaint:{employer_id}"))
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
    _send_vac_card(cid, vac, idx + 1, total)

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
            "Перейдите в раздел 🔍 Ищу работу → 👤 Мои данные.",
            reply_markup=worker_menu_markup())
        return

    # Создаём заявку в applications
    app_id = db.add_application(vac_id, worker_id, employer_id)
    if not app_id:
        bot.answer_callback_query(call.id, "Вы уже откликались на эту вакансию.")
        bot.send_message(worker_id, "ℹ️ Вы уже откликались на эту вакансию.")
        return

    bot.answer_callback_query(call.id, "✅ Отклик отправлен!")

    # Сообщение работнику
    bot.send_message(worker_id,
        "✅ *Отклик отправлен!*\n\n"
        "Работодатель рассмотрит вашу анкету и свяжется с вами.\n"
        "Статус можно проверить в разделе 📬 Мои отклики.",
        parse_mode="Markdown")

    # Получаем данные вакансии
    vac = db.get_vacancy_by_id(vac_id) or {}

    # Уведомление работодателю
    lines = [
        "📩 *Новый отклик на вакансию!*\n",
        f"🏢 Вакансия: *{vac.get('profession', '—')}* — {vac.get('company', '—')} ({vac.get('city', '—')})\n",
        "👤 *Кандидат:*",
        f"👤 Имя: {profile.get('name', '—')}",
        f"🔧 Профессия: {profile.get('profession', '—')}",
        f"🏙 Город: {profile.get('city', '—')}",
        f"📋 Опыт: {profile.get('experience', '—')} лет",
        f"💰 Желаемая зарплата: {profile.get('salary', '—')}",
        f"⛺ Вахта: {profile.get('shift', '—')}",
        f"📞 Телефон: {profile.get('phone', '—')}",
    ]
    inline = InlineKeyboardMarkup(row_width=2)
    inline.add(
        InlineKeyboardButton("✅ Принять",  callback_data=f"app_accept:{app_id}"),
        InlineKeyboardButton("❌ Отказать", callback_data=f"app_reject:{app_id}"),
    )
    inline.add(InlineKeyboardButton("👤 Открыть профиль", callback_data=f"view_profile:{worker_id}"))
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
    apps = db.get_applications_for_employer(cid)
    if not apps:
        bot.send_message(cid, "📩 Откликов пока нет.", reply_markup=employer_menu_markup())
        return

    # Группируем заявки по вакансии
    vac_groups: dict[int, list] = {}
    for a in apps:
        vac_groups.setdefault(a['vacancy_id'], []).append(a)

    bot.send_message(cid,
        f"📩 *Отклики на ваши вакансии* — всего {len(apps)}:",
        parse_mode="Markdown")

    for vac_id, group in vac_groups.items():
        first = group[0]
        vac_emoji = STATUS_EMOJI.get(first.get('vac_status', 'active'), '🟢')
        header = (
            f"📋 *{first.get('profession', '—')}* — {first.get('company', '—')} "
            f"({first.get('vac_city', '—')}) {vac_emoji}\n"
            f"👥 Откликнулись: {len(group)}"
        )
        bot.send_message(cid, header, parse_mode="Markdown")

        for a in group:
            st_label = db.APPLICATION_STATUS_LABEL.get(a['status'], a['status'])
            date = (a.get('created_at') or '')[:10]
            card = (
                f"👤 *{a.get('name') or '—'}*  {st_label}\n"
                f"• 🔧 {a.get('worker_profession') or '—'}\n"
                f"• 📍 {a.get('worker_city') or '—'}\n"
                f"• 📋 Опыт: {a.get('experience') or '—'} лет\n"
                f"• 💰 {a.get('worker_salary') or '—'}\n"
                f"• ⛺ {a.get('shift') or '—'}\n"
                f"• 📞 {a.get('phone') or '—'}\n"
                f"_Дата: {date}_"
            )
            # Кнопки зависят от статуса
            inline = InlineKeyboardMarkup(row_width=2)
            if a['status'] not in ('accepted', 'rejected'):
                inline.add(
                    InlineKeyboardButton("✅ Принять",  callback_data=f"app_accept:{a['id']}"),
                    InlineKeyboardButton("❌ Отказать", callback_data=f"app_reject:{a['id']}"),
                )
            inline.add(InlineKeyboardButton(
                "👤 Профиль", callback_data=f"view_profile:{a['worker_id']}"))
            bot.send_message(cid, card, parse_mode="Markdown", reply_markup=inline)
            # Помечаем просмотренным
            db.mark_application_viewed(a['id'])

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_accept:'))
def handle_app_accept(call):
    employer_id = call.message.chat.id
    app_id = int(call.data.split(':')[1])
    app = db.get_application_by_id(app_id)
    if not app or app['employer_id'] != employer_id:
        bot.answer_callback_query(call.id, "Заявка не найдена.")
        return
    if app['status'] in ('accepted', 'rejected'):
        bot.answer_callback_query(call.id, "Решение по этой заявке уже принято.")
        return
    worker_id = db.set_application_status(app_id, 'accepted')
    bot.answer_callback_query(call.id, "✅ Отклик принят!")
    # Обновляем кнопки
    new_inline = InlineKeyboardMarkup()
    new_inline.add(InlineKeyboardButton(
        "👤 Профиль", callback_data=f"view_profile:{app['worker_id']}"))
    try:
        bot.edit_message_reply_markup(
            employer_id, call.message.message_id, reply_markup=new_inline)
    except Exception:
        pass
    chat_inline_emp = InlineKeyboardMarkup()
    chat_inline_emp.add(InlineKeyboardButton(
        "💬 Написать работнику", callback_data=f"chat_open:{app_id}:employer"))
    bot.send_message(employer_id,
        "✅ Вы приняли отклик кандидата.\nТеперь вы можете написать ему напрямую.",
        reply_markup=chat_inline_emp)
    # Уведомляем работника
    if worker_id:
        vac = db.get_vacancy_by_id(app['vacancy_id']) or {}
        chat_inline_w = InlineKeyboardMarkup()
        chat_inline_w.add(InlineKeyboardButton(
            "💬 Написать работодателю", callback_data=f"chat_open:{app_id}:worker"))
        try:
            bot.send_message(worker_id,
                f"✅ *Работодатель принял ваш отклик!*\n\n"
                f"🏢 Компания: {vac.get('company', '—')}\n"
                f"👷 Вакансия: {vac.get('profession', '—')}\n"
                f"📍 Город: {vac.get('city', '—')}\n"
                f"📞 Контакт: {vac.get('contact', '—')}\n\n"
                "Теперь вы можете написать работодателю напрямую.",
                parse_mode="Markdown",
                reply_markup=chat_inline_w)
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_reject:'))
def handle_app_reject(call):
    employer_id = call.message.chat.id
    app_id = int(call.data.split(':')[1])
    app = db.get_application_by_id(app_id)
    if not app or app['employer_id'] != employer_id:
        bot.answer_callback_query(call.id, "Заявка не найдена.")
        return
    if app['status'] in ('accepted', 'rejected'):
        bot.answer_callback_query(call.id, "Решение по этой заявке уже принято.")
        return
    worker_id = db.set_application_status(app_id, 'rejected')
    bot.answer_callback_query(call.id, "❌ Отклик отклонён.")
    # Обновляем кнопки
    new_inline = InlineKeyboardMarkup()
    new_inline.add(InlineKeyboardButton(
        "👤 Профиль", callback_data=f"view_profile:{app['worker_id']}"))
    try:
        bot.edit_message_reply_markup(
            employer_id, call.message.message_id, reply_markup=new_inline)
    except Exception:
        pass
    bot.send_message(employer_id, "❌ Вы отказали кандидату.")
    # Уведомляем работника
    if worker_id:
        vac = db.get_vacancy_by_id(app['vacancy_id']) or {}
        try:
            bot.send_message(worker_id,
                f"❌ *Работодатель отказал по вашему отклику.*\n\n"
                f"🏢 Компания: {vac.get('company', '—')}\n"
                f"👷 Вакансия: {vac.get('profession', '—')}\n\n"
                "Не расстраивайтесь — продолжайте поиск!",
                parse_mode="Markdown")
        except Exception:
            pass

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
        db.refresh_employer_status(state['employer_id'])
        bot.send_message(cid, f"✅ Отзыв сохранён! Оценка: {'⭐' * state['rating']}")
    else:
        bot.send_message(cid, "Вы уже оставляли отзыв на эту вакансию.")

@bot.message_handler(func=lambda m: m.chat.id in review_states)
def handle_review_text(message):
    cid = message.chat.id
    state = review_states.pop(cid)
    saved = db.add_review(cid, state['employer_id'], state['vac_id'], state['rating'], text=message.text)
    if saved:
        db.refresh_employer_status(state['employer_id'])
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
    # Уведомляем подписчиков при повторном открытии вакансии
    if new_status == 'active':
        subscribers = db.find_matching_subscribers(
            profession=vac.get('profession', ''),
            city=vac.get('city', '')
        )
        if subscribers:
            notify_text = (
                "🔔 *Вакансия снова открыта!*\n\n"
                f"🏢 Компания: {vac.get('company', '—')}\n"
                f"👷 Профессия: {vac.get('profession', '—')}\n"
                f"📍 Город: {vac.get('city', '—')}\n"
                f"💰 Зарплата: {vac.get('salary', '—')}\n"
                f"⛺ График: {vac.get('schedule', '—')}"
            )
            notify_inline = InlineKeyboardMarkup(row_width=2)
            notify_inline.add(
                InlineKeyboardButton("📩 Откликнуться",   callback_data=f"apply:{employer_id}:{vac_id}"),
                InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f"review:{employer_id}:{vac_id}"),
            )
            for sub_uid in subscribers:
                if sub_uid == employer_id:
                    continue
                try:
                    bot.send_message(sub_uid, notify_text,
                                     parse_mode="Markdown", reply_markup=notify_inline)
                except Exception:
                    pass

@bot.message_handler(func=lambda m: m.text == '👥 Найти работников')
def find_workers(message):
    bot.send_message(message.chat.id, "👥 Раздел поиска работников — скоро будет доступен.")

# ── Мои отклики (работник) ───────────────────────────────────

@bot.message_handler(func=lambda m: m.text == '📬 Мои отклики')
def my_applications(message):
    cid = message.chat.id
    apps = db.get_applications_for_worker(cid)
    if not apps:
        bot.send_message(cid,
            "📬 У вас пока нет откликов.\n"
            "Найдите вакансию через 🔍 Найти работу и откликнитесь.",
            reply_markup=worker_menu_markup())
        return
    bot.send_message(cid,
        f"📬 *Ваши отклики* — всего {len(apps)}:",
        parse_mode="Markdown")
    for a in apps:
        st_label = db.APPLICATION_STATUS_LABEL.get(a['status'], a['status'])
        date = (a.get('created_at') or '')[:10]
        lines = [
            f"🏢 *{a.get('company', '—')}*",
            f"👷 {a.get('profession', '—')} — {a.get('vac_city', '—')}",
            f"💰 {a.get('salary', '—')}",
            f"📊 Статус: {st_label}",
            f"_Дата отклика: {date}_",
        ]
        bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

# ── Жалобы на работодателей ───────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith('complaint:'))
def handle_complaint_start(call):
    cid = call.message.chat.id
    employer_id = int(call.data.split(':')[1])
    bot.answer_callback_query(call.id)
    inline = InlineKeyboardMarkup(row_width=1)
    for key, label in COMPLAINT_REASONS.items():
        inline.add(InlineKeyboardButton(label, callback_data=f"cmp_reason:{employer_id}:{key}"))
    bot.send_message(cid,
        "⚠️ *Жалоба на работодателя*\n\nВыберите причину жалобы:",
        parse_mode="Markdown", reply_markup=inline)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cmp_reason:'))
def handle_complaint_reason(call):
    cid = call.message.chat.id
    parts = call.data.split(':')
    employer_id = int(parts[1])
    reason_key  = parts[2]
    if reason_key not in COMPLAINT_REASONS:
        bot.answer_callback_query(call.id, "Неверная причина.")
        return
    bot.answer_callback_query(call.id)
    complaint_states[cid] = {'employer_id': employer_id, 'reason': reason_key}
    reason_label = COMPLAINT_REASONS[reason_key]
    bot.send_message(cid,
        f"📝 Причина: *{reason_label}*\n\n"
        "Опишите ситуацию подробнее (или отправьте /skip_complaint чтобы пропустить):",
        parse_mode="Markdown")

@bot.message_handler(commands=['skip_complaint'])
def handle_complaint_skip(message):
    cid = message.chat.id
    if cid not in complaint_states:
        return
    state = complaint_states.pop(cid)
    _save_complaint(cid, state, text=None)

@bot.message_handler(func=lambda m: m.chat.id in complaint_states)
def handle_complaint_text(message):
    cid = message.chat.id
    state = complaint_states.pop(cid)
    _save_complaint(cid, state, text=message.text.strip())

def _save_complaint(user_id, state, text):
    employer_id = state['employer_id']
    reason_key  = state['reason']
    result = db.add_complaint(employer_id, user_id, reason_key, text)
    if result:
        reason_label = COMPLAINT_REASONS.get(reason_key, reason_key)
        bot.send_message(user_id,
            f"✅ *Жалоба принята*\n\n"
            f"Причина: {reason_label}\n"
            "Администратор рассмотрит её в ближайшее время. Спасибо за обратную связь.",
            parse_mode="Markdown")
        # Уведомляем администратора если ADMIN_ID задан
        if ADMIN_ID:
            try:
                bot.send_message(ADMIN_ID,
                    f"⚠️ *Новая жалоба!*\n"
                    f"Причина: {reason_label}\n"
                    f"Работодатель ID: {employer_id}",
                    parse_mode="Markdown")
            except Exception:
                pass
    else:
        bot.send_message(user_id,
            "ℹ️ Вы уже подавали жалобу по этой причине на данного работодателя.")

# ── Админ: жалобы ─────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data == 'admin_complaints')
def admin_complaints_list(call):
    if not _is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "🚫 Нет доступа.")
        return
    bot.answer_callback_query(call.id)
    complaints = db.get_pending_complaints()
    if not complaints:
        bot.send_message(call.message.chat.id, "✅ Новых жалоб нет.")
        return
    bot.send_message(call.message.chat.id,
        f"⚠️ *Жалобы на рассмотрении* ({len(complaints)}):",
        parse_mode="Markdown")
    for c in complaints:
        reason_label = COMPLAINT_REASONS.get(c['reason'], c['reason'])
        date = (c.get('created_at') or '')[:10]
        text_preview = (c.get('text') or '_без описания_')[:120]
        msg = (
            f"🏢 *{c.get('company') or '—'}*\n"
            f"📌 Причина: {reason_label}\n"
            f"📅 Дата: {date}\n"
            f"💬 {text_preview}"
        )
        inline = InlineKeyboardMarkup()
        inline.add(InlineKeyboardButton(
            "✅ Отметить рассмотренной", callback_data=f"admin_cmp_resolve:{c['id']}"))
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown", reply_markup=inline)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_cmp_resolve:'))
def admin_complaint_resolve(call):
    if not _is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "🚫 Нет доступа.")
        return
    complaint_id = int(call.data.split(':')[1])
    db.resolve_complaint(complaint_id)
    bot.answer_callback_query(call.id, "✅ Жалоба отмечена как рассмотренная.")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    bot.edit_message_text(
        call.message.text + "\n\n✅ _Рассмотрена_",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# ── Внутренний чат ───────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith('chat_open:'))
def handle_chat_open(call):
    cid = call.message.chat.id
    parts = call.data.split(':')
    app_id   = int(parts[1])
    my_role  = parts[2]          # 'employer' или 'worker'

    app = db.get_application_by_id(app_id)
    if not app or app['status'] != 'accepted':
        bot.answer_callback_query(call.id, "💬 Чат доступен только для принятых откликов.")
        return

    # Определяем receiver
    if my_role == 'employer':
        if app['employer_id'] != cid:
            bot.answer_callback_query(call.id, "🚫 Нет доступа.")
            return
        receiver_id = app['worker_id']
    else:
        if app['worker_id'] != cid:
            bot.answer_callback_query(call.id, "🚫 Нет доступа.")
            return
        receiver_id = app['employer_id']

    # Проверяем блокировку (заблокировал ли receiver нас)
    if db.is_blocked(cid, receiver_id):
        bot.answer_callback_query(call.id, "🚫 Вы не можете отправить сообщение этому пользователю.")
        return

    chat_states[cid] = {'app_id': app_id, 'receiver_id': receiver_id, 'my_role': my_role}
    bot.answer_callback_query(call.id)
    bot.send_message(cid,
        "💬 Напишите сообщение (или /cancel для отмены):",
        reply_markup=ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.chat.id in chat_states)
def handle_chat_message(message):
    cid   = message.chat.id
    state = chat_states.pop(cid)
    app_id      = state['app_id']
    receiver_id = state['receiver_id']
    my_role     = state['my_role']
    text        = message.text.strip() if message.text else ''

    if not text:
        bot.send_message(cid, "⚠️ Пустое сообщение не отправлено.")
        return

    # Повторно проверяем блокировку
    if db.is_blocked(cid, receiver_id):
        bot.send_message(cid,
            "🚫 Сообщение не доставлено — получатель вас заблокировал.",
            reply_markup=main_menu_markup())
        return

    # Сохраняем в БД
    db.save_message(app_id, cid, receiver_id, text)

    # Подтверждение отправителю
    bot.send_message(cid, "✅ Сообщение отправлено.")

    # Формируем кнопки для получателя
    receiver_role = 'worker' if my_role == 'employer' else 'employer'
    sender_label  = "работодателя" if my_role == 'employer' else "кандидата"
    reply_inline = InlineKeyboardMarkup(row_width=1)
    reply_inline.add(
        InlineKeyboardButton("💬 Ответить",          callback_data=f"chat_open:{app_id}:{receiver_role}"),
        InlineKeyboardButton("🚫 Заблокировать",     callback_data=f"block_chat:{app_id}:{cid}"),
    )

    try:
        bot.send_message(receiver_id,
            f"💬 *Новое сообщение от {sender_label}:*\n\n{text}",
            parse_mode="Markdown",
            reply_markup=reply_inline)
    except Exception:
        bot.send_message(cid,
            "⚠️ Сообщение сохранено, но не удалось доставить получателю.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('block_chat:'))
def handle_block_chat(call):
    cid   = call.message.chat.id
    parts = call.data.split(':')
    app_id    = int(parts[1])
    target_id = int(parts[2])

    # Проверяем, что вызывающий — участник этой заявки
    app = db.get_application_by_id(app_id)
    if not app or cid not in (app['worker_id'], app['employer_id']):
        bot.answer_callback_query(call.id, "🚫 Нет доступа.")
        return

    db.block_user(cid, target_id)
    bot.answer_callback_query(call.id, "🚫 Пользователь заблокирован.")
    # Убираем кнопки из исходного сообщения
    try:
        bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    bot.send_message(cid,
        "🚫 *Пользователь заблокирован.*\n"
        "Он больше не сможет отправлять вам сообщения через бота.\n\n"
        "Если передумаете — обратитесь в поддержку.",
        parse_mode="Markdown")

# ── Прочие разделы ────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == 'ℹ️ О проекте')
def about(message):
    bot.send_message(message.chat.id,
        "ℹ️ О проекте\n\n"
        "Vahta-bot — платформа для поиска работы и сотрудников.\n"
        "Мы помогаем соискателям и работодателям найти друг друга быстро и удобно.")

print("Бот запущен")

bot.infinity_polling()
