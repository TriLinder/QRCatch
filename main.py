from flask import Flask, render_template, request, redirect, send_file
from io import BytesIO
import base64
import qrcode
import shelve
import logging
import random
import uuid
import time

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

abc = "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z"
abc = abc + "," + abc.upper() + ",0,1,2,3,4,5,6,7,8,9"
abc = abc.split(",")

lastKnownState = {} #Game state cache

def updateLastKnownState(gameID, state) : #Update the cache
    global lastKnownState

    lastKnownState[gameID] = {"state": state, "lastUpdate": time.time(), "updateID": uuid.uuid4().hex[:16]}

def register(username) :
    id = ""

    for i in range(6) : #Generate random player id
        id = id + random.choice(abc)
    
    with shelve.open("players") as s :
        s[id] = {"username": username, "id": id, "games": []}
    
    return id

def newGame() :
    id = ""

    for i in range(6) : #Generate random game id
        id = id + random.choice(abc)
    
    game = {"created": time.time(), "players": {}, "id": id}

    with shelve.open("games") as s :
        s[id] = game
        updateLastKnownState(id, game)
    
    return id

def base64QR(data) :
    qr = qrcode.make(data)

    buffered = BytesIO()
    qr.save(buffered, format="JPEG", quality=100)

    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

def joinGame(player, gameID) :

    with shelve.open("games") as s :
        try :
            game = s[gameID]
        except KeyError :
            return "Invalid game."

        gamePlayer = {"username": player["username"], "id": player["id"], "kills":[], "deaths":[]}

        if player["id"] in game["players"] :
            return "You can not join the same game twice."

        game["players"][player["id"]] = gamePlayer

        s[gameID] = game
        updateLastKnownState(gameID, game)
    
    with shelve.open("players") as s :
        playerInfo = s[player["id"]]

        playerGames = playerInfo["games"]
        playerGames.append(gameID)

        playerInfo["games"] = playerGames

        s[player["id"]] = playerInfo

    return "Game joined."

def killPlayer(killer, killed) :
    print("Kill!")

    g = shelve.open("games")
    p = shelve.open("players")

    pKiller = p[killer]
    pKilled = p[killed]

    gamesKiller = pKiller["games"]
    gamesKilled = pKilled["games"]

    matches = list(set(gamesKiller) & set(gamesKilled))
    
    if len(matches) == 0 :
        return "You aren't sharing any games with this player."

    for gameID in matches :
        game = g[gameID]
        players = game["players"]

        players[killer]["kills"].append(killed)
        players[killed]["deaths"].append(killer)

        game["players"] = players
        g[gameID] = game
        updateLastKnownState(gameID, game)
    
    return "Player killed."

#---------------------------------------#

@app.get("/") 
def indexPage() :
    return render_template("index.html")

@app.get("/new-game")
def newGamePage() :
    id = newGame()

    return redirect(f"/game/{id}")

@app.get("/game/<id>/")
def gameIndexPage(id) :
    if not len(id) == 6 :
        return "Invalid ID lenght."

    qr = base64QR(f"game-{id}")

    return render_template("gameIndex.html", id=id, qr=qr)

@app.get("/game/<id>/leaderboard")
def gameLeaderboardPage(id) :
    with shelve.open("games") as s :

        try :
            game = s[id]
        except KeyError :
            return redirect("/")
    
    players = game["players"]
    
    html = ""

    for player in players :
        username = players[player]["username"]

        kills = len(players[player]["kills"])
        deaths = len(players[player]["deaths"])

        score = round(kills - (deaths/2))

        html = html + f"<tr> <td>{username}</td> <td>{kills}</td> <td>{deaths}</td> <td>{score}</td> </tr>"

    if len(players) == 0 :
        html = "<tr> <td>EMPTY</td> <td>0</td> <td>0</td> <td>0</td> </tr>"

    return render_template("gameLeaderboard.html", html=html, id=id, state=str(game), updateID=getLastKnownStateID(id))

@app.get("/game/<id>/state")
def gameState(id) :
    with shelve.open("games") as s :
        game = s[id]
    
    updateLastKnownState(id, game)
    
    return str(game)

@app.get("/game/<id>/lastKnownState") #Avoid disk usage
def getLastKnownState(id) :
    global lastKnownState
    
    try :
        game = lastKnownState[id]["state"]
    except :
        print("Loading game state from disk")

        game = gameState(id)
    
    return str(game)

@app.get("/game/<id>/lastKnownStateID") #Changes on every cache update
def getLastKnownStateID(id) :
    global lastKnownState
    
    try :
        updateID = lastKnownState[id]["updateID"]
    except :
        print("Loading game state from disk")

        gameState(id)
        return getLastKnownStateID(id)
    
    return str(updateID)


@app.get("/player/<playerID>") #Player scan
def playerScanHandler(playerID) :
    args = request.args
    
    try :
        content = args["content"]
    except KeyError :
        return "Invalid request", 400

    with shelve.open("players") as s :
        if not playerID in s :
            print("Invalid player ID")
            return "Invalid player ID", 400
        
        player = s[playerID]
    
    if not "-" in content :
        return "Invalid QR Code", 400

    type = content.split("-")[0]
    id = content.split("-")[1]

    if type == "game" :
        return joinGame(player, id), 200
    elif type == "player" :
        if id == playerID :
            return "You can not hit yourself.", 200
        
        return killPlayer(playerID, id)

    return "Invalid QR Code", 400

@app.get("/new") #New player
def newPlayerPage() :
    return render_template("newPlayer.html")

@app.post("/new")
def newPlayerHandler() :
    username = request.form["username"].strip()

    if not len(username) in range(1, 17) :
        return render_template("newPlayer.html", error="Username cannot be empty or longer than 16 characters.")

    for char in username :
        if not char in abc :
            if char == " " :
                return render_template("newPlayer.html", error=f"Your username cannot contain a space.")
            else :
                return render_template("newPlayer.html", error=f"Character '{char}' not allowed.")

    id = register(username)

    qr = base64QR(f"player-{id}")

    return render_template("registered.html", id=id, qr=qr)

@app.get("/favicon.ico")
def favicon() :
    try :
        return send_file("favicon.ico")
    except :
        return "favicon.ico was not found", 400

if __name__ == "__main__" :
    app.run(threaded=True, host="0.0.0.0", port=5000, debug=False)