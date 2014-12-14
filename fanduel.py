#!/usr/bin/python

"""fanduel.com API provider."""

import sys
import optparse
import getpass
import re
import os
import json
import StringIO
import time
import pickle
import math
from grab import Grab
from grab.tools.logs import default_logging
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

MAIN_PAGE = 'https://www.fanduel.com'
HOME_PAGE = 'https://www.fanduel.com/p/Home'
LOGIN_PAGE = 'https://www.fanduel.com/login'


def getPassword():
    if "counter" not in getPassword.__dict__:
        getPassword.password = getpass.getpass()
    return getPassword.password

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

    def uniqueId(self):       return self.__getBy__('uniqueId')
    def gameId(self):   return self.__getBy__('gameId') 
    def title(self):    return self.__getBy__('title')
    def sport(self):    return self.__getBy__('sport')
    def tableSpecId(self):  return self.__getBy__('tableSpecId')
    def url(self):      return MAIN_PAGE + self.__getBy__('entryURL')
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
    def __init__(self, uniqid, data):
        self.uniqid = uniqid
        self.properties = data

    def id(self):       return self.uniqid
    def position(self): return self.__safeIndex__(0)
    def name(self):     return self.__safeIndex__(1)
    def fixture(self):  return self.__safeIndex__(2)
    def teamId(self):   return self.__safeIndex__(3)
    def salary(self):   return int(self.__safeIndex__(5))

    def diff(self, other):
        buff = StringIO.StringIO()
        if self.id() != other.id():
            buff.write("id: %d vs. %d\n" % (self.id(), other.id()))
        if len(self.properties) != len(other.properties):
            buff.write("lenOfProp: %d vs. %d\n" % (len(self.properties), len(other.properties)))
        minLen = min(len(self.properties), len(other.properties))
        for i in range(0,minLen):
            if self.properties[i] != other.properties[i]:
                buff.write("[%d] %s vs. %s\n" % (i, self.properties[i], other.properties[i]))
        prop = self.properties
        if minLen == len(self.properties):
            prop = other.properties
        for i in range(minLen, len(prop)):
            buff.write("[%d] %s\n" % (i, prop[i]))
        return buff.getvalue()

    def __safeIndex__(self, index):
        if (index < 0) or (index >= len(self.properties)):
            raise Exception("Index '%d' not available in player %s" % \
                (index, json.dumps(self.properties, indent=2)))
        return self.properties[index]

    def __str__(self):
        return json.dumps(self.properties, indent=2)
    def __eq__(self, other):
        return (self.uniqid == other.uniqid) and (set(self.properties) == set(other.properties))
    def __ne__(self, other):
        return not self.__eq__(other)


class PlayersProvider:
    def __init__(self, dictOfPlayers):
        self.players = {}
        for uniqid, data in dictOfPlayers.iteritems():
            player = Player(uniqid, data)
            self.players[player.name()] = player

    def merge(self, playersProvider):
        playersCollision = open('players_collision.txt', 'a')
        foundCollisions = 0
        added = 0
        for name, player in playersProvider.players.iteritems():
            if name not in self.players.keys():
                self.players[name] = player
                added += 1
            elif player != self.players[name]:
                playersCollision.write(name + '\n')
                playersCollision.write(player.diff(self.players[name]) + '\n')
                foundCollisions += 1
        if foundCollisions > 0:
            print "Found collisions %d" % (foundCollisions)
        playersCollision.close()
        return added

    def add(self, player):
        if player.name() in self.players.keys():
            raise Exception("player '%s' already in provider" % (player.name()))
        self.players[player.name()] = player

    def fetchByNames(self, listOfNames, fullMatch = False):
        fetched = PlayersProvider({})
        for name in listOfNames:
            if name in self.players.keys():
                fetched.add(self.players[name])
            elif fullMatch:
                raise Exception("player '%s' not exist in current provider" % (name))
            else:
                print "playes '%s' not exist in provider" % (name)
        return fetched

    def summarizeBySalary(self):
        salary = 0
        for k,p in self.players.iteritems():
            salary += p.salary()
        return salary

    def saveToFile(self, filename = 'players.txt'):
        dumpFile = open(filename, 'w')
        if not dumpFile:
            raise Exception("Can not open the file '%s'" % (filename))
        pickle.Pickler(file=dumpFile).dump(self)
        dumpFile.close()

    def loadFromFile(self, filename = 'players.txt'):
        dumpFile = open(filename, 'r')
        if not dumpFile:
            raise Exception("Can not open the file '%s'" % (filename))
        self = pickle.Unpickler(file=dumpFile).load()
        dumpFile.close()
        return self

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
        default_logging()
        logDir = '/tmp/fanduel'
        if not os.path.exists(logDir):
            os.makedirs(logDir)
        self.grab = Grab(log_dir=logDir, debug_post=True)

    def auth(self, email):
        cookiefile = "%s.cookie" % (re.sub('[!@#$.]', '', email))
        if not os.path.isfile(cookiefile):
            open(cookiefile, 'a+').close()
            self.grab.setup(cookiefile=cookiefile)
            print "real authorization"
            self.grab.go(LOGIN_PAGE)
            self.grab.set_input('email', email)
            self.grab.set_input('password', getPassword())
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
        self.grab.go(contest.url())

    def getPlayerData(listOfPlayers):
        jsonPlayers = []
        for p in listOfPlayers:
            jsonPlayer = [p.position(), p.id(), p.fixture(), p.teamId(), 'false']
            jsonPlayers.append(json.dumps(jsonPlayer))
        playerData = json.dumps(jsonPlayers)
        return playerData

    def getAttr(self, path, attr, selector = None):
        if not selector:
            selector = self.grab.doc
        return selector.select(path).attr(attr)

    def joinContest(self, contest, playerData):
        self.openContest(contest)
        getValue = lambda name: self.grab.doc.select("//form/input[@name='%s']"%(name)).attr('value')
        postReq = {}
        postReq['cc_session_id'] = getValue('cc_session_id')
        postReq['cc_action'] = 'cca_jointable'
        postReq['cc_failure_url'] = getValue('cc_failure_url')
        postReq['game_id'] = getValue('game_id')
        postReq['playerData'] = playerData
        postReq['table_id'] = str(contest.uniqueId())
        postReq['tablespec_id'] = ''
        postReq['is_public'] = getValue('is_public')
        postReq['currencytype'] = getValue('currencytype')
        print json.dumps(postReq, indent=2)
        self.grab.setup(multipart_post=postReq)
        #    {
        #    'cc_session_id':getValue('cc_session_id'),
        #    'cc_action':'cca_jointable',
        #    'cc_failure_url' : getValue('cc_failure_url'),
        #    'game_id' : getValue('game_id'), 'playerData' : playerData, 
        #    'table_id' : str(contest.uniqueId()), 'tablespec_id' : str(contest.tableSpecId()),
        #    'is_public' : '1', 'currencytype' : '1'
        #    })
        self.grab.request()
        print self.grab.doc.select('//head/title').text()
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
        self.driver.get(LOGIN_PAGE)
        loginForm = self.driver.find_element_by_tag_name('form')
        loginForm.find_element_by_id('email').send_keys(email)
        loginForm.find_element_by_id('password').send_keys(getPassword())
        loginForm.submit()
        print self.driver.current_url

    def getContests(self):
        if self.driver.current_url != HOME_PAGE:
            self.driver.get(HOME_PAGE)
        response = self.driver.page_source;
        rawJsonDataBegin = response.find('LobbyConnection.initialData') + len('LobbyConnection.initialData = ')
        rawJsonDataEnd = response.rfind(';', rawJsonDataBegin, response.find('LobbyConnection.lastUpdate'))
        rawJsonInitData = response[rawJsonDataBegin:rawJsonDataEnd]
        jsonInitData = json.loads(rawJsonInitData)
        return jsonInitData['additions']

    def openContest(self, contest):
        if self.driver.current_url != contest.url():
            self.driver.get(contest.url())
        return self.driver.title.count(contest.title()) > 0

    def getPlayers(self, contest):
        if self.driver.current_url != contest.url():
            self.driver.get(contest.url())
        response = self.driver.page_source;
        rawJsonDataBegin = response.find('FD.playerpicker.allPlayersFullData') + len('FD.playerpicker.allPlayersFullData = ')
        rawJsonDataEnd = response.rfind(';', rawJsonDataBegin, response.find('FD.playerpicker.teamIdToFixtureCompactString'))
        rawJsonData = response[rawJsonDataBegin:rawJsonDataEnd]
        return json.loads(rawJsonData)

    def joinContest(self, contest, playersName, allPlayers):
        if self.driver.current_url != contest.url():
            self.driver.get(contest.url())
        for name in playersName:
            playerId = allPlayers[name].id()
            onPlayer = self.driver.find_element(By.XPATH, "//a[@data-player-id='%s']" % (playerId))
            if onPlayer:    
                onPlayer.click()
            else:
                raise Exception("Cant find '%s' with id %s" % (name, playerId))
        self.driver.find_element_by_id('enterButton').click()
        print self.driver.title

    def __del__(self):
        self.driver.quit()

def worker(browser, cmdOps):

    allPlayers = PlayersProvider({}).loadFromFile()
    print "restored %d players from file" % (len(allPlayers))

    browser.auth(cmdOps.email)
    print "authorization passed"

    allGames = ContestsProvider(browser.getContests())
    print "loaded %d contests" % (len(allGames))

    nflGames = allGames.getNFL()
    print "found %d NFL games" % (len(nflGames))

    freeNflGames = nflGames.getFreeGames()
    print "found %d NFL free games" % (len(freeNflGames))

    teamPlayersNames = [
        'Matt Flynn',
        'Trey Watts',
        'DuJuan Harris',
        'Chris Givens',
        'Courtney Roby',
        'Jarrett Boykin',
        'Matthew Mulligan',
        'Chandler Catanzaro',
        'Atlanta Falcons']

    #falseMerge = 0
    #allPlayers = PlayersProvider({})
    #for game in nflGames:
    #    players = PlayersProvider(browser.getPlayers(game))
    #    added = allPlayers.merge(players)
    #    if added == 0:
    #        if falseMerge == 5:
    #            break
    #        falseMerge += 1
    #    print "Added %d playes, total %d" % (added, len(allPlayers))
    #allPlayers.saveToFile()


    for game in freeNflGames:
        if game.freeSpace() > 0:
            print "open game '%s'" % (game.title())
            if not browser.openContest(game):
                print "could not open the game"
            players = PlayersProvider(browser.getPlayers(game))
            team = players.fetchByNames(teamPlayersNames)
            if len(team) != 9:
                print "could not create full team"
                break 
            print "Salary of team %d$ and game provide %d$" % (team.summarizeBySalary(), game.salary())
            if team.summarizeBySalary() <= game.salary():
                print "Enter to game '%s'" % (game.url())
                ret = browser.joinContest(game, teamPlayersNames, players)
            else:
                print "Can't enter to game '%s' team salary > game provide" % (game.title())
            break

    #for c in nflGames:
    #    players = PlayersProvider(api.getPlayers(c))
    #    if len(players) == 553:
    #        players.dumpSalariesToFile()
    #        break


def main(argv=None):
    cmdOps = parseOptions(argv)

    #browser = FanduelApiProvider()
    browser = FanduelSelenium()

    worker(browser, cmdOps)
                     
    return 0


if __name__ == "__main__":
    argv = ["-e", "cupper.jj@gmail.com"]
    sys.exit(main(argv))