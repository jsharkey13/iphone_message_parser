import sys
import os
import codecs

import ios_parser


# Nasty hack to force utf-8 encoding by default:
reload(sys)
sys.setdefaultencoding('utf8')

# Change stdout to allow printing of unicode characters:
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

if __name__ == "__main__":
    """Allow the parser to be run from the command line.

       Optionally, the function allows specifying the filename to read in from
       as the first argument."""
    if len(sys.argv) >= 2:
        # If filname passed in and a recognised format, continue:
        if ((".db" in sys.argv[1]) or (".sqlite" in sys.argv[1]) or (".pickle" in sys.argv[1])):
            fname = sys.argv[1]
        else:
            # If not a recognised format, stop but allow override:
            print "File is not a .db file, a .sqlite file or a pickle file."
            print "Later code will verify the file is an sms.db file, and will terminate anyway if not."
            cont = raw_input("Continue now? (y/n)")
            if cont == "n":
                sys.exit(-1)
    else:
        # If no argument, attempt to open the default sms.db file:
        fname = "sms.db"
    if not os.path.isfile(fname):
        print "File " + fname + " does not exist or could not be found! Abort."
        sys.exit(-1)

    # Some example code to add functionality immediately.

    # Create the parser, and parse the messages file:
    if ".pickle" in fname:
        SMS = ios_parser.iOSMessageParse(fname, load_pickle=True)
    else:
        SMS = ios_parser.iOSMessageParse(fname)
        SMS.parse_messages()
    print SMS.Texts
