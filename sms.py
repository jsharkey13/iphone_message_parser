import sys
import codecs

import datetime
import sqlite3 as sql

import ios_chat


# Nasty hack to force utf-8 encoding by default:
reload(sys)
sys.setdefaultencoding('utf8')

# Change stdout to allow printing of unicode characters:
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

_MYNAME = "My Name"
_MYNUMBER = "+NNNNNNNNNNN"

_HANDLENUMBER = {}
_NUMBERNAME = {_MYNUMBER: _MYNAME}


def _read_handles(cursor):
    cursor.execute("SELECT ROWID, id FROM handle")
    handles = cursor.fetchall()
    for handle in handles:
        _HANDLENUMBER.update({handle[0]: handle[1]})

def _read_numbers_people():
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

def _parse_message_num(num):
    return int(num)
    
def _parse_message_handle(handle):
    try:
        num = _HANDLENUMBER[handle]
    except KeyError, error:
        if int(error[0]) == 0: # If the missing handle is 0, simply _MYNUMBER:
            # {0: _MYNUMBER} not added to _HANDLENUMBER, fix this:
            _HANDLENUMBER.update({0: _MYNUMBER})
            num = _MYNUMBER
        else:
            print "Message sent to/from non-existent handle: is database corrupt? Abort."
            sys.exit(-1)
    try:
        name = _NUMBERNAME[num]
    except KeyError:
        name = num
    return name

def _parse_message_author(name, is_from_me):
    is_from_me = bool(is_from_me)
    if is_from_me:
        author = _MYNAME
    else:
        author = name
    return author

def _parse_message_date(mac_time):
    unix_time = int(mac_time) + 978307200
    date = datetime.datetime.fromtimestamp(unix_time)
    return date

def _parse_message_body(message_body):
    if message_body is None:
        message_body = ""
    message_body = '<|NEWLINE|>'.join(message_body.splitlines())  # We can't have newline characters in a csv file
    message_body = message_body.replace('"', '""')  # Attempt to escape " characters in messages, for csv output
    return message_body
    
with sql.connect('sms.db') as sms_db:
    cursor = sms_db.cursor()

    _read_handles(cursor)

    _read_numbers_people()

    cursor.execute("SELECT ROWID, handle_id, is_from_me, date, text FROM message ORDER BY handle_id")
    messages_data = cursor.fetchall()
    #
    _chat_list = []
    _thread_list = []
    _previous_thread_name = None    
    #
    for m in messages_data:
        message_num = _parse_message_num(m[0])
        thread_name = _parse_message_handle(m[1])
        message_author = _parse_message_author(thread_name, m[2])
        message_date = _parse_message_date(m[3])
        message_body = _parse_message_body(m[4])
        #
        if thread_name == _previous_thread_name:
            _thread_list.append(ios_chat.Message(thread_name, message_author, message_date, message_body, message_num))
        else:
            _chat_list.append(ios_chat.Thread(_previous_thread_name, _thread_list))
            _thread_list = [ios_chat.Message(thread_name, message_author, message_date, message_body, message_num)]
        _previous_thread_name = thread_name
    #
    _chat_list.append(ios_chat.Thread(thread_name, _thread_list))
    Texts = ios_chat.Chat(_MYNAME, _chat_list)
