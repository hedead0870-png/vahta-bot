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

print("Бот запущен")

bot.infinity_polling()
