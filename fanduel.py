#!/usr/bin/python

"""fanduel.com API provider."""

import sys
import optparse
import getpass
from grab import Grab
from grab.tools.logs import default_logging

LOGIN_PAGE = 'https://www.fanduel.com/login'

def parseOptions(argv):
    usage = "usage: %prog [options] arg"
    parser = optparse.OptionParser(usage)
    parser.add_option("-u", "--username", 
                        help="login to access to fanduel.com, " \
                        "password will requested from stdin")
    (options, args) = parser.parse_args(argv)
    if options.username:
        options.password = getpass.getpass()
    #if some error in command line:
    #    parser.error("incorrect number of arguments")
    return options

class FanduelApiProvider:
    def __init__(self):
        self.grab = Grab(log_dir='/tmp/fanduel')
    def auth(self, login, password):
        self.grab.go(LOGIN_PAGE)
        self.grab.set_input('email', login)
        self.grab.set_input('password', password)
        self.grab.submit()
        return self.grab.response.code

def main(argv=None):
    cmdOps = parseOptions(argv)
    default_logging()

    api = FanduelApiProvider();
    print api.auth(cmdOps.username, cmdOps.password)

    return 0


if __name__ == "__main__":
    sys.exit(main())