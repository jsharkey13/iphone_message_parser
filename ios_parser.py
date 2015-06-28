import datetime
import sys
import sqlite3 as sql
import pickle
import ios_chat


class iOSMessageParse(object):

    _MYNAME = "My Name"
    _MYNUMBER = "+NNNNNNNNNNN"

    def __init__(self, fname, load_pickle=False):
        self._HANDLENUMBER = {0: self._MYNUMBER}
        self._NUMBERNAME = {self._MYNUMBER: self._MYNAME}
        self._UNKNOWNS = []
        #
        self.Texts = None
        #
        self._sqlite_db = None
        self._cursor = None
        #
        if not load_pickle:
            self._sqlite_db = sql.connect(fname)
            self._cursor = self._sqlite_db.cursor()
            # We don't want Apple's default Write-Ahead Log turned on, use SQLite default setting = DELETE.
            # Only needs to be run once per SQLite file, but nothing lost by re-running in case.
            # This may cause problems if file is reuploaded onto phone; but should never happen anyway.
            # This avoids the creation of temporary files, and we don't actually want to write to file:
            try:
                self._cursor.execute("PRAGMA journal_mode = DELETE")
            except sql.DatabaseError:  # If it's not an sqlite file, it may go wrong:
                print "File is not an sms.db database. Is file " + fname + " correct? Abort."
                sys.exit(-1)
            #
            self._verify_file()  # If it was an sqlite file, check it's an sms.db file too
            #
            self._read_handles()
            self._read_numbers_people()
        else:
            self.load_from_pickle(fname)

    def _close(self):
        if self._sqlite_db is not None:
            self._cursor = None
            self._sqlite_db.close()  # Close connection without committing; don't save changes

    def __del__(self):
        self._close()
    
    def _verify_file(self):
        # Verify that we're parsing an sms.db file:
        _correct_tables = 0
        self._cursor.execute("SELECT * FROM sqlite_master WHERE name='handle' AND type='table'")
        _correct_tables += len(self._cursor.fetchall()) # Must have 'handle' table (add 1 if does, 0 if not)
        self._cursor.execute("SELECT * FROM sqlite_master WHERE name='message' AND type='table'")
        _correct_tables += len(self._cursor.fetchall()) # And 'message' table (add 1 if does, 0 if not) 
        if _correct_tables != 2:
            print "The database does not contain a handle table and a message table. Fatal Error: Abort."
            sys.exit(-1)

    def _read_handles(self):
        if self._cursor is None:
            print "Cannot read handles from database; was data loaded from a pickle file?"
            return
        self._cursor.execute("SELECT ROWID, id FROM handle")
        handles = self._cursor.fetchall()
        for handle in handles:
            self._HANDLENUMBER.update({handle[0]: handle[1]})

    def _read_numbers_people(self):
        try:
            with open('mobilenumbers_people') as f:
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
            self._UNKNOWNS.append(num)
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

    def print_unknowns(self):
        if self.Texts is None:
            print "The database file has not been parsed. Run parse_messages()."
            return
        if len(self._UNKNOWNS) == 0:
            return
        self._UNKNOWNS = list(set(self._UNKNOWNS))  # An unordered duplicate removal method
        print "After identifying any of these accounts, add '[mobilenumber]:[name]' to 'mobilenumbers_people'"
        print "Email addresses for iMessage contacts may appear, as may company names: treat these as mobile numbers."
        for uid in self._UNKNOWNS:
            print uid

    def parse_messages(self):
        if self._sqlite_db is None:
            print "No database open. Was data loaded from a pickle file?"
            return
        # Get all the messages, sorted by handle_id to group conversations together:
        self._cursor.execute("SELECT ROWID, handle_id, is_from_me, date, text FROM message ORDER BY handle_id")
        messages_data = self._cursor.fetchall()
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
            # If message continuation of thread, add to list (or if very first message and None):
            if ((thread_name == _previous_thread_name) or (_previous_thread_name is None)):
                _thread_list.append(ios_chat.Message(thread_name, message_author, message_date, message_body, message_num))
            else:  # If first message of new thread:
                if _previous_thread_name not in _thread_names:  # And the old one not duplicate thread:
                    _thread_names.add(_previous_thread_name)
                    _chat_list.append(ios_chat.Thread(_previous_thread_name, _thread_list))
                else:  # But if the old one is a duplicate thread:
                    for thread in _chat_list:
                        if thread.people_str == _previous_thread_name:
                            thread._add_messages(_thread_list)
                            break
                # And then start new list with current message:
                _thread_list = [ios_chat.Message(thread_name, message_author, message_date, message_body, message_num)]
            # Before finishing loop, update previous name:
            _previous_thread_name = thread_name
        #
        _chat_list.append(ios_chat.Thread(thread_name, _thread_list))
        self.Texts = ios_chat.Chat(self._MYNAME, _chat_list)

    def write_to_csv(self, filename='sms.csv', chronological=False):
        with open(filename, "w") as f:
            header_line = '"Thread","Message Number","Message Author","Message Timestamp","Message Body"\n'
            f.write(header_line.encode('utf8'))
            if chronological:
                for message in self.Texts.all_messages():
                    text = str(message)
                    f.write(text.encode('utf8'))
            else:
                for thread in self.Texts.threads:
                    for message in thread.messages:
                        text = str(message)
                        f.write(text.encode('utf8'))

    def dump_to_pickle(self, filename='sms.pickle'):
        with open(filename, "w") as f:
            pickle.dump(self.Texts, f)

    def load_from_pickle(self, filename='sms.pickle'):
        with open(filename, "r") as f:
            self.Texts = pickle.load(f)
        return self.Texts
