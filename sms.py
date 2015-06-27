import sys
import codecs

import ios_parser


# Nasty hack to force utf-8 encoding by default:
reload(sys)
sys.setdefaultencoding('utf8')

# Change stdout to allow printing of unicode characters:
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

if __name__ == "__main__":
    SMS = ios_parser.iOSMessageParse()
    SMS.parse_messages()
    print SMS.Texts
