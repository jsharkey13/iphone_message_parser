import datetime
import sys
import sqlite3 as sql

import ios_chat

class iOSMessageParse(object):
    _MYNAME = "My Name"
    _MYNUMBER = "+NNNNNNNNNNN"

    _HANDLENUMBER = {}
    _NUMBERNAME = {_MYNUMBER: _MYNAME}


    def __init__(self):
        self.Texts = None

    def _read_handles(self, cursor):
        cursor.execute("SELECT ROWID, id FROM handle")
        handles = cursor.fetchall()
        for handle in handles:
            self._HANDLENUMBER.update({handle[0]: handle[1]})

    def _read_numbers_people(self):
        try:
            with open('mobilenumberspeople') as f:
                lines = [line.rstrip('\n') for line in f]
                for line in lines:
                    try:
                        key, value = line.split(":")
                        self._NUMBERNAME.update({key: value})
                    except ValueError:
                        pass
        except IOError:
            pass

    def _parse_message_num(self, num):
        return int(num)

    def _parse_message_handle(self, handle):
        try:
            num = self._HANDLENUMBER[handle]
        except KeyError, error:
            if int(error[0]) == 0:  # If the missing handle is 0, simply _MYNUMBER:
                # {0: _MYNUMBER} not added to _HANDLENUMBER, fix this:
                self._HANDLENUMBER.update({0: self._MYNUMBER})
                num = self._MYNUMBER
            else:
                print "Message sent to/from non-existent handle: is database corrupt? Abort."
                sys.exit(-1)
        try:
            name = self._NUMBERNAME[num]
        except KeyError:
            name = num
        return name

    def _parse_message_author(self, name, is_from_me):
        is_from_me = bool(is_from_me)
        if is_from_me:
            author = self._MYNAME
        else:
            author = name
        return author

    def _parse_message_date(self, mac_time):
        unix_time = int(mac_time) + 978307200
        date = datetime.datetime.fromtimestamp(unix_time)
        return date

    def _parse_message_body(self, message_body):
        if message_body is None:
            message_body = ""
        message_body = '<|NEWLINE|>'.join(message_body.splitlines())  # We can't have newline characters in a csv file
        message_body = message_body.replace('"', '""')  # Attempt to escape " characters in messages, for csv output
        return message_body

    def parse_messages(self):
        with sql.connect('sms.db') as sms_db:
            cursor = sms_db.cursor()

            self._read_handles(cursor)

            self._read_numbers_people()

            # We don't want Apple's default Write-Ahead Log turned on, use SQLite default setting = DELETE.
            # Only needs to be run once per SQLite file, but nothing lost by re-running in case.
            # This may cause problems if file is reuploaded onto a phone; but should never happen anyway.
            # This avoids the creation of temporary files, and we don't actually want to write to file:
            cursor.execute("PRAGMA journal_mode = DELETE")

            # Get all the messages, sorted by handle_id; groups conversations together:
            cursor.execute("SELECT ROWID, handle_id, is_from_me, date, text FROM message ORDER BY handle_id")
            messages_data = cursor.fetchall()
            #
            _chat_list = []
            _thread_list = []
            _previous_thread_name = None
            #
            _thread_names = set()
            #
            for m in messages_data:
                message_num = self._parse_message_num(m[0])
                thread_name = self._parse_message_handle(m[1])
                message_author = self._parse_message_author(thread_name, m[2])
                message_date = self._parse_message_date(m[3])
                message_body = self._parse_message_body(m[4])
                # If message continuation of thread, add to list (or if first message and None):
                if ((thread_name == _previous_thread_name) or (_previous_thread_name is None)):
                    _thread_list.append(ios_chat.Message(thread_name, message_author, message_date, message_body, message_num))
                else:  # If first message of new thread:
                    if _previous_thread_name not in _thread_names:  # And the old one not duplicate thread:
                        _thread_names.add(_previous_thread_name)
                        _chat_list.append(ios_chat.Thread(_previous_thread_name, _thread_list))
                    else:  # But if the old one is a duplicate thread:
                        for thread in _chat_list:
                            if thread.people == _previous_thread_name:
                                thread._add_messages(_thread_list)
                                break
                    # And then start new list with current message:
                    _thread_list = [ios_chat.Message(thread_name, message_author, message_date, message_body, message_num)]
                # Before finishing loop, update previous name:
                _previous_thread_name = thread_name
            #
            _chat_list.append(ios_chat.Thread(thread_name, _thread_list))
        self.Texts = ios_chat.Chat(self._MYNAME, _chat_list)