import sys
import codecs

import sqlite3 as sql


# Nasty hack to force utf-8 encoding by default:
reload(sys)
sys.setdefaultencoding('utf8')

# Change stdout to allow printing of unicode characters:
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)


_HANDLENUMBER = {}
_NUMBERNAME = {}

with sql.connect('sms.db') as sms_db:
    cursor = sms_db.cursor()

    cursor.execute("SELECT ROWID, id FROM handle")
    handles = cursor.fetchall()
    for handle in handles:
        _HANDLENUMBER.update({handle[0]: handle[1]})

    try:
        with open('mobilenumberspeople') as f:
            lines = [line.rstrip('\n') for line in f]
            for line in lines:
                try:
                    key, value = line.split(":")
                    _NUMBERNAME.update({key: value})
                except ValueError:
                    pass
    except IOError:
        pass

    cursor.execute("SELECT ROWID, handle_id, is_from_me, date, text FROM message")
    messages_data = cursor.fetchall()
    for m in messages_data:
        try:
            num = _HANDLENUMBER[m[1]]
            name = _NUMBERNAME[num]
        except KeyError:
            name = num
        print name, bool(m[2]), m[4].replace("\n","<|NEWLINE|>")
