import telebot
from telebot import types
from dnevnikc import *
from datetime import datetime
import os
from dotenv import load_dotenv
import db
import json

load_dotenv()
tgtoken = os.getenv('TOKEN')
bot = telebot.TeleBot(tgtoken)

week = None
weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']

spec_chr = ['\\', '_', '*', '[', ']',
            '(', ')', '~', '`', '>', '<', '&', '#', '+', '-', '=', '|', '{', '}', '.', '!']


def esc_md(text):
    for char in spec_chr:
        text = text.replace(char, f'\\{char}')
    return text


def buttons(message):
    temp = db.get(message.chat.id)
    if temp != None:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        d = dnevnik(temp)
        temp = d.profile()
        b1 = types.KeyboardButton(
            "🗓 Расписание "+str(temp['classInfo']['number'])+temp['classInfo']['litera'])
        b2 = types.KeyboardButton("На завтра")
        b3 = types.KeyboardButton("На сегодня")
        b4 = types.KeyboardButton("📋 Оценки на этой неделе")
        b5 = types.KeyboardButton("📋 Все оценки")
        b6 = types.KeyboardButton("📄 Список команд")
        b7 = types.KeyboardButton("✍️ Домашние задания")
        markup.add(b1).row(b2, b3).row(b5).row(b7, b4).row(b6)
        return markup
    else:
        return types.ReplyKeyboardRemove()


@bot.message_handler(commands=['pgrades'])
def get_grades_year(message):
    temp = db.get(message.chat.id)
    if temp != None:
        d = dnevnik(temp)
        res = ''
        for i in d.grades_year():
            for j in range(4):
                if i['grades'][j] == None:
                    i['grades'][j] = '━'
            if i['yeargrade'] == None:
                i['yeargrade'] = '━'
            res += i['name']+'\n└ '+i['grades'][0]+' • '+i['grades'][1]+' • ' + \
                i['grades'][2]+' • '+i['grades'][3] + \
                '   Итог: '+i['yeargrade']+'\n'
        if res != '':
            res = 'Четвертные оценки\n\n'+res
            bot.send_message(message.chat.id, res,
                             reply_markup=buttons(message))
        else:
            bot.send_message(
                message.chat.id, 'Оценок в четвертях пока нет', reply_markup=buttons(message))
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


def get_grades_period(message, period):
    temp = db.get(message.chat.id)
    if temp != None:
        d = dnevnik(temp)
        res = ''
        for i in d.grades_period(period):
            temp = ''
            if i['grades'] != []:
                for j in i['grades']:
                    for u in j[:-1]:
                        temp += u+'/'
                    temp += j[-1]+' • '
            if temp == '':
                res += i['name']+'\n└ ━\n'
            else:
                res += i['name']+" • " + \
                    str(round(i['averagew'], 2))+"\n└ "+temp[:-2]+'\n'
        if res == '':
            res = ['В', 'Во', 'В', 'В'][period]+' ' + \
                str(period+1)+' четверти пока нет оценок'
        else:
            res = str(period+1)+' четверть\n\n'+res
        bot.send_message(message.chat.id, res, reply_markup=buttons(message))
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


@bot.message_handler(commands=['wgrades'])
def get_grades_week(message):
    temp = db.get(message.chat.id)
    if temp != None:
        d = dnevnik(temp)
        res = ''
        gr = d.grades_week()
        for i in gr:
            res += i+'\n└ '
            for j in gr[i]:
                res += '/'.join(str(x) for x in j)+" • "
            res = res[:-2]+'\n'
        if res == '':
            res = 'На этой неделе пока нет оценок'
        else:
            res = 'Текущая неделя\n\n'+res
        bot.send_message(message.chat.id, res)
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


@bot.message_handler(commands=['start'])
def start_message(message):
    temp = db.get(message.chat.id)
    if temp == None:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton(
            "📄 Список команд", callback_data='help')
        b2 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1).row(b2)
        bot.send_message(
            message.chat.id, 'Здравствуйте! Зарегистрируйтесь, чтобы в дальнейшем пользоваться ботом', reply_markup=markup)
    else:
        b1 = types.InlineKeyboardButton(
            "📄 Список команд", callback_data='help')
        markup = types.InlineKeyboardMarkup()
        markup.add(b1)
        bot.send_message(
            message.chat.id, "Вы уже зарегистрированны", reply_markup=markup)


@bot.message_handler(commands=['login'])
def login(message):
    if db.get(message.chat.id) == None:
        webapp = types.WebAppInfo("https://zasdc.ru/static/bot/login.html")
        b1 = types.KeyboardButton(text="Регистрация", web_app=webapp)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(b1)
        bot.send_message(
            message.chat.id, "Чтобы зарегистрироваться нажмите кнопку снизу\\. \nТакже обязательно прочтите [инструкцию](https://telegra.ph/Instrukciya-dlya-registracii-10-25)", reply_markup=markup, parse_mode='MarkdownV2')
    else:
        b1 = types.InlineKeyboardButton(
            "📄 Список команд", callback_data='help')
        markup = types.InlineKeyboardMarkup()
        markup.add(b1)
        bot.send_message(
            message.chat.id, "Вы уже зарегистрированны", reply_markup=buttons(message))


@bot.message_handler(content_types="web_app_data")
def logindata(message):
    temp = json.loads(message.web_app_data.data)
    d = dnevnik((temp['accessToken'], temp['refreshToken']))
    temp = d.refresh()
    if temp == False:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton(
            "✏️ Попробовать снова", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, "Произошла ошибка. Возможно вы ввели неверные токены.\nПопробуйте заного", reply_markup=markup)
    else:
        db.add(message.chat.id, temp[0], temp[1])
        b1 = types.InlineKeyboardButton(
            "📄 Список команд", callback_data='help')
        markup = types.InlineKeyboardMarkup()
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы успешно зарегистрировались', reply_markup=markup)


def schedule(message, day):
    temp = db.get(message.chat.id)
    if temp != None:
        d = dnevnik(temp)
        sch = d.schedule(day)
        res = weekdays[day]+'\n\n'
        if sch != 0:
            for i in sch:
                res += i['num']+'│'+i['name']+" • "+i['room']+"\n"
        else:
            res += "Уроков нет"
        bot.send_message(message.chat.id, res)
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


@bot.message_handler(commands=['help'])
def help(message):
    msg = '🛠 Сервис\n/login • Регистрация\n/help • Это меню\n/profile • Информация об аккаунте\n/delacc • Удалить аккаунт в боте\n\n📅 Расписание\n/all • Расписание на любой день\n/today • Расписание на сегодня\n/nextday • Расписание на завтра\n/calls • Расписание звонков\n\n📋 Оценки\n/grades • Все оценки\n/wgrades • Оценки на этой неделе\n/pgrades • Четвертные оценки\n\n✍️ Домашнее задание\n/homework • ДЗ по дням'
    bot.send_message(message.chat.id, msg, reply_markup=buttons(message))


@bot.message_handler(commands=['delacc'])
def deleteaccount(message):
    temp = db.get(message.chat.id)
    if temp != None:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("Да", callback_data='deleteacc1')
        b2 = types.InlineKeyboardButton(
            "Нет, отмена", callback_data='deleteacc0')
        markup.add(b1, b2)
        bot.send_message(message.chat.id, 'Удалить аккаунт?',
                         reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Чтобы удалить аккаунт, нужно зарегистрироваться', reply_markup=markup)


@bot.message_handler(commands=['profile'])
def profile(message):
    temp = db.get(message.chat.id)
    if temp != None:
        d = dnevnik(temp)
        temp = d.profile()
        bot.send_message(message.chat.id, temp['user']['lastName']+" "+temp['user']['firstName']+" "+str(
            temp['classInfo']['number'])+temp['classInfo']['litera']+'\n\nУдалить аккаунт - /delacc')
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


def texthomework(message, hw):
    date = [int(i) for i in hw['date'].split('-')]
    now = datetime(date[0], date[1], date[2])
    res = esc_md(weekdays[now.weekday()]+' • '+str(date[2]) +
                 '-'+str(date[1])+'-'+str(date[0])+'\n\n')
    for i in hw['homework']:
        res += esc_md(i[0])+':\n>'+esc_md(i[1])+'||\n'
    markup = types.InlineKeyboardMarkup()

    cd = 0
    if hw['pages']['previousDate'] != "0001-01-01":
        cd = 'hw'+hw['pages']['previousDate']
    b1 = types.InlineKeyboardButton("◀", callback_data=cd)
    cd = 0
    if hw['pages']['nextDate'] != "0001-01-01":
        cd = 'hw'+hw['pages']['nextDate']
    b2 = types.InlineKeyboardButton("▶", callback_data=cd)
    markup.add(b1, b2)
    return res, markup


@bot.message_handler(commands=['homework'])
def homework(message):
    temp = db.get(message.chat.id)
    if temp != None:
        d = dnevnik(temp)
        temp = d.homework(None)
        res, markup = texthomework(message, temp)
        bot.send_message(message.chat.id, res,
                         reply_markup=markup, parse_mode='MarkdownV2')
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


@bot.callback_query_handler(func=lambda callback: True)
def callback_msg(callback):
    temp = db.get(callback.message.chat.id)
    if callback.data == 'reg':
        login(callback.message)
    elif callback.data == 'help':
        help(callback.message)
    elif temp != None:
        if 'schedule' in callback.data:
            bot.delete_message(callback.message.chat.id,
                               callback.message.message_id)
            schedule(callback.message, int(callback.data[-1]))
        if 'deleteacc' in callback.data:
            if callback.data[-1] == '1':
                markup = types.InlineKeyboardMarkup()
                b1 = types.InlineKeyboardButton(
                    "✏️ Повторная регистрация", callback_data='reg')
                markup.add(b1)
                bot.send_message(callback.message.chat.id,
                                 'Ваш аккаунт удален', reply_markup=markup)
                bot.delete_message(callback.message.chat.id,
                                   callback.message.message_id)
            else:
                bot.delete_message(callback.message.chat.id,
                                   callback.message.message_id)

        if 'grades' in callback.data:
            if callback.data[0] == 'p':
                bot.delete_message(callback.message.chat.id,
                                   callback.message.message_id)
                get_grades_period(callback.message, int(callback.data[-1]))
            if callback.data[0] == 'w':
                bot.delete_message(callback.message.chat.id,
                                   callback.message.message_id)
                get_grades_week(callback.message)
            if callback.data[0] == 'y':
                bot.delete_message(callback.message.chat.id,
                                   callback.message.message_id)
                get_grades_year(callback.message)
        if 'hw' in callback.data:
            d = dnevnik(temp)
            temp = d.homework(callback.data[2:])
            res, markup = texthomework(callback.message, temp)
            bot.edit_message_text(chat_id=callback.message.chat.id, message_id=callback.message.message_id,
                                  text=res, reply_markup=markup, parse_mode='MarkdownV2')
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(callback.message.chat.id,
                         'Вы не зарегистрированны', reply_markup=markup)


@bot.message_handler(commands=['calls'])
def calls(message):
    bot.send_message(message.chat.id, 'Расписание звонков\n\n1 │ 8:30 - 9:10\n2 │ 9:20 - 10:00\n3 │ 10:20 - 11:00\n4 │ 11:20 - 12:00\n5 │ 12:20 - 13:00\n6 │ 13:10 - 13:50\n7 │ 14:05 - 14:45\n8 │ 14:55 - 15:35')


@bot.message_handler(commands=['grades'])
def grades_select(message):
    temp = db.get(message.chat.id)
    if temp != None:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton(
            "Текущая неделя", callback_data='wgrades')
        b2 = types.InlineKeyboardButton("1 четверть", callback_data='pgrades0')
        b3 = types.InlineKeyboardButton("2 четверть", callback_data='pgrades1')
        b4 = types.InlineKeyboardButton("3 четверть", callback_data='pgrades2')
        b5 = types.InlineKeyboardButton("4 четверть", callback_data='pgrades3')
        b6 = types.InlineKeyboardButton(
            "По четвертям", callback_data='ygrades')
        markup.add(b1).row(b2, b3).row(b4, b5).row(b6)
        bot.send_message(message.chat.id, 'Выберите период',
                         reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


@bot.message_handler(content_types=['text'])
def text(message):
    temp = db.get(message.chat.id)
    if 'Список команд' in message.text:
        help(message)
    elif temp != None:
        if message.text == 'На сегодня' or message.text == '/today':
            schedule(message, datetime.now().weekday() % 6)
        elif message.text == 'На завтра' or message.text == '/nextday':
            schedule(message, (datetime.now().weekday()+1) % 6)
        elif 'Расписание ' in message.text or message.text == '/all':
            markup = types.InlineKeyboardMarkup()
            b1 = types.InlineKeyboardButton(
                "Понедельник", callback_data='schedule0')
            b2 = types.InlineKeyboardButton(
                "Вторник", callback_data='schedule1')
            b3 = types.InlineKeyboardButton("Среда", callback_data='schedule2')
            b4 = types.InlineKeyboardButton(
                "Четверг", callback_data='schedule3')
            b5 = types.InlineKeyboardButton(
                "Пятница", callback_data='schedule4')
            b6 = types.InlineKeyboardButton(
                "Суббота", callback_data='schedule5')
            markup.add(b1, b2, b3, b4, b5, b6)
            bot.send_message(message.chat.id, 'Выберите день',
                             reply_markup=markup)
        elif 'на этой неделе' in message.text:
            get_grades_week(message)
        elif 'Все оценки' in message.text:
            grades_select(message)
        elif 'Домашние' in message.text:
            homework(message)

    else:
        markup = types.InlineKeyboardMarkup()
        b1 = types.InlineKeyboardButton("✏️ Регистрация", callback_data='reg')
        markup.add(b1)
        bot.send_message(
            message.chat.id, 'Вы не зарегистрированны', reply_markup=markup)


bot.infinity_polling()
