from dnevnikc import dnevnik
import db
import time
import datetime

while True:
    for i in db.list_tids():
        id = i[0]
        tokens = db.get(id)

        d = dnevnik(tokens)
        res = d.refresh()
        if res != False:
            db.update(id, res[0], res[1])
            print(str(datetime.datetime.now().time())[:-7])
            print(id, '+', res[0][-5:])
        else:
            db.delete(id)
            print(datetime.datetime.now().time()[:-7])
            print(id, '-')

    time.sleep(60*60*3)
