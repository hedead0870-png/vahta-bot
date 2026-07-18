import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from config import TOKEN

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        KeyboardButton('🔍 Ищу работу'),
        KeyboardButton('🏢 Работодатель'),
        KeyboardButton('ℹ️ О проекте')
    )
    bot.send_message(message.chat.id, "Привет! Выбери нужный раздел:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '🔍 Ищу работу')
def looking_for_job(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('👤 Мои данные'), KeyboardButton('⛺ Моя вахта'))
    markup.add(KeyboardButton('💰 Зарплата'), KeyboardButton('💸 Расходы'))
    markup.add(KeyboardButton('🔍 Найти работу'))
    markup.add(KeyboardButton('🏠 Главное меню'))
    bot.send_message(message.chat.id, "🔍 Меню работника:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '🏠 Главное меню')
def main_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        KeyboardButton('🔍 Ищу работу'),
        KeyboardButton('🏢 Работодатель'),
        KeyboardButton('ℹ️ О проекте')
    )
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=markup)

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

@bot.message_handler(func=lambda m: m.text == '👤 Мои данные')
def my_data(message):
    bot.send_message(message.chat.id, "👤 Ваш профиль пока не заполнен")

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

print("Бот запущен")

bot.infinity_polling()
