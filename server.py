import random

from flask import Flask, request, render_template
from flask_socketio import SocketIO

app = Flask(__name__, static_folder='static')
socketio = SocketIO(app)
game = {
    'number': 0,
    'num_guesses': 0,
    'max_players': 2,
    'players': {}
}

def prompt_players():
    '''
    Send a message to players letting them know if it's their turn
    or if they are waiting on another player to guess.
    '''
    next_player_id, (next_player_number, _, _) = next_player()

    socketio.send("It's your turn. What number am I thinking of?", room=next_player_id)

    for player_id, (player_number, _, _) in game['players'].items():
        if player_id != next_player_id:
            socketio.send(f"Waiting on player {next_player_number} to guess.", room=player_id)

def response_to_accuracy(player_accuracy):
    '''
    Create a message letting the player know how good their guess is.
    :param player_accuracy: distance from the actual number
    :return: message
    '''
    message = ""

    if player_accuracy == 0:
        message = "You must be a mind reader."

    elif player_accuracy < 5:
        message = "Wow! You're really good at this."

    elif player_accuracy < 10:
        message = "That's a decent guess."

    elif player_accuracy < 20:
        message = "Not terrible, but could be better."

    else:
        message = "Oof. That's terrible."

    return message

def update(player_id, player_guess):
    '''
    Update the player to include their guess and its accuracy
    :param player_id: session id of the player
    :param player_guess: the number they guessed
    :return:
    '''
    player_number, _, _ = game['players'][player_id]
    accuracy = abs(player_guess - game['number'])
    game['players'][request.sid] = (player_number, player_guess, accuracy)
    game['num_guesses'] = game['num_guesses'] + 1

def next_player():
    '''
    Return the session id and corresponding parameters of the next player
    that will guess.

    If all players have guessed, session id and parameters will be `None`.
    :return:
    '''
    def number(player_id):
        return game['players'][player_id][0]

    try:
        player_id = sorted(game['players'], key=number)[game['num_guesses']]
    except IndexError:
        player_id = None
        player = (None, None, None)
    else:
        player = game['players'][player_id]
    return player_id, player

def add_player(player_id):
    '''
    Adds the session id for the new player to the game
    :param player_id: session id
    :return:
    '''
    num_players = len(game['players'])
    game['players'][player_id] = (num_players + 1, None, None)

def start_game():
    '''
    Resets values for the game and prompts the players.
    :return:
    '''
    game['num_guesses'] = 0
    game['number'] = random.randint(1, 101)

    socketio.send("I'm thinking of a number between 1 and 100.")
    prompt_players()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('disconnect')
def disconnect():
    del game['players'][request.sid]

@socketio.on('connect')
def connected():
    '''
    Listens for new players and adds them to the game.
    The game will not start until `game['max_players']` have joined.
    :return:
    '''
    add_player(request.sid)
    number_players = len(game['players'])
    max_players = game['max_players']

    socketio.send(f"You are player {number_players}.", room=request.sid)
    socketio.send(f"This will be a {max_players} player game.", room=request.sid)

    if number_players != max_players:
        socketio.send(f"Waiting for player {number_players + 1}")

    else:
        socketio.send("All players are here. Let's play!")
        start_game()

@socketio.on('message')
def on_message(player_guess):
    '''
    Listens for guesses from players. Guesses that are not from the current player are ignored.

    Once all gueses are received, let players know the correct answer and reset the game.
    :param player_guess:
    :return:
    '''
    def accuracy(player_id):
        '''
        Returns the accuracy for the player
        :param player_id: session id
        :return:
        '''
        return game['players'][player_id][2]

    player_number, _, _ = game['players'][request.sid]

    #If the current player has guessed, update the game and let the player know how well they guessed.
    if player_number - 1 == game['num_guesses']:
        update(request.sid, player_guess)
        _, _, player_accuracy = game['players'][request.sid]
        socketio.send(response_to_accuracy(player_accuracy), room=request.sid)

    #Otherwise, let the player know it's not their turn to guess.
    else:
        socketio.send("It's not your turn, silly.", room=request.sid)

    next_player_id, (next_player_number, _, _) = next_player()

    #All players have guesses, so check to see who won based off of closest guess
    if game['num_guesses'] == game['max_players']:
        number = game['number']
        socketio.send(f"My number was {number}")

        for _, (player_number, player_guess, _) in game['players'].items():
            socketio.send(f"Player {player_number} guessed {player_guess}")

        player_id = min(game['players'], key=accuracy)
        player_number, _, _ = game['players'][player_id]

        socketio.send(f"Player {player_number} won!")
        start_game()

    #Otherwise, prompt all players if it's someone elses turn
    elif next_player_number != player_number:
        socketio.send(f"Player {player_number} guessed.")
        prompt_players()

if __name__ == "__main__":
    socketio.run(app)