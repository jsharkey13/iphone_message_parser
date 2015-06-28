import datetime
import sys
import sqlite3 as sql
import pickle
import ios_chat


class iOSMessageParse(object):
    """An object to encapsulate all the methods required to parse the iOS6 sms.db.

       These include methods to initialise, save and load a ios_chat.Chat object,
       which contains a Pythonic representation of iPhone message history.
        - Can read in messages from the sms.db sqlite database.
        - Can dump the Chat object to a pickle file and load it again in another
          session: use dump_to_pickle() and load_from_pickle().
        - Can export messages to csv format: use write_to_csv()
        - Using a 'mobilenumbers_people' file, can turn unrecognised +NNNNNNNNNNN
          phone numbers into names. Lines should be '[mobile_number]:[name]'.
          See the print_unknowns() function."""

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
        """Close any open database and cursor before deletion. Do not call manually."""
        if self._sqlite_db is not None:
            self._cursor = None
            self._sqlite_db.close()  # Close connection without committing; don't save changes

    def __del__(self):
        """Ensure _close() is called on deletion."""
        self._close()

    def _verify_file(self):
        """Verify the file loaded is an sms.db file.

           It must contain a 'handle' table and a 'message' table; if these are
           not both present; the file might be an sqlite databse, but is not the
           iOS6 sms.db file. Will abort whole program execution if fails!"""
        _correct_tables = 0
        self._cursor.execute("SELECT * FROM sqlite_master WHERE name='handle' AND type='table'")
        _correct_tables += len(self._cursor.fetchall()) # Must have 'handle' table (add 1 if does, 0 if not)
        self._cursor.execute("SELECT * FROM sqlite_master WHERE name='message' AND type='table'")
        _correct_tables += len(self._cursor.fetchall()) # And 'message' table (add 1 if does, 0 if not)
        if _correct_tables != 2:
            print "The database does not contain a handle table and a message table. Fatal Error: Abort."
            sys.exit(-1)

    def _read_handles(self):
        """Read in the 'handle' table and add line entries to dictionaries.

           Called automatically; do not call manually. Read in the 'handle'
           table from the database and add line entries to the dictionaries used
           to translate between iOS contact handle and Name, and vice versa."""
        if self._cursor is None:
            print "Cannot read handles from database; was data loaded from a pickle file?"
            return
        self._cursor.execute("SELECT ROWID, id FROM handle")
        handles = self._cursor.fetchall()
        for handle in handles:
            self._HANDLENUMBER.update({handle[0]: handle[1]})

    def _read_numbers_people(self):
        """Read in the 'mobilenumbers_people' file and add line entries to dictionaries.

           Called automatically; do not call manually. Read in the 'mobilenumbers_people'
           file and add line entries to the dictionaries used to translate between
           phone number and Name, and vice versa.
            - Lines should be formatted '[mobile_number]:[name]'.
            - Ill-formatted lines are ignored, and the file does not have to be present
              for the code to function: unrecognised numbers are left unchanged."""
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
        """Turn string form of message number into an integer."""
        return int(num)

    def _parse_message_handle(self, handle):
        """Tidy up the name of the sender of a message.

           The message handle is turned into a mobile number using the _HANDLENUMBER
           dictionary. If the number is recognised, use the _NUMBERNAME dictionary
           to replace this with a name if possible. Any numbers which remain unchanged
           are added to a list to facilitate populating a 'mobilenumbers_people'
           file: see print_unknowns()."""
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
        """Return the name of message author, given a boolean is_from_me."""
        is_from_me = bool(is_from_me)
        if is_from_me:
            author = self._MYNAME
        else:
            author = name
        return author

    def _parse_message_date(self, mac_time):
        """Turn the datestamp on the message into a datetime object.

           The datestamp is stored in Mac Time; add 978307200 seconds to make
           it into UNIX time and then convert UNIX time into a datetime.datetime
           object."""
        unix_time = int(mac_time) + 978307200
        date = datetime.datetime.fromtimestamp(unix_time)
        return date

    def _parse_message_body(self, message_body):
        """Tidy up the message body itself.

           This turns newline characters into a unique custom string which can
           be replaced after export if necessary. Quote marks are also escaped,
           to allow the use of quotes and commas in messages whilst allowing
           export to csv. Those two lines can be removed if desired."""
        if message_body is None:
            message_body = ""
        message_body = '<|NEWLINE|>'.join(message_body.splitlines())  # We can't have newline characters in a csv file
        message_body = message_body.replace('"', '""')  # Attempt to escape " characters in messages, for csv output
        return message_body

    def print_unknowns(self):
        """Print out any mobile numbers not recognised by the code.

           Prints lines containing unrecognised numbers, along with instructions on
           how to add the names to the 'mobilenumbers_people' file."""
        if self.Texts is None:
            print "The database file has not been parsed. Run parse_messages()."
            return
        if len(self._UNKNOWNS) == 0:
            return
        self._UNKNOWNS = list(set(self._UNKNOWNS))  # An unordered duplicate removal method
        print "After identifying any of these accounts, add '[mobile_number]:[name]' to a file in the current directory named 'mobilenumbers_people'"
        print "Email addresses for iMessage contacts may appear, as may company names: treat these as mobile numbers."
        for uid in self._UNKNOWNS:
            print uid

    def parse_messages(self):
        """Take the loaded database and create a Chat object.

           Takes the sms.db file and reads in the messages using SQLite. Creates
           the Chat object, which can be used independently and accessed as the
           iOSMessageParse.Texts object."""
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
        """Export all messages to csv format.

           The filename can be specified as an optional argument. If 'chronological'
           is True, messages are printed in date order, otherwise they are printed
           grouped in Threads sorted by total thread length."""
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
        """Serialise the Chat object to a pickle file.

           The pickle file can be used to restore the Chat object in another
           session without re-importing the zip or htm file. Load either using
           load_from_pickle(), or in another program using Pickle's standard load()
           command."""
        with open(filename, "w") as f:
            pickle.dump(self.Texts, f)

    def load_from_pickle(self, filename='sms.pickle'):
        """Read in the pickle file, optionally from a specified filename.

           The function sets the internal Chat object and returns the Chat object.
           Provided mainly as an example, since the parser's main aim is to read
           in from the sms.db file, and to output csv or the Chat object."""
        with open(filename, "r") as f:
            self.Texts = pickle.load(f)
        return self.Texts
