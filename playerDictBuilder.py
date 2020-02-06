import json
import time
import argparse
from riotwatcher import RiotWatcher, ApiError
from os import listdir
from os.path import isfile
import re

def playerDictBuilder(apiKey, region, maxPlayers=10000, accountId=''):
    #setup watcher and default values
    watcher = RiotWatcher(apiKey)
    myRegion = region
    maxPlayerNumber = maxPlayers
    startingAccountId = accountId
    playerDict = {}
    gameIds = []
    unusedAccountPlayers = []
    usedAccountPlayers = []
    
    
    #get the latest saved data
    onlyfiles = [f for f in listdir() if isfile(f)]
    times = {}
    latest = 0
    for i in onlyfiles:
        if re.match(r''+myRegion+'', i):
            times[time.strptime(i[len(myRegion)+1:],"%Y%m%d-%H%M%S")] = i
            if not latest:
                latest = time.strptime(i[len(myRegion)+1:],"%Y%m%d-%H%M%S")
    for i in times:
        if i > latest:
            latest = i
    
    #if a saved dataset exists for this region key, load it
    #otherwise use the passed accountId to begin a new dict
    if latest:
        with open(times[latest], 'r') as fp:
            data = json.load(fp)
        
        playerDict = data['playerDict']
        gameIds = data['gameIds']
        unusedAccountPlayers = data['unusedAccountPlayers']
        usedAccountPlayers = data['usedAccountPlayers']
        print('loaded from saved dataset')
        print(repr(len(playerDict)) + ' players loaded')
    else:
        if accountId:
            unusedAccountPlayers.append(startingAccountId)
        else:
            print("No dataset found, enter an accountId")
            exit()
    
    
    #
    #build the dictionary
    #
    while len(playerDict) < maxPlayerNumber:
        playerSummonerList = []
        playerDictLength = len(playerDict)
        
        #get the next unused player account id
        playerId = unusedAccountPlayers.pop(0)
        if playerId in usedAccountPlayers:
            continue
        
        
        #get ranked matches player has been in
        print('getting matches for player - ' + playerId)
        while True:
            try:
                matchList = watcher.match.matchlist_by_account(myRegion, playerId, 420)
            except ApiError as err:
                if err.response.status_code == 429:
                    print('ERROR 429 - Rate limit exceeded')
                    print('    We should retry in {} seconds.'.format(err.response.headers['Retry-After']))
                    continue
                else:
                    raise
            break
        
        
        #only keep matches that aren't repeats globally and have been played this season
        gamesFound = []
        for match in matchList['matches']:
            if match['gameId'] in gameIds or not match['season'] == 13:
                continue
            gameIds.append(match['gameId'])
            gamesFound.append(match['gameId'])
        print('found ' + repr(len(gamesFound)) + ' games')
        
        
        #search all new matches for player ids (summoner and account)
        #add new player ids to list of ids and unused list
        playersAdded = 0
        for game in gamesFound:
            while True:
                try:
                    currentMatch = watcher.match.by_id(myRegion, game)
                except ApiError as err:
                    if err.response.status_code == 429:
                        print('ERROR 429 - Rate limit exceeded')
                        print('    We should retry in {} seconds.'.format(err.response.headers['Retry-After']))
                        continue
                    else:
                        raise
                break
            
            #get new players from the matchlist
            for participant in currentMatch['participantIdentities']:
                if participant['player']['summonerId'] in playerDict or participant['player']['summonerId'] in playerSummonerList:
                    continue
                playerSummonerList.append(participant['player']['summonerId'])
                unusedAccountPlayers.append(participant['player']['accountId'])
                playersAdded += 1
                
            print('    players to be added: ' + repr(playersAdded), end='\r')
        print('    players to be added: ' + repr(playersAdded))
        
        
        #get the rank and tier of the new players then add them to dict
        for player in playerSummonerList:
            while True:
                try:
                    currentPlayer = watcher.league.by_summoner(myRegion, player)
                except ApiError as err:
                    if err.response.status_code == 429:
                        print('ERROR 429 - Rate limit exceeded')
                        print('    We should retry in {} seconds.'.format(err.response.headers['Retry-After']))
                        continue
                    else:
                        raise
                break
            for i in currentPlayer:
                if i['queueType'] == 'RANKED_SOLO_5x5':
                    playerDict[player] = [i['tier'], i['rank']]
        print('added ' + repr(len(playerDict) - playerDictLength) + ' new players to dictionary')
        usedAccountPlayers.append(playerId)
        
        
        #save data to prevent loss
        saveData = {}
        saveData['region'] = myRegion
        saveData['playerDict'] = playerDict
        saveData['gameIds'] = gameIds
        saveData['unusedAccountPlayers'] = unusedAccountPlayers
        saveData['usedAccountPlayers'] = usedAccountPlayers
        
        #create a filename from current timestamp to prevent overwriting
        filename = myRegion + '-' + time.strftime("%Y%m%d-%H%M%S")
        with open(filename, 'w') as fp:
            json.dump(saveData, fp, indent=4)
            print('saved to ' + filename + '.json')
            print(repr(len(playerDict)) + ' total players in dictionary')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build a dictionary of players.')
    parser.add_argument('apiKey', type=str, help='the api key')
    parser.add_argument('region', type=str, help='the region key, eg. kr, oc1')
    parser.add_argument('--maxPlayers', type=int, help='max number of players to add to the dictionary, default 10000')
    parser.add_argument('--accountId', type=str, help='accountId used to start an empty dictionary')
    args = parser.parse_args()
    
    if args.maxPlayers and args.accountId:
        playerDictBuilder(args.apiKey, args.region, args.maxPlayers, args.accountId)
    elif args.maxPlayers:
        playerDictBuilder(args.apiKey, args.region, args.maxPlayers)
    else:
        playerDictBuilder(args.apiKey, args.region)
