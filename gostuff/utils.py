import platform
import subprocess
import numpy as np
from gostuff import gotypes

# Adapted from https://github.com/maxpumperla/deep_learning_and_the_game_of_go/blob/master/code/dlgo/utils.py

# Stdout representations
COLS = 'ABCDEFGHJKLMNOPQRST'
STONE_TO_CHAR = {
    None: ' . ',
    gotypes.Player.black: ' x ',
    gotypes.Player.white: ' o ',
}

def print_move(player, move):
    if move.is_pass:
        move_str = 'passes'
    elif move.is_resign:
        move_str = 'resigns'
    else:
        move_str = '%s%d' % (COLS[move.point.col - 1], move.point.row)
    print('%s %s' % (player, move_str))

def print_board(board):
    for row in range(board.num_rows, 0, -1):
        bump = " " if row <= 9 else ""
        line = []
        for col in range(1, board.num_cols + 1):
            stone = board.get(gotypes.Point(row=row, col=col))
            line.append(STONE_TO_CHAR[stone])
        print('%s%d %s' % (bump, row, ''.join(line)))
    print('    ' + '  '.join(COLS[:board.num_cols]))

def point_from_coords(coords):
    col = COLS.index(coords[0]) + 1
    row = int(coords[1:])
    return gotypes.Point(row=row, col=col)

def coords_from_point(point):
    return '%s%d' % (
        COLS[point.col - 1],
        point.row
    )

# Array of the order in which stones have been played. 
class MoveAge():
    def __init__(self, board):
        self.move_ages = np.zeros((board.num_rows, board.num_cols))

    def get(self, row, col):
        # Age of specific point.
        return self.move_ages[row, col]

    def reset_age(self, point):
        # Stone removed.
        self.move_ages[point.row - 1, point.col - 1] = 0

    def add(self, point):
        # New stone.
        self.move_ages[point.row - 1, point.col - 1] = 1
