"""
Telegram Bot: "Run Away from Cats"

Description:
This module implements a Telegram bot that allows players
to engage in a game where the goal is to evade cats on a
grid-like field. The bot supports starting new games, player
movements, and saving/loading game progress.

Game Logic:
Cats move towards the player using Manhattan distance
to simulate chasing behavior. Obstacles and cats are dynamically
generated to keep the game unpredictable.

Telegram Integration:
The bot uses Telegram's API to handle user input, send messages,
and manage game sessions.

Author: iamshelldy
Version: 1.0.0
Date: 2024-11-12
"""


import json
import time
import logging
import pickle
import random

from typing import Union, List

import requests

# Size of the game grid (must be an odd number). Default: 5.
FIELD_SIZE = 5
# The middle index of the grid. Also, player's coordinates are MIDDLE_POS, MIDDLE_POS
MIDDLE_POS: int = (FIELD_SIZE - 1) // 2

PLAYER_SYMBOL = '🙂'    # Represents the player.
CAT_SYMBOL = '🐱'       # Represents cats.
OBSTACLE_SYMBOL = '🌳'  # Represents obstacles.
EMPTY_SYMBOL = '🟩'     # Represents an empty cell.

# Predefined messages for game events.
GREETING_MESSAGE = 'Hi, {}! To start game, press /newgame'
NEW_GAME_MESSAGE = "You have to run from cats! I don't know why. Just run.\n"
GAME_OVER_MESSAGE = 'Unfortunately, the cats caught up with you. Play again? /newgame\n'
GOOD_JOB_MESSAGE = "You're doing great! Keep running away from cats.\n"
PROGRESS_LOADED_MESSAGE = 'Your game was successfully loaded!\n'
FIELD_MESSAGE = ('{}' * FIELD_SIZE + '\n') * FIELD_SIZE
NAVIGATED_MESSAGE = '⠀' * (FIELD_SIZE + 2) + '/up\n' + \
                    ('⠀⠀⠀' + '{}' * FIELD_SIZE + '\n') * MIDDLE_POS +\
                    '/left' + '{}' * FIELD_SIZE + '/right\n' +\
                    ('⠀⠀⠀' + "{}" * FIELD_SIZE + '\n') * MIDDLE_POS +\
                    '⠀' * (FIELD_SIZE + 2) + '/down'

# Dictionary mapping movement directions to their opposites.
# If player runs to the left, we have move objects to the right.
DIRECTIONS = {
    'left': 'right',
    'right': 'left',
    'up': 'down',
    'down': 'up'
}

# Predefined positions around the player to check for cats.
POSITIONS_TO_CHECK_CATS = [
    (MIDDLE_POS, MIDDLE_POS - 1),
    (MIDDLE_POS, MIDDLE_POS + 1),
    (MIDDLE_POS - 1, MIDDLE_POS),
    (MIDDLE_POS + 1, MIDDLE_POS),
]


class Position:
    """
    Represents a single cell on the game field.

    Attributes:
        :param x (int): row coordinate
        :param y (int): column coordinate
        :param data(str): the symbol representing the cell content.
    """
    def __init__(self, x: int, y: int, data: str) -> None:
        self.x = x
        self.y = y
        self.data = data

    def manhattan(self, other_position: Union['Position', tuple[int, int]]) -> int:
        """
        Calculates the Manhattan distance between the
        current position and another position.

        :param other_position: another position
        :return: int: the manhattan distance
        """
        if isinstance(other_position, Position):
            return abs(self.x - other_position.x) + abs(self.y - other_position.y)
        return abs(self.x - other_position[0]) + abs(self.y - other_position[1])

    def __str__(self) -> str:
        return self.data


class GameField:
    """
    Represents the game field where the game takes place.

    Attributes:
        :param field_data (List[List[Position]]): the game field data.
    """
    def __init__(self) -> None:
        self.field_data = self.generate_clear()
        self.generate_cats()
        self.generate_obstacles()

    def __str__(self) -> str:
        return '\n'.join(''.join(str(col) for col in row)\
                         for row in self.field_data)

    def __getitem__(self, item) -> Union[Position, List[Position]]:
        """
        Allows direct access to rows or positions using []
        x.__getitem__(y) <==> x.field_data[y]
        """
        return self.field_data[item]

    @staticmethod
    def generate_row(row_index: int) -> List[Position]:
        """
        Generates a single row with random obstacles.

        :param row_index: index of the new row
        :return: generated row
        """
        result = []
        for col in range(FIELD_SIZE):
            result.append(Position(row_index, col, EMPTY_SYMBOL))

        for i in range(FIELD_SIZE // 3):
            random.choice(result).data = OBSTACLE_SYMBOL

        return result

    @staticmethod
    def generate_clear() -> List[List[Position]]:
        """
         Creates an empty field and places the player in the center.

        :return: generated field
        """
        result = [[] for _ in range(FIELD_SIZE)]
        for row in range(FIELD_SIZE):
            for col in range(FIELD_SIZE):
                result[row].append(Position(row, col, EMPTY_SYMBOL))
        result[MIDDLE_POS][MIDDLE_POS].data = PLAYER_SYMBOL
        return result

    def generate_cats(self, number: int = 1) -> None:
        """
        Spawns a given number of cats at random edges of the field.

        :param number: number of cats to spawn
        :return: None
        """
        cats_generated = 0
        while cats_generated < number:
            random_coordinate = random.randint(0, FIELD_SIZE - 1)
            possible_cats_positions = [
                (0, random_coordinate),
                (FIELD_SIZE - 1, random_coordinate),
                (random_coordinate, 0),
                (random_coordinate, FIELD_SIZE - 1),
            ]
            new_cat_position = random.choice(possible_cats_positions)
            x, y = new_cat_position
            if self[x][y].data != EMPTY_SYMBOL:
                continue
            if self[MIDDLE_POS][MIDDLE_POS].manhattan((x, y)) < 2:
                continue
            self[x][y].data = CAT_SYMBOL
            cats_generated += 1

    def generate_obstacles(self, obstacles_number: int = 3) -> None:
        """
        Places random obstacles on the field

        :param obstacles_number: number of obstacles to place
        :return: None
        """
        obstacles_generated = 0
        while obstacles_generated < obstacles_number:
            x, y = (random.randint(0, FIELD_SIZE - 1),
                    random.randint(0, FIELD_SIZE - 1))
            if self[x][y].data != EMPTY_SYMBOL:
                continue
            self[x][y].data = OBSTACLE_SYMBOL
            obstacles_generated += 1

    def move_objects(self, direction: str) -> None:
        """
        Moves all objects on the field based on the player's movement direction.

        :param direction: either 'left' or 'right' or 'up' or 'down'
        :return: None
        """
        # Remove player from field
        self[MIDDLE_POS][MIDDLE_POS].data = EMPTY_SYMBOL
        match direction:
            case 'left':
                for row in range(FIELD_SIZE):
                    new_row = self[row][1:]
                    new_row.append(Position(row, FIELD_SIZE, EMPTY_SYMBOL))
                    self.field_data[row] = new_row
                    for col in range(FIELD_SIZE):
                        self[row][col].y -= 1

                for i in range(2):
                    random_row = random.randint(0, FIELD_SIZE - 1)
                    self[random_row][FIELD_SIZE - 1].data = OBSTACLE_SYMBOL
            case 'right':
                for row in range(FIELD_SIZE):
                    new_row = [Position(row, -1, EMPTY_SYMBOL)]
                    new_row.extend(self[row][:-1])
                    self.field_data[row] = new_row
                    for col in range(FIELD_SIZE):
                        self[row][col].y += 1

                for i in range(2):
                    random_row = random.randint(0, FIELD_SIZE - 1)
                    self[random_row][0].data = OBSTACLE_SYMBOL
            case 'up':
                for row in range(FIELD_SIZE - 1):
                    self.field_data[row] = self.field_data[row + 1]
                    for col in range(FIELD_SIZE - 1):
                        self[row][col].x -= 1
                self.field_data[FIELD_SIZE - 1] = self.generate_row(FIELD_SIZE - 1)
            case 'down':
                for row in range(FIELD_SIZE - 1, 0, -1):
                    print(row)
                    self.field_data[row] = self.field_data[row - 1]
                    for col in range(FIELD_SIZE - 1):
                        self[row][col].x += 1
                self.field_data[0] = self.generate_row(0)
        # Return player to field
        self[MIDDLE_POS][MIDDLE_POS].data = PLAYER_SYMBOL

    def move_cat(self, cat_row: int, cat_column: int):
        """
        Moves a cat one step closer to the player.

        :param cat_row: row of the cat
        :param cat_column: column of the cat
        :return: None
        """
        positions_to_check = [
            (cat_row, cat_column),
            (cat_row, cat_column - 1),
            (cat_row, cat_column + 1),
            (cat_row - 1, cat_column),
            (cat_row + 1, cat_column),
        ]
        current_position = positions_to_check[0]
        current_distance = self[MIDDLE_POS][MIDDLE_POS].manhattan(current_position)

        for position in positions_to_check[1:]:
            x, y = position
            if x < 0 or x >= FIELD_SIZE or y < 0 or y >= FIELD_SIZE:
                continue
            if self[x][y].data != EMPTY_SYMBOL:
                continue
            new_distance = self[MIDDLE_POS][MIDDLE_POS].manhattan(position)
            if new_distance < current_distance:
                current_distance = new_distance
                current_position = position

        self.field_data[cat_row][cat_column].data = EMPTY_SYMBOL
        x, y = current_position
        self.field_data[x][y].data = CAT_SYMBOL

    def proceed_cats_turn(self) -> None:
        """
        Processes all cat movements and checks for game over.

        :return: None
        """
        for row in range(FIELD_SIZE):
            for col in range(FIELD_SIZE):
                if self[row][col].data == CAT_SYMBOL:
                    self.move_cat(row, col)
                    if self.is_game_over():
                        return

    def is_game_over(self) -> bool:
        """
        Checks if the game is over (a cat has reached the player).

        :return: True if the game is over, False otherwise
        """
        return any(self[x][y].data == CAT_SYMBOL for x, y in POSITIONS_TO_CHECK_CATS)

    def move_player(self, direction: str) -> None:
        """
        Moves the player in the specified direction if the path is clear.

        :param direction: either 'left' or 'right' or 'up' or 'down'
        :return: None
        """
        if direction not in DIRECTIONS:
            raise ValueError('invalid direction')
        match direction:
            case 'left':
                if self[MIDDLE_POS][MIDDLE_POS - 1].data == EMPTY_SYMBOL:
                    self.move_objects(DIRECTIONS[direction])
            case 'right':
                if self[MIDDLE_POS][MIDDLE_POS + 1].data == EMPTY_SYMBOL:
                    self.move_objects(DIRECTIONS[direction])
            case 'up':
                if self[MIDDLE_POS - 1][MIDDLE_POS].data == EMPTY_SYMBOL:
                    self.move_objects(DIRECTIONS[direction])
            case 'down':
                if self[MIDDLE_POS + 1][MIDDLE_POS].data == EMPTY_SYMBOL:
                    self.move_objects(DIRECTIONS[direction])


class Bot:
    """
    Handles the Telegram bot's interaction with users and game logic.

    :param token (str): Bot token

    Attributes:
        :param base_url (str): Base URL for Telegram Bot API requests
        :param last_update_id (int): The id of the last update
        :param players_data (dict[GameField]): Stores game fields for each player
    """
    def __init__(self, token) -> None:
        self.logger = logging.getLogger(__name__)
        self.base_url = f'https://api.telegram.org/bot{token}/'
        self.last_update_id = None
        self.players_data = dict()

    def save_state(self) -> None:
        """Saves the bot's state (e.g., last update ID) to a file."""
        with open('./data/bot_state.json', 'w') as f:
            state = {'last_update_id': self.last_update_id}
            json.dump(state, f)

    def load_state(self) -> None:
        """Loads the bot's state from a file."""
        try:
            with open('./data/bot_state.json', 'r') as f:
                state = json.load(f)
                self.last_update_id = state.get('last_update_id', None)
                self.logger.info('BOT STATE SUCCESSFULLY LOADED')
        except FileNotFoundError:
            self.last_update_id = None
            self.logger.info("CAN'T LOAD BOT STATE. FILE NOT FOUND")

    def load_player_data(self, chat_id: int) -> None:
        """Loads a player's game field from a file."""
        with open(f'./data/{chat_id}.pkl', 'rb') as f:
            self.players_data[chat_id] = pickle.load(f)
        self.logger.debug(f'PLAYER {chat_id} LOADED FIELD:\n'
                         f'{self.players_data[chat_id]}')

    def save_player_data(self, chat_id: int) -> None:
        """Saves a player's game field to a file."""
        with open(f'./data/{chat_id}.pkl', 'wb') as f:
            pickle.dump(self.players_data[chat_id], f)
        self.logger.debug(f'PLAYER {chat_id} SAVED FIELD:\n'
                          f'{self.players_data[chat_id]}')

    def get_updates(self, started) -> dict:
        """
        Fetches updates from the Telegram API.

        :param started: True if the bot gets first update, False otherwise
        :return: Updates dictionary
        """
        url = f'{self.base_url}getUpdates'
        if started:
            url += '?offset=-1'
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.warning(f'ERROR FETCHING UPDATES: {e}')
            return {'ok': False, 'result': []}

    def send_message(self, chat_id: int, text: str) -> None:
        """Sends a message to the specified chat."""
        url = f'{self.base_url}sendMessage'
        requests.post(url, json={'chat_id': chat_id, 'text': text})

    def proceed_message(self, chat_id: int, user_name: str, message: str):
        """Processes incoming messages and performs the appropriate action."""
        match message:
            case '/newgame':
                self.logger.info(f'PLAYER {chat_id} STARTS NEW GAME.')
                self.players_data[chat_id] = GameField()
                message = NEW_GAME_MESSAGE + NAVIGATED_MESSAGE.format(
                    *(cell for row in self.players_data[chat_id] for cell in row)
                )
                self.send_message(chat_id, message)

            case '/left' | '/right' | '/up' | '/down':
                self.logger.debug(f'PROCEEDING PLAYER {chat_id} TURN {message}. '
                                  f'STARTING FIELD STATE:\n{self.players_data[chat_id]}')
                self.players_data[chat_id].move_player(message[1:])
                self.logger.debug(f'OBJECTS MOVED:\n{self.players_data[chat_id]}')
                self.players_data[chat_id].proceed_cats_turn()
                self.logger.debug(f'CATS MOVES PROCEEDED:\n{self.players_data[chat_id]}')
                self.players_data[chat_id].generate_cats()
                self.logger.debug(f'GENERATED NEW CATS:\n{self.players_data[chat_id]}')

                if self.players_data[chat_id].is_game_over():
                    self.logger.info(f'PLAYER {chat_id} LOST GAME.')
                    message = GAME_OVER_MESSAGE + FIELD_MESSAGE.format(
                        *(cell for row in self.players_data[chat_id] for cell in row)
                    )
                else:
                    message = GOOD_JOB_MESSAGE + NAVIGATED_MESSAGE.format(
                        *(cell for row in self.players_data[chat_id] for cell in row)
                    )
                self.send_message(chat_id, message)

            case _:
                if chat_id in self.players_data:
                    message = PROGRESS_LOADED_MESSAGE + NAVIGATED_MESSAGE.format(
                        *(cell for row in self.players_data[chat_id] for cell in row)
                    )
                else:
                    message = GREETING_MESSAGE.format(user_name)
                self.send_message(chat_id, message)

    def run(self):
        """Main loop for running the bot."""
        self.load_state()
        just_started = True

        while True:
            updates = self.get_updates(just_started)
            just_started = False
            if updates.get('ok'):
                for update in updates['result']:
                    if 'message' in update:
                        update_id = update['update_id']
                        if self.last_update_id is None or\
                                update_id > self.last_update_id:
                            chat_id = update['message']['chat']['id']

                            if chat_id not in self.players_data:
                                try:
                                    self.load_player_data(chat_id)
                                except FileNotFoundError:
                                    self.players_data[chat_id] = GameField()
                                    self.logger.debug(f"CAN'T LOAD PLAYER {chat_id}"
                                                      'FIELD. CREATED NEW ONE.\n'
                                                      f'{self.players_data[chat_id]}')

                            message = update['message']['text']
                            user_name = update['message']['from']['first_name']

                            self.proceed_message(chat_id, user_name, message)
                            self.save_player_data(chat_id)

                            self.last_update_id = update_id
                            self.save_state()

                    time.sleep(3)
