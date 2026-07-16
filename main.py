import telebot
from config import TOKEN

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    print("Получена команда start")
    bot.send_message(message.chat.id, "Работаю ✅")

print("Бот запущен")

bot.infinity_polling()
