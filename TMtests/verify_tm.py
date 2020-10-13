import argparse

from tmcode.bots.randombot import FastRandomBot
from tmcode.board import Point, Player, GameState

COLS = 'ABCDEFGHJKLMNOPQRST'
STONE_TO_CHAR = {
    None: ' . ',
    Player.black: ' x ',
    Player.white: ' o ',
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
            stone = board.get(Point(row=row, col=col))
            line.append(STONE_TO_CHAR[stone])
        print('%s%d %s' % (bump, row, ''.join(line)))
    print('    ' + '  '.join(COLS[:board.num_cols]))

def point_from_coords(coords):
    col = COLS.index(coords[0]) + 1
    row = int(coords[1:])
    return Point(row=row, col=col)

def coords_from_point(point):
    return '%s%d' % (
        COLS[point.col - 1],
        point.row
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--board-size', type=int, default=9)
    parser.add_argument('--tm-value', type=int, default=8)
    args = parser.parse_args()

    game = GameState.new_game(args.board_size, komi=None, ThueMorse=args.tm_value)
    bots = {
        Player.black: FastRandomBot(),
        Player.white: FastRandomBot(),
    }
    
    print_board(game.board)
    for i in range(args.tm_value+5):
        bot_move = bots[game.next_player].select_move(game)
        print_move(game.next_player, bot_move)
        game = game.apply_move(bot_move)
        print_board(game.board)

if __name__ == '__main__':
    main()
