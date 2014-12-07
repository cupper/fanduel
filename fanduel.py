#!/usr/bin/python

"""fanduel.com API provider."""

import sys
import optparse
import getpass
import re
import os
import json
import StringIO
from grab import Grab
from grab.tools.logs import default_logging
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

MAIN_PAGE = 'https://www.fanduel.com'
LOGIN_PAGE = 'https://www.fanduel.com/login'

# first - gameId
# second - tableId
ENTER_GAME_PAGE = 'https://www.fanduel.com/e/Game/%s?tableId=%s&fromLobby=true'

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
    #if something goes wrong:
    #    parser.error("incorrect number of arguments")
    return options


class Contest:
    def __init__(self, dictOfProperties):
        self.properties = dictOfProperties

    def id(self):       return self.__getBy__('uniqueId')
    def gameId(self):   return self.__getBy__('gameId') 
    def title(self):     return self.__getBy__('title')
    def sport(self):    return self.__getBy__('sport')
    def tableId(self):  return self.__getBy__('tableSpecId')
    def entryFee(self): return int(self.__getBy__('entryFee'))
    def prize(self):    return int(self.__getBy__('prizes'))
    def salary(self):   return int(self.__getBy__('cap'))
    def size(self):     return int(self.__getBy__('size'))
    def entered(self):  
        try:
            return int(self.__getBy__('entriesData'))
        except Exception:
            return int(self.__getBy__('stack'))
    def freeSpace(self): return self.size() - self.entered()

    def __getBy__(self, key):
        if key not in self.properties:
            raise Exception("Property '%s' not available in contest %s" % \
                (key, json.dumps(self.properties, indent=2)))
        return self.properties[key]

    def __str__(self):
        return json.dumps(self.properties, indent=2)


class ContestsProvider:
    def __init__(self, listOfContests):
        self.contests = [c if isinstance(c, Contest) else Contest(c) for c in listOfContests]

    def getNFL(self):
        try:
            return self.nfl
        except AttributeError:
            self.nfl = ContestsProvider(self.__filterBy__('sport', 'nfl'))
            return self.nfl

    def getFreeGames(self):
        try:
            return self.freeGames
        except AttributeError:
            self.freeGames = ContestsProvider(self.__filterBy__('entryFee', 0))
            return self.freeGames

    def __filterBy__(self, key, value):
        filteredContests = []
        for c in self.contests:
            if c.__getBy__(key) == value:
                filteredContests.append(c)
        return filteredContests

    def __len__(self): 
        return len(self.contests)
    def __iter__(self):
        for elem in self.contests:
            yield elem
    def __getitem__(self, key):
        return self.contests[key]


class Player:
    def __init__(self, playerTuple):
        self.id = playerTuple[0]
        self.properties = playerTuple[1]

    def id(self):       return self.id
    def position(self): return self.__safeIndex__(0)
    def name(self):     return self.__safeIndex__(1)
    def fixture(self):  return self.__safeIndex__(2)
    def teamId(self):   return self.__safeIndex__(3)
    def salary(self):   return self.__safeIndex__(5)

    def __safeIndex__(self, index):
        if (index < 0) or (index >= len(self.properties)):
            raise Exception("Index '%d' not available in player %s" % \
                (index, json.dumps(self.properties, indent=2)))
        return self.properties[index]

    def __str__(self):
        return json.dumps(self.properties, indent=2)


class PlayersProvider:
    def __init__(self, listOfTuples):
        self.players = [p if isinstance(p, Player) else Player(p) for p in listOfTuples.items()]

    def dumpSalariesToFile(self, filename = 'salaries.txt'):
        dumpFile = open(filename, 'w')
        if not dumpFile:
            raise Exception("Can not open the file '%s'" % (filename))
        
        duplicates = {}
        for p in self.players:
            dumpFile.write("%s, %s\n" % (p.name(), p.salary()))
            if p.name() in duplicates:
                duplicates[p.name()] += 1
            else:
                duplicates[p.name()] = 1

        if len(duplicates) > 0:
            print "Players with the same names:"
            for name,times in duplicates.iteritems():
                if times > 1:
                    print "\t %s - %d" % (name,times)

    def __len__(self):
        return len(self.players)
    def __iter__(self):
        for elem in self.players:
            yield elem
    def __getitem__(self, key):
        return self.players[key]


class FanduelApiProvider:
    def __init__(self):
        logDir = '/tmp/fanduel'
        if not os.path.exists(logDir):
            os.makedirs(logDir)
        self.grab = Grab(log_dir=logDir)

    def auth(self, email):
        cookiefile = "%s.cookie" % (re.sub('[!@#$.]', '', email))
        if not os.path.isfile(cookiefile):
            open(cookiefile, 'a+').close()
            self.grab.setup(cookiefile=cookiefile)
            print "real authorization"
            password = getpass.getpass()
            self.grab.go(LOGIN_PAGE)
            self.grab.set_input('email', email)
            self.grab.set_input('password', password)
            self.grab.submit()
        else:
            print "use coockie"
            self.grab.setup(cookiefile=cookiefile)
            self.grab.go(MAIN_PAGE)
        return self.grab.response.code

    def getContests(self):
        response = self.grab.response.body;
        rawJsonDataBegin = response.find('LobbyConnection.initialData') + len('LobbyConnection.initialData = ')
        rawJsonDataEnd = response.rfind(';', rawJsonDataBegin, response.find('LobbyConnection.lastUpdate'))
        rawJsonInitData = response[rawJsonDataBegin:rawJsonDataEnd]
        jsonInitData = json.loads(rawJsonInitData)
        return jsonInitData['additions']

    def openContest(self, contest):
        contestUrl = ENTER_GAME_PAGE % (contest.gameId(), contest.tableId())
        #print "enter to %s" % (contestUrl)
        self.grab.go(contestUrl)
        #print "return code [%s]" % (self.grab.response.code)

    def getPlayerData(listOfPlayers):
        jsonPlayers = []
        for p in listOfPlayers:
            jsonPlayer = [p.position(), p.id(), p.fixture(), p.teamId()]
            jsonPlayers.append(json.dumps(jsonPlayer))
        playerData = json.dumps(jsonPlayers)
        return playerData

    def enterContest(self, contest, playerData):
        self.openContest(contest)
        self.grab.set_input('playerData', playerData)
        self.grab.set_input('entryForm-tablespec_id', '')
        self.grab.submit()
        return self.grab.response.code

    def getPlayers(self, contest):
        self.openContest(contest)
        response = self.grab.response.body;
        rawJsonDataBegin = response.find('FD.playerpicker.allPlayersFullData') + len('FD.playerpicker.allPlayersFullData = ')
        rawJsonDataEnd = response.rfind(';', rawJsonDataBegin, response.find('FD.playerpicker.teamIdToFixtureCompactString'))
        rawJsonData = response[rawJsonDataBegin:rawJsonDataEnd]
        tmp = json.loads(rawJsonData)
        return tmp


class FanduelSelenium:
    def __init__(self):
        self.driver = webdriver.Firefox()

    def auth(self, email):
        cookiefile = "%s_.cookie" % (re.sub('[!@#$.]', '', email))
        open(cookiefile, 'a+').close()
        password = getpass.getpass()
        self.driver.get(LOGIN_PAGE)
        loginForm = self.driver.find_element_by_id('ccf0')
        loginForm.find_element_by_id('email').send_keys(email)
        loginForm.find_element_by_id('password').send_keys(password)
        loginForm.submit()
        cookiefile.write(json.dumps((self.driver.get_cookies())))


def main(argv=None):
    cmdOps = parseOptions(argv)
    default_logging()

    api = FanduelApiProvider()
    if not api.auth(cmdOps.email) == 200:
        return 2;
    print "Authorization passed"

    allGames = ContestsProvider(api.getContests())
    print "loaded %d contests" % (len(allGames))

    nflGames = allGames.getNFL()
    print "found %d NFL games" % (len(nflGames))

    #freeNflGames = nflGames.getFreeGames()
    #print "found %d NFL games" % (len(freeNflGames))

    #predef = '[["QB",34308,"86901","12"],["RB",10777,"86901","11"],["RB",6728,"86905","16"],["WR",11505,"86906","13"],["WR",14187,"86783","8"],["WR",27445,"86904","28"],["TE",14394,"86906","13"],["K",6767,"86784","9"],["D",12534,"86784","9"]]'
    #for game in freeNflGames:
    #    if game.freeSpace() > 0:
    #        ret = api.enterContest(game, predef)
    #        print "Enter to '%s' : %d" % (game.title(), ret) 
    #        break

    for c in nflGames:
        players = PlayersProvider(api.getPlayers(c))
        if len(players) == 553:
            players.dumpSalariesToFile()
            break
                     
    return 0


if __name__ == "__main__":
    argv = ["-e", "cupper.jj@gmail.com"]
    sys.exit(main(argv))