import logging
import ast
import telegram
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from bot_config import token, adminlist, proxy
from edu_parser.profile import Profile
from edu_parser.exceptions import *
from datetime import datetime
import os

bot = telegram.Bot(token=token)
updater = Updater(token=token)
dispatcher = updater.dispatcher

users = {}

START_CREDENTIALS = 0
GET_TERM = 1
GET_DAY = 2
PREDICT_SUBJECT = 3


def check_creds(f):
    def wrap(bot, update):
        global users
        chat = update.message.chat_id
        try:
            return f(bot, update)
        except CredentialsError:
            try:
                del users[chat]
            except KeyError:
                pass
            bot.send_message(chat_id=chat, text="Ваш логин или пароль более не подходит для входа в систему, для того, чтобы продолжить работу с ботом используйте команду /start и введите ваши новые данные для входа")
            return ConversationHandler.END

    return wrap


def start(bot, update):
    global users
    chat = update.message.chat_id
    user = update.message.from_user

    if users.get(chat) is not None:
        return ConversationHandler.END

    bot.send_message(chat_id=chat, text="Здравствуйте! Для того, чтобы начать работу с ботом вам необходимо "
                                        "предоставить ваш логин и пароль от личного кабинета edu.tatar.ru в формате "
                                        "логин:пароль")
    
    return START_CREDENTIALS


def credentials(bot, update):
    global users
    chat = update.message.chat_id

    reply = update.message.text.replace(' ', '')
    try:
        if len(reply.split(':')) != 2:
            raise ValueError()
        creds = {'main_login': reply.split(':')[0], 'main_password': reply.split(':')[1]}
    except BaseException:
        bot.send_message(chat_id=chat, text="Неправильный формат данных. Попробуйте еще раз.")
        return START_CREDENTIALS
    
    try:
        bot.send_message(chat_id=chat, text="Пожалуйста, подождите...")
        users[chat] = Profile(creds, proxy=proxy)
    except CredentialsError:
        bot.send_message(chat_id=chat, text="Неправильный логин или пароль. Попробуйте еще раз.")
        return START_CREDENTIALS

    bot.send_message(chat_id=chat, text="Авторизация прошла успешно. Начните работу с ботом с команды /help")
    with open('credentials/{}.txt'.format(chat), 'w') as f:
        f.write(str(creds))
    return ConversationHandler.END


def helpp(bot, update):
    chat = update.message.chat_id

    reply_msg = '<b>Список команд:</b> \n\n' \
                '/help - список команд; \n' \
                '/diary_curterm - табель оценок за текущую четверть/полугодие; \n' \
                '/diary_term - получить оценки за выбранную четверть/полугодие; \n' \
                '/diary_today - показать страницу дневника за сегодня; \n' \
                '/diary_day - показать страницу дневника за указанный день; \n' \
                '/profile_info - показать данные профиля; \n' \
                '/check_grades - проверить наличие новых оценок; \n' \
                '/predict - предсказать средний балл за указанный предмет (имя предмета не чувствительно к регистру, также не обязательно писать его полностью, достаточно, например "русский" или "обж"); \n' \
                '/cancel - отменить действие.'
    
    bot.send_message(chat_id=chat, text=reply_msg, parse_mode=telegram.ParseMode.HTML)


def cancel(bot, update):
    chat = update.message.chat_id
    
    bot.send_message(chat_id=chat, text='Команда отменена', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


@check_creds
def get_profile_info(bot, update):
    global users
    chat = update.message.chat_id

    user_data = users[chat].data
    reply_msg = '<b>Информация о вашем профиле:</b>\n'
    translation = {
        'name': 'Имя',
        'login': 'Логин',
        'school': 'Школа',
        'position': 'Должность',
        'birthday': 'День рождения',
        'gender': 'Пол',
        'cert': 'Номер сертификата'
    }
    for key, value in user_data.items():
        reply_msg += '<b>{}</b>: {}\n'.format(translation[key], value)
    
    bot.send_message(chat_id=chat, text=reply_msg, parse_mode=telegram.ParseMode.HTML)


@check_creds
def get_diary_curterm(bot, update):
    global users
    chat = update.message.chat_id

    bot.send_message(chat_id=chat, text="Пожалуйста, подождите...")
    diary = users[chat].diary_term(draw=True, draw_path=str(chat)+'grades.png')
    bot.send_photo(chat_id=chat, photo=open(str(chat)+'grades.png', 'rb'))


def get_diary_term(bot, update):
    chat = update.message.chat_id

    bot.send_message(chat_id=chat, text="Введите номер четверти/полугодия")
    return GET_TERM


@check_creds
def get_diary_numterm(bot, update):
    global users
    chat = update.message.chat_id

    try:
        reply = int(update.message.text)
    except ValueError:
        bot.send_message(chat_id=chat, text="Неправильный формат. Проверьте правильность введенных данных и попробуйте еще раз")
        return GET_TERM

    bot.send_message(chat_id=chat, text="Пожалуйста, подождите...")
    diary = users[chat].diary_term(term=str(reply), draw=True, draw_path=str(chat)+'grades' + str(reply) + '.png')
    bot.send_photo(chat_id=chat, photo=open(str(chat)+'grades' + str(reply) + '.png', 'rb'))
    return ConversationHandler.END


@check_creds
def get_diary_today(bot, update):
    global users
    chat = update.message.chat_id

    bot.send_message(chat_id=chat, text="Пожалуйста, подождите...")
    diary = users[chat].diary_day()

    weekday = {
        0: 'Понедельник',
        1: 'Вторник',
        2: 'Среда',
        3: 'Четверг',
        4: 'Пятница',
        5: 'Суббота',
        6: 'Воскресенье'
    }
    reply_msg = '<b>Страница дневника на {} - {}:\n</b>'.format(weekday[diary.weekday], diary.date_str)
    
    for subject in diary.subjects:
        new_line = '<b>{} - {}:</b>\nДомашнаяя работа: {}\nКомментарий: {}\nОценки:\n'.format(
            subject.time, subject.name, subject.homework, subject.comment    
        )
        for grade in subject.grades:
            new_line += '{} - {}\n'.format(grade.grade, grade.comment)
        new_line += '\n'
        reply_msg += new_line

    bot.send_message(chat_id=chat, text=reply_msg, parse_mode=telegram.ParseMode.HTML)


def get_diary_day(bot, update):
    chat = update.message.chat_id

    bot.send_message(chat_id=chat, text="Введите дату в формате DD.MM.YYYY")
    return GET_DAY


@check_creds
def get_diary_numday(bot, update):
    global users
    chat = update.message.chat_id

    reply = update.message.text
    try:
        datetime.strptime(reply, '%d.%m.%Y')
    except BaseException:
        bot.send_message(chat_id=chat, text="Неправильный формат. Проверьте правильность введенных данных и попробуйте еще раз")
        return GET_DAY

    bot.send_message(chat_id=chat, text="Пожалуйста, подождите...")
    diary = users[chat].diary_day(date=reply)

    weekday = {
        0: 'Понедельник',
        1: 'Вторник',
        2: 'Среда',
        3: 'Четверг',
        4: 'Пятница',
        5: 'Суббота',
        6: 'Воскресенье'
    }
    reply_msg = '<b>Страница дневника на {} - {}:\n</b>'.format(weekday[diary.weekday], diary.date_str)
    
    for subject in diary.subjects:
        new_line = '<b>{} - {}:</b>\nДомашнаяя работа: {}\nКомментарий: {}\nОценки:\n'.format(
            subject.time, subject.name, subject.homework, subject.comment    
        )
        for grade in subject.grades:
            new_line += '{} - {}\n'.format(grade.grade, grade.comment)
        new_line += '\n'
        reply_msg += new_line

    bot.send_message(chat_id=chat, text=reply_msg, parse_mode=telegram.ParseMode.HTML)
    return ConversationHandler.END


def predict(bot, update):
    chat = update.message.chat_id
    bot.send_message(chat_id=chat, text='Введите предмет и оценки, которые вы планируете получить в формате "Английский 5 5 5 5"')
    
    return PREDICT_SUBJECT


@check_creds
def predict_subject(bot, update):
    global users

    chat = update.message.chat_id
    reply = update.message.text.split()
    if len(reply) < 2:
        bot.send_message(chat_id=chat, text="Неправильный формат. Проверьте правильность введенных данных и попробуйте еще раз (учитывайте, что вы не можете указать менее одной оценки)")
        return PREDICT_SUBJECT
    diary = users[chat].diary_term()
    subject = diary.get_subject(reply[0])
    if subject is None:
        bot.send_message(chat_id=chat, text="Неправильный формат. Проверьте правильность введенных данных и попробуйте еще раз (учитывайте, что вы не можете указать менее одной оценки)")
        return PREDICT_SUBJECT
    new_grades = list(map(int, reply[1:]))
    bot.send_message(chat_id=chat, text='Ваш новый балл средний балл будет равен {}'.format(subject.predict(new_grades)))
    return ConversationHandler.END


@check_creds
def check_grades(bot, update):
    global users
    chat = update.message.chat_id

    bot.send_message(chat_id=chat, text="Пожалуйста, подождите...")
    new_grades = users[chat].check_grades()

    if not new_grades:
        bot.send_message(chat_id=chat, text="Новых оценок нет")
        return None

    reply = ''
    for key, value in new_grades.items():
        reply += '{}: {}\n'.format(key, ', '.join(value))
    bot.send_message(chat_id=chat, text=reply)


def shutdown(bot, update):
    global updater

    chat = update.message.chat_id
    user = update.message.from_user
    
    if user['username'] not in adminlist:
        bot.send_message(chat_id=chat, text='Извините, по-видимому, у вас нет прав на исполнение данной команды')
    else:
        bot.send_message(chat_id=chat, text='Бот был успешно выключен')
        updater.stop()
        dispatcher.stop()
        bot.stop()
        exit(0)


def main():
    global bot, updater, dispatcher, users

    for filename in os.listdir('credentials'):
        with open('credentials/' + filename) as f:
                users[int(filename.split('.txt')[0])] = Profile(ast.literal_eval(f.readline()), proxy=proxy)
    print(users)

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    start_handler = CommandHandler('start', start)

    get_diary_term_handler = CommandHandler('diary_term', get_diary_term)

    get_diary_day_handler = CommandHandler('diary_day', get_diary_day)

    predict_handler = CommandHandler('predict', predict)

    cancel_handler = CommandHandler('cancel', cancel)

    help_handler = CommandHandler('help', helpp)
    dispatcher.add_handler(help_handler)

    check_grades_handler = CommandHandler('check_grades', check_grades)
    dispatcher.add_handler(check_grades_handler)

    get_profile_info_handler = CommandHandler('profile_info', get_profile_info)
    dispatcher.add_handler(get_profile_info_handler)

    get_diary_curterm_handler = CommandHandler('diary_curterm', get_diary_curterm)
    dispatcher.add_handler(get_diary_curterm_handler)

    get_diary_today_handler = CommandHandler('diary_today', get_diary_today)
    dispatcher.add_handler(get_diary_today_handler)
    
    shutdown_handler = CommandHandler('shutdown', shutdown)
    dispatcher.add_handler(shutdown_handler)

    dispatcher.add_handler(ConversationHandler(
        entry_points=[start_handler, get_diary_term_handler, get_diary_day_handler, predict_handler],
        states={
            START_CREDENTIALS: [MessageHandler(Filters.text, credentials)],
            GET_TERM: [MessageHandler(Filters.text, get_diary_numterm)],
            GET_DAY: [MessageHandler(Filters.text, get_diary_numday)],
            PREDICT_SUBJECT: [MessageHandler(Filters.text, predict_subject)]
        },
        fallbacks=[cancel_handler]
    ))

    updater.start_polling()


if __name__ == '__main__':
    main()