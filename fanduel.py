#!/usr/bin/python

"""fanduel.com API provider."""

import sys
import optparse
import getpass
import re
import os
from grab import Grab
from grab.tools.logs import default_logging

MAIN_PAGE = 'https://www.fanduel.com'
LOGIN_PAGE = 'https://www.fanduel.com/login'

# <form action='https://www.fanduel.com/c/CCEntry' id='enterForm'>

"""
FD.playerpicker.allPlayersFullData = {
    "29358":["QB","Marcus Mariota","95320","2714","1000","11300",37.9,"3",false,4,"","recent",""],
    "33128":[
        "QB"
        "Shane Carden"
        "86352" - data-fixture
        "2744" - team ID
        "1000","10000",20.3,"3",false,4,"","recent",""],

[["QB",29358,"95320","2714"],["RB",41911,"86353","2743"],["RB",43886,"95319","5723"],["WR",0],["WR",0],["WR",0],["TE",0]]
<input type='text' id='playerData'
"""

def parseOptions(argv):
    usage = "usage: %prog [options] arg"
    parser = optparse.OptionParser(usage)
    parser.add_option("-e", "--email", 
                        help="email to access to fanduel.com, " \
                        "password will requested from stdin")
    (options, args) = parser.parse_args(argv)
    options.password = None
    if options.email:
        options.password = getpass.getpass()

    #if some error in command line:
    #    parser.error("incorrect number of arguments")
    return options

class FanduelApiProvider:
    def __init__(self):
        logDir = '/tmp/fanduel'
        if not os.path.exists(logDir):
            os.makedirs(logDir)
        self.grab = Grab(log_dir=logDir)

    def auth(self, email, password):
        cookiefile = "%s.coockie" % (re.sub('[!@#$.]', '', email))
        open(cookiefile, 'a+').close()
        self.grab.setup(cookiefile=cookiefile)
        if not os.path.isfile(cookiefile):
            print "real authorization"
            self.grab.go(LOGIN_PAGE)
            self.grab.set_input('email', email)
            self.grab.set_input('password', password)
            self.grab.submit()
        else:
            print "use coockie"
            self.grab.go(MAIN_PAGE)
        return self.grab.response.code

    def getContests(self):
        print self.grab.response.body[0:100]       

def main(argv=None):
    cmdOps = parseOptions(argv)
    default_logging()

    api = FanduelApiProvider()
    if not api.auth(cmdOps.email, cmdOps.password) == 200:
        return 2;
    print "Authorization passed"

    api.getContests()

    return 0


if __name__ == "__main__":
    sys.exit(main())