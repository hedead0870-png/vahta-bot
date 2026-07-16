import telebot
from config import TOKEN

bot = telebot.TeleBot(TOKEN)

users = {}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if user_id not in users:
        users[user_id] = {
            "city": "Не указан",
            "job": "Не указана"
        }

    bot.send_message(
        message.chat.id,
        "Добро пожаловать в бот ВАХТА 👷\n\n"
        "Команды:\n"
        "/profile — мой профиль\n"
        "/city — изменить город работодателя"
    )


@bot.message_handler(commands=['profile'])
def profile(message):
    user = users.get(message.from_user.id)

    if user:
        bot.send_message(
            message.chat.id,
            f"🏙 Город: {user['city']}\n"
            f"👷 Должность: {user['job']}"
        )
    else:
        bot.send_message(message.chat.id, "Нажмите /start")


@bot.message_handler(commands=['city'])
def change_city(message):
    bot.send_message(message.chat.id, "Введите новый город работодателя:")
    bot.register_next_step_handler(message, save_city)


def save_city(message):
    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {}

    users[user_id]["city"] = message.text

    bot.send_message(
        message.chat.id,
        f"✅ Город изменён на: {message.text}"
    )


bot.infinity_polling()
