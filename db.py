import sqlite3


def get(tid):
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT token, refresh FROM users WHERE telegramid=?', (str(tid),))
    res = list(cursor)
    cursor.close()
    return res[0] if len(res) != 0 else None


def update(tid, token, refresh):
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET token = ?, refresh=? WHERE telegramid=?', (token, refresh, str(tid)))
    conn.commit()
    cursor.close()


def add(tid, token, refresh):
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users(telegramid,token,refresh) VALUES(?,?,?)', (str(
        tid), token, refresh))
    conn.commit()
    cursor.close()


def list_tids():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT telegramid FROM users')
    res = list(cursor)
    cursor.close()
    return [i[0] for i in res]


def delete(tid):
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE telegramid = ?', (str(tid),))
    conn.commit()
    cursor.close()
