#!/usr/bin/python

"""fanduel.com API provider."""

import sys
import getopt
import getpass
from grab import Grab

LOGIN_PAGE = 'https://www.fanduel.com/p/login'

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

class CmdOptions:
    def __init__(self):
        self.login = None;
        self.password = None;


def parseOptions(argv):
    if argv is None:
        argv = sys.argv
    try:
        cmdOpt = CmdOptions()
        #parse options
        try:
            opts, args = getopt.getopt(argv[1:], "h", ["help"])
        except getopt.error, msg:
            raise Usage(msg)
        # process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print __doc__
                return 0,None
            elif o in ("-u", "--user"):
                cmdOpt.login = a
            elif o in ("-p", "--password"):
                cmdOpt.password = getpass.getpass()
        # process arguments
        for arg in args:
            process(arg) # process() is defined elsewhere
    except Usage, err:
        print >>sys.stderr, err.msg
        print >>sys.stderr, "for help use --help"
        return 2,None

    return 0,cmdOpt

class FanduelApiProvider:
    def __init__(self):
        self.grab = None
    def auth(login, password)

def main(argv=None):
    ret, cmdOptions = parseOptions(argv)
    if cmdOptions is None:
        return ret




if __name__ == "__main__":
    sys.exit(main())