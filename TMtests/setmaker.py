import csv
import h5py
import argparse

from tmcode.board import Player, GameState
from tmcode.bots.predict import load_bot
from tmcode.bots.randombot import FastRandomBot

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--board-sizes', type=str, default='9,13,19')
    parser.add_argument('--tm-values', type=str, default='8')
    parser.add_argument('--num-games', type=int, default=1000)
    parser.add_argument('--bot', type=str, default='random')
    parser.add_argument('--savepath', type=str, required=True)
    args = parser.parse_args()

    board_sizes = [int(item) for item in args.board_sizes.split(',')]
    if args.bot.endswith('.h5'):
        board_sizes = [19]
    tm_values = [int(item) for item in args.tm_values.split(',')]
    tm_values.insert(0, 0)
    total_test_groups = len(board_sizes) * len(tm_values) + len(board_sizes)
    total_games = total_test_groups * args.num_games
    print('Total number of test groups is %s. Total number of games is %s.' %(total_test_groups, total_games))

    if not args.savepath.endswith('.csv'):
        args.savepath = args.savepath + '.csv'
    csv_columns = ['tm_value', 'board_size', 'winner', 'margin', 'komi']
    csvfile = open(args.savepath,'w')
    writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
    writer.writeheader()

    bots = {
        Player.black: FastRandomBot(),
        Player.white: FastRandomBot()
        }

    if args.bot.endswith('.h5'):
        bot1 = load_bot(h5py.File(args.bot, 'r'))
        bot2 = load_bot(h5py.File(args.bot, 'r'))
        bots = {
            Player.black: bot1,
            Player.white: bot2
            }

    raw_results = {}
    game_count = 0
    one_pct = total_games/100
    # games without komi or Thue-Morse
    for board_size in board_sizes:
        for i in range(args.num_games):
            game = GameState.new_game(board_size, komi=None)
            while not game.is_over():
                bot_move = bots[game.next_player].select_move(game)
                game = game.apply_move(bot_move)
            winner, margin, komi = game.result()
            results = {'tm_value': 0, 
                       'board_size': board_size, 
                       'winner': winner, 
                       'margin': margin, 
                       'komi': komi}
            writer.writerow(results)
            game_count += 1
            if game_count >= one_pct and game_count % one_pct == 0:
                print('%s%% complete' %(int(game_count/one_pct)))

    for value in tm_values:
        for board_size in board_sizes:
            for i in range(args.num_games):
                if value:
                    game = GameState.new_game(board_size, komi=None, ThueMorse=value)
                else:
                    game = GameState.new_game(board_size, ThueMorse=value)
                while not game.is_over():
                    bot_move = bots[game.next_player].select_move(game)
                    game = game.apply_move(bot_move)
                winner, margin, komi = game.result()
                results = {'tm_value': value, 
                           'board_size': board_size, 
                           'winner': winner, 
                           'margin': margin, 
                           'komi': komi}
                writer.writerow(results)
                game_count += 1
                if game_count % one_pct == 0:
                    print('%s%% complete' %(int(game_count/one_pct)))

    csvfile.close()

if __name__ == '__main__':
    main()
