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
    bot.send_message(message.chat.id,
        "🔍 Раздел «Ищу работу»\n\n"
        "Здесь вы найдёте актуальные вакансии и сможете откликнуться на подходящие предложения.")

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
