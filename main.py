from ast import arg
from re import T
import re
from flask import Flask, render_template, request, send_file, redirect
from io import BytesIO
import base64
import qrcode
import shelve
import logging
import random
import time
import os

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

abc = "a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z"
abc = abc + "," + abc.upper()
abc = abc.split(",")

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
    
    with shelve.open("games") as s :
        s[id] = {"created": time.time(), "players": {}, "id": id}
    
    return id

def base64QR(data) :
    qr = qrcode.make(data)

    buffered = BytesIO()
    qr.save(buffered, format="JPEG")

    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

def joinGame(player, gameID) :
    with shelve.open("games") as s :
        game = s[gameID]

        gamePlayer = {"username": player["username"], "id": player["id"], "kills":[], "deaths":[]}

        if player["id"] in game["players"] :
            return "You can not join the same game twice."

        game["players"][player["id"]] = gamePlayer

        s[gameID] = game
    
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
    
    for gameID in matches :
        game = g[gameID]
        players = game["players"]

        players[killer]["kills"].append(killed)
        players[killed]["deaths"].append(killer)

        game["players"] = players
        g[gameID] = game

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
    qr = base64QR(f"game-{id}")

    return render_template("gameIndex.html", id=id, qr=qr)

@app.get("/game/<id>/leaderboard")
def gameLeaderboardPage(id) :
    with shelve.open("games") as s :
        game = s[id]
    
    players = game["players"]
    
    html = ""

    for player in players :
        username = players[player]["username"]

        kills = len(players[player]["kills"])
        deaths = len(players[player]["deaths"])

        score = round(kills - (deaths/2))

        html = html + f"<tr> <td>{username}</td> <td>{kills}</td> <td>{deaths}</td> <td>{score}</td> </tr>"

    return render_template("gameLeaderboard.html", html=html, id=id)

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
        
        killPlayer(playerID, id)
        return "Player killed."

    return "Invalid code", 400

@app.get("/new") #New player
def newPlayerPage() :
    return render_template("newPlayer.html")

@app.post("/new")
def newPlayerHandler() :
    username = request.form["username"].strip()

    if not len(username) in range(1, 17) :
        return render_template("newPlayer.html", error="Username cannot be empty or longer than 16 characters.")

    id = register(username)

    qr = base64QR(f"player-{id}")

    return render_template("registered.html", id=id, qr=qr)

if __name__ == "__main__" :
    for dir in [] :
        if not os.path.isdir(dir) :
            os.mkdir(dir)

    app.run(threaded=True, host="0.0.0.0", port=5000, debug=True)