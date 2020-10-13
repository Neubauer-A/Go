import copy
import enum
from collections import namedtuple

# Go types
class Player(enum.Enum):
    black = 1
    white = 2

    @property
    def other(self):
        return Player.black if self == Player.white else Player.white

class Point(namedtuple('Point', 'row col')):
    def neighbors(self):
        return [
            Point(self.row - 1, self.col),
            Point(self.row + 1, self.col),
            Point(self.row, self.col - 1),
            Point(self.row, self.col + 1),
        ]

    def __deepcopy__(self, memodict={}):
        return self

# scoring
class Territory:
    def __init__(self, territory_map):
        self.num_black_territory = 0
        self.num_white_territory = 0
        self.num_black_stones = 0
        self.num_white_stones = 0
        self.num_dame = 0
        self.dame_points = []
        for point, status in territory_map.items(): 
            if status == Player.black:
                self.num_black_stones += 1
            elif status == Player.white:
                self.num_white_stones += 1
            elif status == 'territory_b':
                self.num_black_territory += 1
            elif status == 'territory_w':
                self.num_white_territory += 1
            elif status == 'dame':
                self.num_dame += 1
                self.dame_points.append(point)

class GameResult(namedtuple('GameResult', 'b w komi')):
    @property
    def winner(self):
        if self.b > self.w + self.komi:
            return 'Black'
        return 'White'

    @property
    def winning_margin(self):
        w = self.w + self.komi
        return abs(self.b - w)

    def __str__(self):
        w = self.w + self.komi
        if self.b > w:
            return 'B+%.1f' % (self.b - w,)
        return 'W+%.1f' % (w - self.b,)

def evaluate_territory(board):
    status = {}
    for r in range(1, board.num_rows + 1):
        for c in range(1, board.num_cols + 1):
            p = Point(row=r, col=c)
            if p in status: 
                continue
            stone = board.get(p)
            if stone is not None: 
                status[p] = board.get(p)
            else:
                group, neighbors = _collect_region(p, board)
                if len(neighbors) == 1: 
                    neighbor_stone = neighbors.pop()
                    stone_str = 'b' if neighbor_stone == Player.black else 'w'
                    fill_with = 'territory_' + stone_str
                else:
                    fill_with = 'dame'
                for pos in group:
                    status[pos] = fill_with
    return Territory(status)

def _collect_region(start_pos, board, visited=None):

    if visited is None:
        visited = {}
    if start_pos in visited:
        return [], set()
    all_points = [start_pos]
    all_borders = set()
    visited[start_pos] = True
    here = board.get(start_pos)
    deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for delta_r, delta_c in deltas:
        next_p = Point(row=start_pos.row + delta_r, col=start_pos.col + delta_c)
        if not board.is_on_grid(next_p):
            continue
        neighbor = board.get(next_p)
        if neighbor == here:
            points, borders = _collect_region(next_p, board, visited)
            all_points += points
            all_borders |= borders
        else:
            all_borders.add(neighbor)
    return all_points, all_borders

def compute_game_result(game_state, komi):
    territory = evaluate_territory(game_state.board)
    return GameResult(
        territory.num_black_territory + territory.num_black_stones,
        territory.num_white_territory + territory.num_white_stones,
        komi=komi)

# Go board
neighbor_tables = {}
corner_tables = {}

def init_neighbor_table(dim):
    rows, cols = dim
    new_table = {}
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            p = Point(row=r, col=c)
            full_neighbors = p.neighbors()
            true_neighbors = [
                n for n in full_neighbors
                if 1 <= n.row <= rows and 1 <= n.col <= cols]
            new_table[p] = true_neighbors
    neighbor_tables[dim] = new_table


def init_corner_table(dim):
    rows, cols = dim
    new_table = {}
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            p = Point(row=r, col=c)
            full_corners = [
                Point(row=p.row - 1, col=p.col - 1),
                Point(row=p.row - 1, col=p.col + 1),
                Point(row=p.row + 1, col=p.col - 1),
                Point(row=p.row + 1, col=p.col + 1),
            ]
            true_corners = [
                n for n in full_corners
                if 1 <= n.row <= rows and 1 <= n.col <= cols]
            new_table[p] = true_corners
    corner_tables[dim] = new_table


class IllegalMoveError(Exception):
    pass


class GoString():
    def __init__(self, color, stones, liberties):
        self.color = color
        self.stones = frozenset(stones)
        self.liberties = frozenset(liberties)

    def without_liberty(self, point):
        new_liberties = self.liberties - set([point])
        return GoString(self.color, self.stones, new_liberties)

    def with_liberty(self, point):
        new_liberties = self.liberties | set([point])
        return GoString(self.color, self.stones, new_liberties)

    def merged_with(self, string):
        assert string.color == self.color
        combined_stones = self.stones | string.stones
        return GoString(
            self.color,
            combined_stones,
            (self.liberties | string.liberties) - combined_stones)

    @property
    def num_liberties(self):
        return len(self.liberties)

    def __eq__(self, other):
        return isinstance(other, GoString) and \
            self.color == other.color and \
            self.stones == other.stones and \
            self.liberties == other.liberties

    def __deepcopy__(self, memodict={}):
        return GoString(self.color, self.stones, copy.deepcopy(self.liberties))


class Board():
    def __init__(self, num_rows, num_cols):
        self.num_rows = num_rows
        self.num_cols = num_cols
        self._grid = {}
        self._hash = EMPTY_BOARD

        global neighbor_tables
        dim = (num_rows, num_cols)
        if dim not in neighbor_tables:
            init_neighbor_table(dim)
        if dim not in corner_tables:
            init_corner_table(dim)
        self.neighbor_table = neighbor_tables[dim]
        self.corner_table = corner_tables[dim]

    def neighbors(self, point):
        return self.neighbor_table[point]

    def corners(self, point):
        return self.corner_table[point]

    def place_stone(self, player, point):
        assert self.is_on_grid(point)
        if self._grid.get(point) is not None:
            print('Illegal play on %s' % str(point))
        assert self._grid.get(point) is None
        adjacent_same_color = []
        adjacent_opposite_color = []
        liberties = []
        for neighbor in self.neighbor_table[point]:
            neighbor_string = self._grid.get(neighbor)
            if neighbor_string is None:
                liberties.append(neighbor)
            elif neighbor_string.color == player:
                if neighbor_string not in adjacent_same_color:
                    adjacent_same_color.append(neighbor_string)
            else:
                if neighbor_string not in adjacent_opposite_color:
                    adjacent_opposite_color.append(neighbor_string)
        new_string = GoString(player, [point], liberties)

        for same_color_string in adjacent_same_color:
            new_string = new_string.merged_with(same_color_string)
        for new_string_point in new_string.stones:
            self._grid[new_string_point] = new_string
        self._hash ^= HASH_CODE[point, None]
        self._hash ^= HASH_CODE[point, player]

        for other_color_string in adjacent_opposite_color:
            replacement = other_color_string.without_liberty(point)
            if replacement.num_liberties:
                self._replace_string(other_color_string.without_liberty(point))
            else:
                self._remove_string(other_color_string)

    def _replace_string(self, new_string):
        for point in new_string.stones:
            self._grid[point] = new_string

    def _remove_string(self, string):
        for point in string.stones:
            for neighbor in self.neighbor_table[point]:
                neighbor_string = self._grid.get(neighbor)
                if neighbor_string is None:
                    continue
                if neighbor_string is not string:
                    self._replace_string(neighbor_string.with_liberty(point))
            self._grid[point] = None
            self._hash ^= HASH_CODE[point, string.color]
            self._hash ^= HASH_CODE[point, None]

    def is_self_capture(self, player, point):
        friendly_strings = []
        for neighbor in self.neighbor_table[point]:
            neighbor_string = self._grid.get(neighbor)
            if neighbor_string is None:
                return False
            elif neighbor_string.color == player:
                friendly_strings.append(neighbor_string)
            else:
                if neighbor_string.num_liberties == 1:
                    return False
        if all(neighbor.num_liberties == 1 for neighbor in friendly_strings):
            return True
        return False

    def will_capture(self, player, point):
        for neighbor in self.neighbor_table[point]:
            neighbor_string = self._grid.get(neighbor)
            if neighbor_string is None:
                continue
            elif neighbor_string.color == player:
                continue
            else:
                if neighbor_string.num_liberties == 1:
                    return True
        return False

    def is_on_grid(self, point):
        return 1 <= point.row <= self.num_rows and \
            1 <= point.col <= self.num_cols

    def get(self, point):
        string = self._grid.get(point)
        if string is None:
            return None
        return string.color

    def get_go_string(self, point):
        string = self._grid.get(point)
        if string is None:
            return None
        return string

    def __eq__(self, other):
        return isinstance(other, Board) and \
            self.num_rows == other.num_rows and \
            self.num_cols == other.num_cols and \
            self._hash() == other._hash()

    def __deepcopy__(self, memodict={}):
        copied = Board(self.num_rows, self.num_cols)
        copied._grid = copy.copy(self._grid)
        copied._hash = self._hash
        return copied

    def zobrist_hash(self):
        return self._hash


class Move():
    def __init__(self, point=None, is_pass=False, is_resign=False):
        assert (point is not None) ^ is_pass ^ is_resign
        self.point = point
        self.is_play = (self.point is not None)
        self.is_pass = is_pass
        self.is_resign = is_resign

    @classmethod
    def play(cls, point):
        return Move(point=point)

    @classmethod
    def pass_turn(cls):
        return Move(is_pass=True)

    @classmethod
    def resign(cls):
        return Move(is_resign=True)

    def __str__(self):
        if self.is_pass:
            return 'pass'
        if self.is_resign:
            return 'resign'
        return '(r %d, c %d)' % (self.point.row, self.point.col)

    def __hash__(self):
        return hash((
            self.is_play,
            self.is_pass,
            self.is_resign,
            self.point))

    def  __eq__(self, other):
        return (
            self.is_play,
            self.is_pass,
            self.is_resign,
            self.point) == (
            other.is_play,
            other.is_pass,
            other.is_resign,
            other.point)

KOMI=0

class GameState():
    # We assume ThueMorse is irrelevant unless specified at the start of a game with some integer.
    def __init__(self, board, next_player, previous, move, ThueMorse=None, turn_count=None):
        self.board = board
        self.next_player = next_player
        self.previous_state = previous
        if previous is None:
            self.previous_states = frozenset()
        else:
            self.previous_states = frozenset(
                previous.previous_states |
                {(previous.next_player, previous.board.zobrist_hash())})
        self.last_move = move
        self.ThueMorse = ThueMorse
        # If we're still in the TM limit we set...
        if self.ThueMorse and self.ThueMorse > turn_count:
            self.turn_count = turn_count
            # get the sequence and determine the player.
            sequence = self.get_tm_sequence(ThueMorse)
            self.next_player = Player.black if sequence[self.turn_count] == 0 else Player.white
    
    def get_tm_sequence(self, length):
        sequence = []
        # Get the binary of each number from 0 to our TM limit, get the sum of 
        # all the 1s, append the remainder of that sum divided by 2 to a list.
        for n in range(length):
            sequence.append(bin(n).count('1') % 2)
        return sequence

    def apply_move(self, move):
        if move.is_play:
            next_board = copy.deepcopy(self.board)
            next_board.place_stone(self.next_player, move.point)
        else:
            next_board = self.board
        if self.ThueMorse:
            if self.turn_count + 1 != self.ThueMorse:
                return GameState(next_board, self.next_player.other, self, move, self.ThueMorse, turn_count=self.turn_count+1)
        return GameState(next_board, self.next_player.other, self, move)

    @classmethod
    def new_game(cls, board_size, komi='default', ThueMorse=None):
        if isinstance(board_size, int):
            board_size = (board_size, board_size)
        board = Board(*board_size)
        global KOMI
        if not komi:
            KOMI = 0
        elif komi == 'default':
            if board_size[0] == 9:
                KOMI = 5.5
            elif board_size[0] == 13:
                KOMI = 6.5
            else:
                KOMI = 7.5
        else:
            KOMI = komi
        if ThueMorse:
            return GameState(board, Player.black, None, None, ThueMorse, turn_count=0)
        return GameState(board, Player.black, None, None)


    def is_move_self_capture(self, player, move):
        if not move.is_play:
            return False
        return self.board.is_self_capture(player, move.point)

    @property
    def situation(self):
        return (self.next_player, self.board)

    def does_move_violate_ko(self, player, move):
        if not move.is_play:
            return False
        if not self.board.will_capture(player, move.point):
            return False
        next_board = copy.deepcopy(self.board)
        next_board.place_stone(player, move.point)
        next_situation = (player.other, next_board.zobrist_hash())
        return next_situation in self.previous_states

    def is_valid_move(self, move):
        if self.is_over():
            return False
        if move.is_pass or move.is_resign:
            return True
        return (
            self.board.get(move.point) is None and
            not self.is_move_self_capture(self.next_player, move) and
            not self.does_move_violate_ko(self.next_player, move))

    def is_over(self):
        if self.last_move is None:
            return False
        if self.last_move.is_resign:
            return True
        second_last_move = self.previous_state.last_move
        if second_last_move is None:
            return False
        return self.last_move.is_pass and second_last_move.is_pass

    def legal_moves(self):
        if self.is_over():
            return []
        moves = []
        for row in range(1, self.board.num_rows + 1):
            for col in range(1, self.board.num_cols + 1):
                move = Move.play(Point(row, col))
                if self.is_valid_move(move):
                    moves.append(move)
        moves.append(Move.pass_turn())
        moves.append(Move.resign())
        return moves

    def result(self):
        if not self.is_over():
            return None
        if self.last_move.is_resign:
            return self.next_player
        game_result = compute_game_result(self, komi=KOMI)
        return game_result.winner, game_result.winning_margin, KOMI

# Hashes for checking ko    
HASH_CODE = {
    (Point(row=1, col=1), None): 1162283130344086229,
    (Point(row=1, col=1), Player.black): 9138212341767108400,
    (Point(row=1, col=1), Player.white): 450552737902997656,
    (Point(row=1, col=2), None): 7518112373655032120,
    (Point(row=1, col=2), Player.black): 2874921448747074414,
    (Point(row=1, col=2), Player.white): 70514938981617122,
    (Point(row=1, col=3), None): 2192665781030413525,
    (Point(row=1, col=3), Player.black): 6225177836033993326,
    (Point(row=1, col=3), Player.white): 6104895567594294390,
    (Point(row=1, col=4), None): 1847120733389269001,
    (Point(row=1, col=4), Player.black): 2454414734780888641,
    (Point(row=1, col=4), Player.white): 2663217514986023210,
    (Point(row=1, col=5), None): 3908964902394744712,
    (Point(row=1, col=5), Player.black): 7238371430473055228,
    (Point(row=1, col=5), Player.white): 9013577144830356870,
    (Point(row=1, col=6), None): 8360033944632935714,
    (Point(row=1, col=6), Player.black): 6119666825129193576,
    (Point(row=1, col=6), Player.white): 437997259908228553,
    (Point(row=1, col=7), None): 3791426452337650040,
    (Point(row=1, col=7), Player.black): 6873485917124616194,
    (Point(row=1, col=7), Player.white): 1060110416072616937,
    (Point(row=1, col=8), None): 502604448516505625,
    (Point(row=1, col=8), Player.black): 4075646587300812859,
    (Point(row=1, col=8), Player.white): 5752403827836694698,
    (Point(row=1, col=9), None): 6323223384925992932,
    (Point(row=1, col=9), Player.black): 5752683057393766470,
    (Point(row=1, col=9), Player.white): 192342943234938291,
    (Point(row=1, col=10), None): 7049990080509731137,
    (Point(row=1, col=10), Player.black): 4904279465046057899,
    (Point(row=1, col=10), Player.white): 3897712267947759083,
    (Point(row=1, col=11), None): 7817041133220518196,
    (Point(row=1, col=11), Player.black): 4330728823793108246,
    (Point(row=1, col=11), Player.white): 725894760182374621,
    (Point(row=1, col=12), None): 5277608133758487382,
    (Point(row=1, col=12), Player.black): 9047883889504830320,
    (Point(row=1, col=12), Player.white): 1405997386190365186,
    (Point(row=1, col=13), None): 8474469086119755766,
    (Point(row=1, col=13), Player.black): 8893020774137184848,
    (Point(row=1, col=13), Player.white): 3583050097803867420,
    (Point(row=1, col=14), None): 3448410960245003263,
    (Point(row=1, col=14), Player.black): 6172799962719315759,
    (Point(row=1, col=14), Player.white): 1973570913837532184,
    (Point(row=1, col=15), None): 1185742311336680131,
    (Point(row=1, col=15), Player.black): 5352314391420658587,
    (Point(row=1, col=15), Player.white): 7633433129071983266,
    (Point(row=1, col=16), None): 6919441994038514658,
    (Point(row=1, col=16), Player.black): 2511133292311201071,
    (Point(row=1, col=16), Player.white): 7135654296981623221,
    (Point(row=1, col=17), None): 50476040059329004,
    (Point(row=1, col=17), Player.black): 4527523903189713222,
    (Point(row=1, col=17), Player.white): 8137114813478478561,
    (Point(row=1, col=18), None): 7372372038296536774,
    (Point(row=1, col=18), Player.black): 4858938193392573849,
    (Point(row=1, col=18), Player.white): 8108883004580733510,
    (Point(row=1, col=19), None): 6735680132391266754,
    (Point(row=1, col=19), Player.black): 3312211730266320016,
    (Point(row=1, col=19), Player.white): 6755421024588510039,
    (Point(row=2, col=1), None): 425550938533968597,
    (Point(row=2, col=1), Player.black): 5128200195365529303,
    (Point(row=2, col=1), Player.white): 6073791951166816759,
    (Point(row=2, col=2), None): 6733837831897796776,
    (Point(row=2, col=2), Player.black): 7800753780189699206,
    (Point(row=2, col=2), Player.white): 5836911720679622870,
    (Point(row=2, col=3), None): 3916916747746594259,
    (Point(row=2, col=3), Player.black): 51003230900314441,
    (Point(row=2, col=3), Player.white): 6655615386933781681,
    (Point(row=2, col=4), None): 8468469829207274574,
    (Point(row=2, col=4), Player.black): 6113952995570937523,
    (Point(row=2, col=4), Player.white): 5432027850383420277,
    (Point(row=2, col=5), None): 3590496365677858416,
    (Point(row=2, col=5), Player.black): 206488478257264029,
    (Point(row=2, col=5), Player.white): 3890989388601001121,
    (Point(row=2, col=6), None): 752817609747504584,
    (Point(row=2, col=6), Player.black): 8240393740136323604,
    (Point(row=2, col=6), Player.white): 2341196014199144354,
    (Point(row=2, col=7), None): 643149331309327222,
    (Point(row=2, col=7), Player.black): 8306176866168248484,
    (Point(row=2, col=7), Player.white): 6386607133951322576,
    (Point(row=2, col=8), None): 6182669472412284272,
    (Point(row=2, col=8), Player.black): 2256719865523669765,
    (Point(row=2, col=8), Player.white): 8600750506327155101,
    (Point(row=2, col=9), None): 3717782693796911672,
    (Point(row=2, col=9), Player.black): 5370642347967254292,
    (Point(row=2, col=9), Player.white): 284933760019036232,
    (Point(row=2, col=10), None): 616829711339977432,
    (Point(row=2, col=10), Player.black): 3788169609662872843,
    (Point(row=2, col=10), Player.white): 302872583030009755,
    (Point(row=2, col=11), None): 8798517287666174427,
    (Point(row=2, col=11), Player.black): 7443790449831297901,
    (Point(row=2, col=11), Player.white): 6366389027096245012,
    (Point(row=2, col=12), None): 7249105629625768445,
    (Point(row=2, col=12), Player.black): 1098166101729740246,
    (Point(row=2, col=12), Player.white): 5140424914640626428,
    (Point(row=2, col=13), None): 2632030050493346902,
    (Point(row=2, col=13), Player.black): 7083380492849425895,
    (Point(row=2, col=13), Player.white): 1635919570268402621,
    (Point(row=2, col=14), None): 5543033225106289220,
    (Point(row=2, col=14), Player.black): 7534659441371070048,
    (Point(row=2, col=14), Player.white): 3085193996757281783,
    (Point(row=2, col=15), None): 8778074437079014739,
    (Point(row=2, col=15), Player.black): 2398236612404517846,
    (Point(row=2, col=15), Player.white): 6448820548392829030,
    (Point(row=2, col=16), None): 3120961501700419031,
    (Point(row=2, col=16), Player.black): 7006943602452129516,
    (Point(row=2, col=16), Player.white): 6450030375349199623,
    (Point(row=2, col=17), None): 8859886747534092276,
    (Point(row=2, col=17), Player.black): 7738981915817647516,
    (Point(row=2, col=17), Player.white): 2797389142094964696,
    (Point(row=2, col=18), None): 1939650880831770366,
    (Point(row=2, col=18), Player.black): 1484305791862344891,
    (Point(row=2, col=18), Player.white): 1562208742859527548,
    (Point(row=2, col=19), None): 2464992479088604602,
    (Point(row=2, col=19), Player.black): 4157331571939281870,
    (Point(row=2, col=19), Player.white): 4435688242100879287,
    (Point(row=3, col=1), None): 6087747361058355195,
    (Point(row=3, col=1), Player.black): 128773978795428337,
    (Point(row=3, col=1), Player.white): 1928224379002316303,
    (Point(row=3, col=2), None): 5924242792793373190,
    (Point(row=3, col=2), Player.black): 7715502696661100716,
    (Point(row=3, col=2), Player.white): 3534442841526700391,
    (Point(row=3, col=3), None): 6184983275288484674,
    (Point(row=3, col=3), Player.black): 979493286986678055,
    (Point(row=3, col=3), Player.white): 685808035345435482,
    (Point(row=3, col=4), None): 5268660652633376782,
    (Point(row=3, col=4), Player.black): 4466706176615707705,
    (Point(row=3, col=4), Player.white): 3844509763912163236,
    (Point(row=3, col=5), None): 4073081094810813108,
    (Point(row=3, col=5), Player.black): 3463658293348187931,
    (Point(row=3, col=5), Player.white): 4492431613437565044,
    (Point(row=3, col=6), None): 4878558677301882975,
    (Point(row=3, col=6), Player.black): 5034731528983809640,
    (Point(row=3, col=6), Player.white): 2999401364374348351,
    (Point(row=3, col=7), None): 2214142910750917201,
    (Point(row=3, col=7), Player.black): 1324700614169022007,
    (Point(row=3, col=7), Player.white): 5830469642816100506,
    (Point(row=3, col=8), None): 242250494624690413,
    (Point(row=3, col=8), Player.black): 4975772730167034295,
    (Point(row=3, col=8), Player.white): 7041563746715310482,
    (Point(row=3, col=9), None): 5985524576340430436,
    (Point(row=3, col=9), Player.black): 4111111989659988448,
    (Point(row=3, col=9), Player.white): 1165528629593696508,
    (Point(row=3, col=10), None): 7753957062569755610,
    (Point(row=3, col=10), Player.black): 1553131915113512580,
    (Point(row=3, col=10), Player.white): 4656161018169441654,
    (Point(row=3, col=11), None): 660164440297922579,
    (Point(row=3, col=11), Player.black): 3836430885862708062,
    (Point(row=3, col=11), Player.white): 1644076248725676727,
    (Point(row=3, col=12), None): 5574696790739121068,
    (Point(row=3, col=12), Player.black): 4696858373576619084,
    (Point(row=3, col=12), Player.white): 2081060695344672347,
    (Point(row=3, col=13), None): 2221805376208431300,
    (Point(row=3, col=13), Player.black): 7702978967929618953,
    (Point(row=3, col=13), Player.white): 1414144801376953814,
    (Point(row=3, col=14), None): 6629875559741917338,
    (Point(row=3, col=14), Player.black): 2886270234539694348,
    (Point(row=3, col=14), Player.white): 6879030072145051784,
    (Point(row=3, col=15), None): 4920223170720074220,
    (Point(row=3, col=15), Player.black): 8495749428163139578,
    (Point(row=3, col=15), Player.white): 1350770839549802911,
    (Point(row=3, col=16), None): 316032151960652467,
    (Point(row=3, col=16), Player.black): 4993354923634450486,
    (Point(row=3, col=16), Player.white): 6129860202117392645,
    (Point(row=3, col=17), None): 1570942225796607387,
    (Point(row=3, col=17), Player.black): 6023838934845960254,
    (Point(row=3, col=17), Player.white): 5264287065200344518,
    (Point(row=3, col=18), None): 3506626677640716028,
    (Point(row=3, col=18), Player.black): 6412913976696959838,
    (Point(row=3, col=18), Player.white): 848484703119682044,
    (Point(row=3, col=19), None): 7832481487860493418,
    (Point(row=3, col=19), Player.black): 4638020777934901331,
    (Point(row=3, col=19), Player.white): 5194817635262925231,
    (Point(row=4, col=1), None): 2947575025986496867,
    (Point(row=4, col=1), Player.black): 493144256240060805,
    (Point(row=4, col=1), Player.white): 8016693566715001875,
    (Point(row=4, col=2), None): 632662653649738599,
    (Point(row=4, col=2), Player.black): 711660639648901843,
    (Point(row=4, col=2), Player.white): 2807713682470261971,
    (Point(row=4, col=3), None): 4302015312536709145,
    (Point(row=4, col=3), Player.black): 2335639103709480305,
    (Point(row=4, col=3), Player.white): 2058990493928982477,
    (Point(row=4, col=4), None): 1769205064058601661,
    (Point(row=4, col=4), Player.black): 3158885905749811677,
    (Point(row=4, col=4), Player.white): 4793067796414384877,
    (Point(row=4, col=5), None): 8617996794463444132,
    (Point(row=4, col=5), Player.black): 8072645854836353988,
    (Point(row=4, col=5), Player.white): 7370756395561447043,
    (Point(row=4, col=6), None): 4985392396127246697,
    (Point(row=4, col=6), Player.black): 4364603943272475922,
    (Point(row=4, col=6), Player.white): 5147144461075642175,
    (Point(row=4, col=7), None): 4570669962700358635,
    (Point(row=4, col=7), Player.black): 6735979788777257512,
    (Point(row=4, col=7), Player.white): 3282837049564162517,
    (Point(row=4, col=8), None): 6446930697755010159,
    (Point(row=4, col=8), Player.black): 4391295938621086611,
    (Point(row=4, col=8), Player.white): 7287597299895215491,
    (Point(row=4, col=9), None): 5972331757521479725,
    (Point(row=4, col=9), Player.black): 7777839438475890763,
    (Point(row=4, col=9), Player.white): 5242836387948264263,
    (Point(row=4, col=10), None): 4773020264925948324,
    (Point(row=4, col=10), Player.black): 640842257028445703,
    (Point(row=4, col=10), Player.white): 9004195578731335901,
    (Point(row=4, col=11), None): 6255824161969928655,
    (Point(row=4, col=11), Player.black): 988108791873828552,
    (Point(row=4, col=11), Player.white): 2951762181610237031,
    (Point(row=4, col=12), None): 4423892227930890741,
    (Point(row=4, col=12), Player.black): 2701088664343997337,
    (Point(row=4, col=12), Player.white): 8732353907268095623,
    (Point(row=4, col=13), None): 1517162043102037804,
    (Point(row=4, col=13), Player.black): 1854042224055970142,
    (Point(row=4, col=13), Player.white): 6742887956340237555,
    (Point(row=4, col=14), None): 5478386889508000756,
    (Point(row=4, col=14), Player.black): 154560630651509824,
    (Point(row=4, col=14), Player.white): 4404066432686545852,
    (Point(row=4, col=15), None): 188719891687381432,
    (Point(row=4, col=15), Player.black): 486957934699089169,
    (Point(row=4, col=15), Player.white): 2057791266926106560,
    (Point(row=4, col=16), None): 735999433971620521,
    (Point(row=4, col=16), Player.black): 7417407732147354411,
    (Point(row=4, col=16), Player.white): 2509857767195124601,
    (Point(row=4, col=17), None): 3163533493540073036,
    (Point(row=4, col=17), Player.black): 5463923581676090438,
    (Point(row=4, col=17), Player.white): 6765616316094982686,
    (Point(row=4, col=18), None): 1643213966945004164,
    (Point(row=4, col=18), Player.black): 7354290050664722934,
    (Point(row=4, col=18), Player.white): 7076350285395167063,
    (Point(row=4, col=19), None): 3305708450297178773,
    (Point(row=4, col=19), Player.black): 2375595489514048666,
    (Point(row=4, col=19), Player.white): 1684172933344140340,
    (Point(row=5, col=1), None): 2737204252875704950,
    (Point(row=5, col=1), Player.black): 45755682013417362,
    (Point(row=5, col=1), Player.white): 2302509291931860626,
    (Point(row=5, col=2), None): 5599434705550755910,
    (Point(row=5, col=2), Player.black): 4520353922637165416,
    (Point(row=5, col=2), Player.white): 6598878958612399771,
    (Point(row=5, col=3), None): 3210263398179775254,
    (Point(row=5, col=3), Player.black): 6866887756097203626,
    (Point(row=5, col=3), Player.white): 943686971525037407,
    (Point(row=5, col=4), None): 4500705965429540854,
    (Point(row=5, col=4), Player.black): 1401346350625414349,
    (Point(row=5, col=4), Player.white): 8157056091562970186,
    (Point(row=5, col=5), None): 7750481426291227514,
    (Point(row=5, col=5), Player.black): 5288039906940838687,
    (Point(row=5, col=5), Player.white): 4245425503966826362,
    (Point(row=5, col=6), None): 704780243050880863,
    (Point(row=5, col=6), Player.black): 4788008647896209174,
    (Point(row=5, col=6), Player.white): 7551091912348209872,
    (Point(row=5, col=7), None): 4228791588451722887,
    (Point(row=5, col=7), Player.black): 2774668757564428307,
    (Point(row=5, col=7), Player.white): 5453858963060095122,
    (Point(row=5, col=8), None): 4899223177583611717,
    (Point(row=5, col=8), Player.black): 7674155147752244511,
    (Point(row=5, col=8), Player.white): 2241553938596892377,
    (Point(row=5, col=9), None): 4138274735400772092,
    (Point(row=5, col=9), Player.black): 8017803294189177068,
    (Point(row=5, col=9), Player.white): 7911091455170764999,
    (Point(row=5, col=10), None): 3032717060216287485,
    (Point(row=5, col=10), Player.black): 427174402822095331,
    (Point(row=5, col=10), Player.white): 6496324631361835147,
    (Point(row=5, col=11), None): 1503184785706353977,
    (Point(row=5, col=11), Player.black): 6014754819412753336,
    (Point(row=5, col=11), Player.white): 4318322752777694598,
    (Point(row=5, col=12), None): 1843234806414383046,
    (Point(row=5, col=12), Player.black): 6124913620496969696,
    (Point(row=5, col=12), Player.white): 8276772214055243633,
    (Point(row=5, col=13), None): 5031498287427088842,
    (Point(row=5, col=13), Player.black): 1878656205194279646,
    (Point(row=5, col=13), Player.white): 7711543025327770976,
    (Point(row=5, col=14), None): 1059755887814275436,
    (Point(row=5, col=14), Player.black): 4885264678529058948,
    (Point(row=5, col=14), Player.white): 8783983991599995930,
    (Point(row=5, col=15), None): 5830002438987759238,
    (Point(row=5, col=15), Player.black): 1288646529884954264,
    (Point(row=5, col=15), Player.white): 5914879578018647330,
    (Point(row=5, col=16), None): 6033799285368865845,
    (Point(row=5, col=16), Player.black): 5688407261925211040,
    (Point(row=5, col=16), Player.white): 586171509497279273,
    (Point(row=5, col=17), None): 3689128337057296126,
    (Point(row=5, col=17), Player.black): 8143465936157355776,
    (Point(row=5, col=17), Player.white): 5342253943796373149,
    (Point(row=5, col=18), None): 7432094628563955663,
    (Point(row=5, col=18), Player.black): 3449926392232017533,
    (Point(row=5, col=18), Player.white): 3605333286424796991,
    (Point(row=5, col=19), None): 2436007186267557889,
    (Point(row=5, col=19), Player.black): 498831444427374025,
    (Point(row=5, col=19), Player.white): 449966740782410926,
    (Point(row=6, col=1), None): 2173738740408398051,
    (Point(row=6, col=1), Player.black): 4665393076384757186,
    (Point(row=6, col=1), Player.white): 2536489705870206263,
    (Point(row=6, col=2), None): 6735378889028663720,
    (Point(row=6, col=2), Player.black): 3732820017173774764,
    (Point(row=6, col=2), Player.white): 5379435586985576322,
    (Point(row=6, col=3), None): 3506708988234314627,
    (Point(row=6, col=3), Player.black): 3276262309492553648,
    (Point(row=6, col=3), Player.white): 645566108644451420,
    (Point(row=6, col=4), None): 103245606218658763,
    (Point(row=6, col=4), Player.black): 1991687204280541397,
    (Point(row=6, col=4), Player.white): 1384206078352061712,
    (Point(row=6, col=5), None): 4028823181026344722,
    (Point(row=6, col=5), Player.black): 4858453628202175471,
    (Point(row=6, col=5), Player.white): 4682576323032814039,
    (Point(row=6, col=6), None): 5361000294010050572,
    (Point(row=6, col=6), Player.black): 7896274233846119175,
    (Point(row=6, col=6), Player.white): 4463399506589439901,
    (Point(row=6, col=7), None): 1081381896604169149,
    (Point(row=6, col=7), Player.black): 2455529750462961962,
    (Point(row=6, col=7), Player.white): 2115695100901481136,
    (Point(row=6, col=8), None): 3673371558846305164,
    (Point(row=6, col=8), Player.black): 5933384013872886148,
    (Point(row=6, col=8), Player.white): 8715197248349724823,
    (Point(row=6, col=9), None): 7674508529893311373,
    (Point(row=6, col=9), Player.black): 4261322875651242114,
    (Point(row=6, col=9), Player.white): 7620529671196095025,
    (Point(row=6, col=10), None): 4054250268845064350,
    (Point(row=6, col=10), Player.black): 1242743297552572613,
    (Point(row=6, col=10), Player.white): 8019922257716118745,
    (Point(row=6, col=11), None): 1258576642818705945,
    (Point(row=6, col=11), Player.black): 4634239272672743952,
    (Point(row=6, col=11), Player.white): 3872234285932796133,
    (Point(row=6, col=12), None): 4928133640267010676,
    (Point(row=6, col=12), Player.black): 583592917583633996,
    (Point(row=6, col=12), Player.white): 6295627042831919907,
    (Point(row=6, col=13), None): 1765207215440327458,
    (Point(row=6, col=13), Player.black): 7442303851232245378,
    (Point(row=6, col=13), Player.white): 7400782461534852568,
    (Point(row=6, col=14), None): 7787789407683267450,
    (Point(row=6, col=14), Player.black): 549496212425754972,
    (Point(row=6, col=14), Player.white): 25556843019032285,
    (Point(row=6, col=15), None): 4061617085224837858,
    (Point(row=6, col=15), Player.black): 6315928519201369390,
    (Point(row=6, col=15), Player.white): 5243228597679734601,
    (Point(row=6, col=16), None): 7506245199034016750,
    (Point(row=6, col=16), Player.black): 4119025711383875550,
    (Point(row=6, col=16), Player.white): 384547999513417796,
    (Point(row=6, col=17), None): 4573982426008141117,
    (Point(row=6, col=17), Player.black): 6423567854433706603,
    (Point(row=6, col=17), Player.white): 8463631954049272644,
    (Point(row=6, col=18), None): 7227274896047738310,
    (Point(row=6, col=18), Player.black): 570150522979623279,
    (Point(row=6, col=18), Player.white): 5202607222514309671,
    (Point(row=6, col=19), None): 7863305715136839902,
    (Point(row=6, col=19), Player.black): 8120928684476466013,
    (Point(row=6, col=19), Player.white): 8752084410343898720,
    (Point(row=7, col=1), None): 2725757763464984311,
    (Point(row=7, col=1), Player.black): 2132807973934839751,
    (Point(row=7, col=1), Player.white): 7442226016731511235,
    (Point(row=7, col=2), None): 4354699901935132798,
    (Point(row=7, col=2), Player.black): 7045003500559636445,
    (Point(row=7, col=2), Player.white): 4493194887590566491,
    (Point(row=7, col=3), None): 8567049715663851201,
    (Point(row=7, col=3), Player.black): 7336201546344200999,
    (Point(row=7, col=3), Player.white): 5039789966781813683,
    (Point(row=7, col=4), None): 8267011999572082525,
    (Point(row=7, col=4), Player.black): 4210531376017046692,
    (Point(row=7, col=4), Player.white): 8512226392565163366,
    (Point(row=7, col=5), None): 5305099660623033482,
    (Point(row=7, col=5), Player.black): 264918848526872470,
    (Point(row=7, col=5), Player.white): 6859778237660826564,
    (Point(row=7, col=6), None): 8829056065103468599,
    (Point(row=7, col=6), Player.black): 1468255622574496523,
    (Point(row=7, col=6), Player.white): 2278579396347714375,
    (Point(row=7, col=7), None): 8111051732785336493,
    (Point(row=7, col=7), Player.black): 3466897690214289977,
    (Point(row=7, col=7), Player.white): 9154213988004818228,
    (Point(row=7, col=8), None): 1205117856153879602,
    (Point(row=7, col=8), Player.black): 7640028311729648167,
    (Point(row=7, col=8), Player.white): 8315897391576062890,
    (Point(row=7, col=9), None): 4457914814175493942,
    (Point(row=7, col=9), Player.black): 2113677560585370194,
    (Point(row=7, col=9), Player.white): 3484047555951895872,
    (Point(row=7, col=10), None): 5933503270835911249,
    (Point(row=7, col=10), Player.black): 3739542004460774078,
    (Point(row=7, col=10), Player.white): 6744100637413056020,
    (Point(row=7, col=11), None): 5658327829211244547,
    (Point(row=7, col=11), Player.black): 6529398888785673905,
    (Point(row=7, col=11), Player.white): 5271496303956840432,
    (Point(row=7, col=12), None): 5831620588092795762,
    (Point(row=7, col=12), Player.black): 3310879154785341703,
    (Point(row=7, col=12), Player.white): 8614792809531091536,
    (Point(row=7, col=13), None): 3029023304173039584,
    (Point(row=7, col=13), Player.black): 5504273876145842072,
    (Point(row=7, col=13), Player.white): 1855344039548726968,
    (Point(row=7, col=14), None): 4686443047156012063,
    (Point(row=7, col=14), Player.black): 7235139171180801308,
    (Point(row=7, col=14), Player.white): 2303536185274333106,
    (Point(row=7, col=15), None): 5139330220549730019,
    (Point(row=7, col=15), Player.black): 843572316152719581,
    (Point(row=7, col=15), Player.white): 5530693685903566296,
    (Point(row=7, col=16), None): 2801621146940987454,
    (Point(row=7, col=16), Player.black): 5923455446620916512,
    (Point(row=7, col=16), Player.white): 2219076344047400233,
    (Point(row=7, col=17), None): 4744216321226893551,
    (Point(row=7, col=17), Player.black): 5038157195586834603,
    (Point(row=7, col=17), Player.white): 1845660578636719935,
    (Point(row=7, col=18), None): 5302128402373857496,
    (Point(row=7, col=18), Player.black): 1289989143109851764,
    (Point(row=7, col=18), Player.white): 7924824851619329812,
    (Point(row=7, col=19), None): 3569627370236803230,
    (Point(row=7, col=19), Player.black): 5734788842719031890,
    (Point(row=7, col=19), Player.white): 3685000032210373900,
    (Point(row=8, col=1), None): 6418264982907873739,
    (Point(row=8, col=1), Player.black): 3726460367447316962,
    (Point(row=8, col=1), Player.white): 7542397498544597971,
    (Point(row=8, col=2), None): 3590504161512614767,
    (Point(row=8, col=2), Player.black): 6737745783802557907,
    (Point(row=8, col=2), Player.white): 4846566052296042342,
    (Point(row=8, col=3), None): 808032272768171566,
    (Point(row=8, col=3), Player.black): 373791415098530678,
    (Point(row=8, col=3), Player.white): 2658078847849035002,
    (Point(row=8, col=4), None): 6191058364073799215,
    (Point(row=8, col=4), Player.black): 1994504006615303205,
    (Point(row=8, col=4), Player.white): 2234339176323322741,
    (Point(row=8, col=5), None): 2128302496285178785,
    (Point(row=8, col=5), Player.black): 5202616071984915501,
    (Point(row=8, col=5), Player.white): 8438857553468806897,
    (Point(row=8, col=6), None): 9070718934283950848,
    (Point(row=8, col=6), Player.black): 1153127874599712090,
    (Point(row=8, col=6), Player.white): 3598188494696337539,
    (Point(row=8, col=7), None): 4652623937964105991,
    (Point(row=8, col=7), Player.black): 7882731175378018582,
    (Point(row=8, col=7), Player.white): 1275913977002097144,
    (Point(row=8, col=8), None): 6737197663410065966,
    (Point(row=8, col=8), Player.black): 3267323250994527221,
    (Point(row=8, col=8), Player.white): 180519266395437990,
    (Point(row=8, col=9), None): 7079725986128857343,
    (Point(row=8, col=9), Player.black): 9167413862284557078,
    (Point(row=8, col=9), Player.white): 3580456999751900917,
    (Point(row=8, col=10), None): 2693047555035266224,
    (Point(row=8, col=10), Player.black): 4953917673219598393,
    (Point(row=8, col=10), Player.white): 5342335254264005610,
    (Point(row=8, col=11), None): 9132476477694523755,
    (Point(row=8, col=11), Player.black): 4039979718049572746,
    (Point(row=8, col=11), Player.white): 4402961578569043804,
    (Point(row=8, col=12), None): 8415162379237983833,
    (Point(row=8, col=12), Player.black): 7689841173881182646,
    (Point(row=8, col=12), Player.white): 806081900131147748,
    (Point(row=8, col=13), None): 6288088846874122253,
    (Point(row=8, col=13), Player.black): 5124174808680703277,
    (Point(row=8, col=13), Player.white): 6596992103676294895,
    (Point(row=8, col=14), None): 6666805614214122325,
    (Point(row=8, col=14), Player.black): 2371243475260289454,
    (Point(row=8, col=14), Player.white): 6232015089852024804,
    (Point(row=8, col=15), None): 3175374051180751572,
    (Point(row=8, col=15), Player.black): 4633089288807487713,
    (Point(row=8, col=15), Player.white): 4653800971740985106,
    (Point(row=8, col=16), None): 4668169880544807736,
    (Point(row=8, col=16), Player.black): 1337783968789848297,
    (Point(row=8, col=16), Player.white): 9092241543865760803,
    (Point(row=8, col=17), None): 3631157650453265381,
    (Point(row=8, col=17), Player.black): 7912376285707166859,
    (Point(row=8, col=17), Player.white): 4478024833819478573,
    (Point(row=8, col=18), None): 272118417501931852,
    (Point(row=8, col=18), Player.black): 3116175634508120705,
    (Point(row=8, col=18), Player.white): 9181234785725282257,
    (Point(row=8, col=19), None): 592003013716137921,
    (Point(row=8, col=19), Player.black): 6552963506268994825,
    (Point(row=8, col=19), Player.white): 6769493853608350726,
    (Point(row=9, col=1), None): 1418275208935359053,
    (Point(row=9, col=1), Player.black): 332603946577160980,
    (Point(row=9, col=1), Player.white): 6660495066308467726,
    (Point(row=9, col=2), None): 4105492608546461333,
    (Point(row=9, col=2), Player.black): 2456324036341728622,
    (Point(row=9, col=2), Player.white): 3736866397813927958,
    (Point(row=9, col=3), None): 6444569304270920908,
    (Point(row=9, col=3), Player.black): 8405364911897534624,
    (Point(row=9, col=3), Player.white): 4906928737313095627,
    (Point(row=9, col=4), None): 2399483855621787118,
    (Point(row=9, col=4), Player.black): 2794022724871234260,
    (Point(row=9, col=4), Player.white): 1581837394846677449,
    (Point(row=9, col=5), None): 7628372958342377135,
    (Point(row=9, col=5), Player.black): 4764654009992320406,
    (Point(row=9, col=5), Player.white): 7542901296226671868,
    (Point(row=9, col=6), None): 2579763795636246440,
    (Point(row=9, col=6), Player.black): 9094604045432033153,
    (Point(row=9, col=6), Player.white): 3668129583279350159,
    (Point(row=9, col=7), None): 7475374518737556414,
    (Point(row=9, col=7), Player.black): 4190046680666963410,
    (Point(row=9, col=7), Player.white): 2395463540609400721,
    (Point(row=9, col=8), None): 4350410455935396126,
    (Point(row=9, col=8), Player.black): 1881456575971873987,
    (Point(row=9, col=8), Player.white): 2976365119932553950,
    (Point(row=9, col=9), None): 1263398944645734255,
    (Point(row=9, col=9), Player.black): 7074761764475804254,
    (Point(row=9, col=9), Player.white): 5042257350876402528,
    (Point(row=9, col=10), None): 2217335637649232047,
    (Point(row=9, col=10), Player.black): 5260049927323382627,
    (Point(row=9, col=10), Player.white): 3151958695483557785,
    (Point(row=9, col=11), None): 1586452570977004825,
    (Point(row=9, col=11), Player.black): 4022138289524765615,
    (Point(row=9, col=11), Player.white): 6350036201756837499,
    (Point(row=9, col=12), None): 9070404760457435009,
    (Point(row=9, col=12), Player.black): 6989013039269247631,
    (Point(row=9, col=12), Player.white): 8988015420288719113,
    (Point(row=9, col=13), None): 7820613740441605108,
    (Point(row=9, col=13), Player.black): 8929753920145660801,
    (Point(row=9, col=13), Player.white): 2944996824568337071,
    (Point(row=9, col=14), None): 7545013395372940462,
    (Point(row=9, col=14), Player.black): 7433816439134621272,
    (Point(row=9, col=14), Player.white): 5023261232538793736,
    (Point(row=9, col=15), None): 3126407811618347685,
    (Point(row=9, col=15), Player.black): 1409798412261681499,
    (Point(row=9, col=15), Player.white): 4857047763242438625,
    (Point(row=9, col=16), None): 1844186529549204435,
    (Point(row=9, col=16), Player.black): 1305219267461031490,
    (Point(row=9, col=16), Player.white): 2197931088739006754,
    (Point(row=9, col=17), None): 6230509502829468742,
    (Point(row=9, col=17), Player.black): 6074267757209423878,
    (Point(row=9, col=17), Player.white): 3551568090532648168,
    (Point(row=9, col=18), None): 1089679889897704113,
    (Point(row=9, col=18), Player.black): 5663930491463859110,
    (Point(row=9, col=18), Player.white): 8938931903050159289,
    (Point(row=9, col=19), None): 8568064649494534007,
    (Point(row=9, col=19), Player.black): 1812424030805242134,
    (Point(row=9, col=19), Player.white): 1423244571802272411,
    (Point(row=10, col=1), None): 1521638820106444324,
    (Point(row=10, col=1), Player.black): 5320093946376038785,
    (Point(row=10, col=1), Player.white): 8058052970492933669,
    (Point(row=10, col=2), None): 3274640314093324993,
    (Point(row=10, col=2), Player.black): 8653895836014833359,
    (Point(row=10, col=2), Player.white): 5679340943863721795,
    (Point(row=10, col=3), None): 5859115878970833882,
    (Point(row=10, col=3), Player.black): 8185523390051238509,
    (Point(row=10, col=3), Player.white): 4615248644304962457,
    (Point(row=10, col=4), None): 6002066814374149962,
    (Point(row=10, col=4), Player.black): 9052125320216351662,
    (Point(row=10, col=4), Player.white): 4210194132027736262,
    (Point(row=10, col=5), None): 5144996275038030066,
    (Point(row=10, col=5), Player.black): 5758566922435928709,
    (Point(row=10, col=5), Player.white): 1653634319987509444,
    (Point(row=10, col=6), None): 3454343484845737546,
    (Point(row=10, col=6), Player.black): 3503597216644304092,
    (Point(row=10, col=6), Player.white): 3354988246339305403,
    (Point(row=10, col=7), None): 5243742649440044608,
    (Point(row=10, col=7), Player.black): 933612205038060031,
    (Point(row=10, col=7), Player.white): 6790016243096917378,
    (Point(row=10, col=8), None): 6782107044470542190,
    (Point(row=10, col=8), Player.black): 6579542531325860684,
    (Point(row=10, col=8), Player.white): 8724103071131668421,
    (Point(row=10, col=9), None): 5933599962134993673,
    (Point(row=10, col=9), Player.black): 6196421710246618144,
    (Point(row=10, col=9), Player.white): 3008556409768438945,
    (Point(row=10, col=10), None): 1486544174696197175,
    (Point(row=10, col=10), Player.black): 4212288249208903214,
    (Point(row=10, col=10), Player.white): 7918519988377072445,
    (Point(row=10, col=11), None): 6000893213128650841,
    (Point(row=10, col=11), Player.black): 2526118690601747525,
    (Point(row=10, col=11), Player.white): 330592007937867773,
    (Point(row=10, col=12), None): 7253867059249992126,
    (Point(row=10, col=12), Player.black): 6838034690572847128,
    (Point(row=10, col=12), Player.white): 4075411952484225146,
    (Point(row=10, col=13), None): 5660607092689494996,
    (Point(row=10, col=13), Player.black): 5215863743413950615,
    (Point(row=10, col=13), Player.white): 1247474538405952572,
    (Point(row=10, col=14), None): 444423466051184955,
    (Point(row=10, col=14), Player.black): 2727989087262035896,
    (Point(row=10, col=14), Player.white): 7268290769033195062,
    (Point(row=10, col=15), None): 8686266622190965864,
    (Point(row=10, col=15), Player.black): 4626125606515150500,
    (Point(row=10, col=15), Player.white): 6581291367246891400,
    (Point(row=10, col=16), None): 1971825384778872947,
    (Point(row=10, col=16), Player.black): 1240935362270823923,
    (Point(row=10, col=16), Player.white): 3504018170463589085,
    (Point(row=10, col=17), None): 283073156001167599,
    (Point(row=10, col=17), Player.black): 4920423938795260527,
    (Point(row=10, col=17), Player.white): 3702102821474615764,
    (Point(row=10, col=18), None): 10764727266210374,
    (Point(row=10, col=18), Player.black): 649117595221133957,
    (Point(row=10, col=18), Player.white): 2588110298780108191,
    (Point(row=10, col=19), None): 4664284582093560576,
    (Point(row=10, col=19), Player.black): 1939998518153080863,
    (Point(row=10, col=19), Player.white): 4427007428091790253,
    (Point(row=11, col=1), None): 5348062519783152455,
    (Point(row=11, col=1), Player.black): 5996392361432254825,
    (Point(row=11, col=1), Player.white): 4422578214905101422,
    (Point(row=11, col=2), None): 5809864552148767385,
    (Point(row=11, col=2), Player.black): 7210131100602837507,
    (Point(row=11, col=2), Player.white): 5868362121548963462,
    (Point(row=11, col=3), None): 5802681260874260921,
    (Point(row=11, col=3), Player.black): 8686965080754872810,
    (Point(row=11, col=3), Player.white): 2485054442760459904,
    (Point(row=11, col=4), None): 7773519911872136726,
    (Point(row=11, col=4), Player.black): 586261577628141812,
    (Point(row=11, col=4), Player.white): 5881695887327119569,
    (Point(row=11, col=5), None): 5633428494282673298,
    (Point(row=11, col=5), Player.black): 3338252750426072785,
    (Point(row=11, col=5), Player.white): 6126999987325839737,
    (Point(row=11, col=6), None): 2557333486793652741,
    (Point(row=11, col=6), Player.black): 7328288244285524556,
    (Point(row=11, col=6), Player.white): 6174063470268583759,
    (Point(row=11, col=7), None): 1560394352721174255,
    (Point(row=11, col=7), Player.black): 1377490540295307177,
    (Point(row=11, col=7), Player.white): 2367385626131998382,
    (Point(row=11, col=8), None): 7726002492454753637,
    (Point(row=11, col=8), Player.black): 1231652342866699614,
    (Point(row=11, col=8), Player.white): 3761737736053096007,
    (Point(row=11, col=9), None): 5852952203382004214,
    (Point(row=11, col=9), Player.black): 285046196431026167,
    (Point(row=11, col=9), Player.white): 6557081050594727387,
    (Point(row=11, col=10), None): 4654797875985344042,
    (Point(row=11, col=10), Player.black): 7804680178556030651,
    (Point(row=11, col=10), Player.white): 6675617189426752806,
    (Point(row=11, col=11), None): 6100345448525787815,
    (Point(row=11, col=11), Player.black): 1915235819964278617,
    (Point(row=11, col=11), Player.white): 9191984496891122238,
    (Point(row=11, col=12), None): 1878420641764065625,
    (Point(row=11, col=12), Player.black): 6137310556075607284,
    (Point(row=11, col=12), Player.white): 2420925702589935557,
    (Point(row=11, col=13), None): 7597683476946674958,
    (Point(row=11, col=13), Player.black): 7076356306204632859,
    (Point(row=11, col=13), Player.white): 3394937759238788993,
    (Point(row=11, col=14), None): 5416712422844281075,
    (Point(row=11, col=14), Player.black): 6810585850200510265,
    (Point(row=11, col=14), Player.white): 5353788091350909232,
    (Point(row=11, col=15), None): 1465472523125987178,
    (Point(row=11, col=15), Player.black): 3394238421020544539,
    (Point(row=11, col=15), Player.white): 7924173482485228708,
    (Point(row=11, col=16), None): 5538593761321123038,
    (Point(row=11, col=16), Player.black): 7384937168207385976,
    (Point(row=11, col=16), Player.white): 6713483607315196923,
    (Point(row=11, col=17), None): 3849621019399972664,
    (Point(row=11, col=17), Player.black): 2195228292668049082,
    (Point(row=11, col=17), Player.white): 4244984086681678539,
    (Point(row=11, col=18), None): 8092462746193724428,
    (Point(row=11, col=18), Player.black): 4697807953211357257,
    (Point(row=11, col=18), Player.white): 2216286540540928267,
    (Point(row=11, col=19), None): 6855415231994608505,
    (Point(row=11, col=19), Player.black): 384020625329842017,
    (Point(row=11, col=19), Player.white): 3644274131863034297,
    (Point(row=12, col=1), None): 998266040215183433,
    (Point(row=12, col=1), Player.black): 5464654337676894640,
    (Point(row=12, col=1), Player.white): 8258236414019485276,
    (Point(row=12, col=2), None): 8447771965457565260,
    (Point(row=12, col=2), Player.black): 8559262682736118878,
    (Point(row=12, col=2), Player.white): 6136999892594372064,
    (Point(row=12, col=3), None): 5067502027298995866,
    (Point(row=12, col=3), Player.black): 8109691821743492636,
    (Point(row=12, col=3), Player.white): 7115711312243220712,
    (Point(row=12, col=4), None): 6424609509065218258,
    (Point(row=12, col=4), Player.black): 924558142139415266,
    (Point(row=12, col=4), Player.white): 3875408167823154717,
    (Point(row=12, col=5), None): 2858776142792028668,
    (Point(row=12, col=5), Player.black): 3592624158473093074,
    (Point(row=12, col=5), Player.white): 1749602571513763862,
    (Point(row=12, col=6), None): 3700681629513930011,
    (Point(row=12, col=6), Player.black): 9161329144303995900,
    (Point(row=12, col=6), Player.white): 4014126085449648120,
    (Point(row=12, col=7), None): 6510987909775895608,
    (Point(row=12, col=7), Player.black): 8295072048558129887,
    (Point(row=12, col=7), Player.white): 4722284033964037165,
    (Point(row=12, col=8), None): 407580790861275507,
    (Point(row=12, col=8), Player.black): 377240960993310941,
    (Point(row=12, col=8), Player.white): 5332553753533207458,
    (Point(row=12, col=9), None): 1982889657249375625,
    (Point(row=12, col=9), Player.black): 8471225795558223533,
    (Point(row=12, col=9), Player.white): 2685712622984157564,
    (Point(row=12, col=10), None): 8897828432946565039,
    (Point(row=12, col=10), Player.black): 4116651642558502485,
    (Point(row=12, col=10), Player.white): 5497820928006536147,
    (Point(row=12, col=11), None): 8897534589018663185,
    (Point(row=12, col=11), Player.black): 835955248229356043,
    (Point(row=12, col=11), Player.white): 6649611640528669463,
    (Point(row=12, col=12), None): 5856998575319238055,
    (Point(row=12, col=12), Player.black): 7006475030081690394,
    (Point(row=12, col=12), Player.white): 4305234555713021441,
    (Point(row=12, col=13), None): 6469508109431937439,
    (Point(row=12, col=13), Player.black): 5904330391822003401,
    (Point(row=12, col=13), Player.white): 5122779117758642967,
    (Point(row=12, col=14), None): 4147588778267983249,
    (Point(row=12, col=14), Player.black): 3511642388707940942,
    (Point(row=12, col=14), Player.white): 8639687657969852123,
    (Point(row=12, col=15), None): 4605687578288735090,
    (Point(row=12, col=15), Player.black): 9003978416941095284,
    (Point(row=12, col=15), Player.white): 1006408344912000908,
    (Point(row=12, col=16), None): 8294404297648394263,
    (Point(row=12, col=16), Player.black): 8769382189639842815,
    (Point(row=12, col=16), Player.white): 65086622567418587,
    (Point(row=12, col=17), None): 2035240250413259383,
    (Point(row=12, col=17), Player.black): 3332491981310133841,
    (Point(row=12, col=17), Player.white): 7990595090759962176,
    (Point(row=12, col=18), None): 1045910823761562679,
    (Point(row=12, col=18), Player.black): 6153957221184064614,
    (Point(row=12, col=18), Player.white): 627042695898267284,
    (Point(row=12, col=19), None): 439033462800838100,
    (Point(row=12, col=19), Player.black): 6481474465169496417,
    (Point(row=12, col=19), Player.white): 6125386700356467221,
    (Point(row=13, col=1), None): 1656143693882853038,
    (Point(row=13, col=1), Player.black): 247278101578381892,
    (Point(row=13, col=1), Player.white): 4759096882029768646,
    (Point(row=13, col=2), None): 275073180837234040,
    (Point(row=13, col=2), Player.black): 5192049507093795500,
    (Point(row=13, col=2), Player.white): 8233932480584390371,
    (Point(row=13, col=3), None): 5298741549504263194,
    (Point(row=13, col=3), Player.black): 8110135987716169336,
    (Point(row=13, col=3), Player.white): 6251427400749291356,
    (Point(row=13, col=4), None): 1074759670397652237,
    (Point(row=13, col=4), Player.black): 4430251706685945624,
    (Point(row=13, col=4), Player.white): 1689834731999885385,
    (Point(row=13, col=5), None): 9153847317880510527,
    (Point(row=13, col=5), Player.black): 2157577701866203459,
    (Point(row=13, col=5), Player.white): 1726522497041541857,
    (Point(row=13, col=6), None): 9126015518336780980,
    (Point(row=13, col=6), Player.black): 791283340431100062,
    (Point(row=13, col=6), Player.white): 8726409939392712790,
    (Point(row=13, col=7), None): 343357643687728789,
    (Point(row=13, col=7), Player.black): 6255252026589550318,
    (Point(row=13, col=7), Player.white): 6010197514708794231,
    (Point(row=13, col=8), None): 7218249684049571269,
    (Point(row=13, col=8), Player.black): 2008718218582480587,
    (Point(row=13, col=8), Player.white): 7292689293357601532,
    (Point(row=13, col=9), None): 5815441573982267917,
    (Point(row=13, col=9), Player.black): 5534352345857055954,
    (Point(row=13, col=9), Player.white): 1009847422559103932,
    (Point(row=13, col=10), None): 3211999501121372946,
    (Point(row=13, col=10), Player.black): 5293683797810235119,
    (Point(row=13, col=10), Player.white): 5644170193541080142,
    (Point(row=13, col=11), None): 2784160896006056703,
    (Point(row=13, col=11), Player.black): 3193406078526993791,
    (Point(row=13, col=11), Player.white): 402509365431834653,
    (Point(row=13, col=12), None): 4791826719391770873,
    (Point(row=13, col=12), Player.black): 6207666807461479134,
    (Point(row=13, col=12), Player.white): 5307511360769591647,
    (Point(row=13, col=13), None): 2381145397860260949,
    (Point(row=13, col=13), Player.black): 4681685013420754604,
    (Point(row=13, col=13), Player.white): 4943565317851368354,
    (Point(row=13, col=14), None): 1877254066388823295,
    (Point(row=13, col=14), Player.black): 1129946990074563131,
    (Point(row=13, col=14), Player.white): 5781552052665213792,
    (Point(row=13, col=15), None): 9150964979341862880,
    (Point(row=13, col=15), Player.black): 6514523517087165609,
    (Point(row=13, col=15), Player.white): 1274889244461580649,
    (Point(row=13, col=16), None): 5825915384047667523,
    (Point(row=13, col=16), Player.black): 2830195534957136697,
    (Point(row=13, col=16), Player.white): 8472333163318175708,
    (Point(row=13, col=17), None): 403055848092342882,
    (Point(row=13, col=17), Player.black): 1184628281060168358,
    (Point(row=13, col=17), Player.white): 4513080377490388901,
    (Point(row=13, col=18), None): 6477104116260386124,
    (Point(row=13, col=18), Player.black): 8428325981815792159,
    (Point(row=13, col=18), Player.white): 8659702572306915125,
    (Point(row=13, col=19), None): 978750003773637313,
    (Point(row=13, col=19), Player.black): 5267072736842939674,
    (Point(row=13, col=19), Player.white): 7449402229013560656,
    (Point(row=14, col=1), None): 7551828168849153751,
    (Point(row=14, col=1), Player.black): 3401118035834791741,
    (Point(row=14, col=1), Player.white): 5777405478278921707,
    (Point(row=14, col=2), None): 4291543908470633818,
    (Point(row=14, col=2), Player.black): 6062830291466411678,
    (Point(row=14, col=2), Player.white): 4225406681215218852,
    (Point(row=14, col=3), None): 5319213614676160611,
    (Point(row=14, col=3), Player.black): 4426389390046124101,
    (Point(row=14, col=3), Player.white): 8649037890261688365,
    (Point(row=14, col=4), None): 8065326951452886791,
    (Point(row=14, col=4), Player.black): 6987946368160679122,
    (Point(row=14, col=4), Player.white): 3020437074238876203,
    (Point(row=14, col=5), None): 7339347534036755011,
    (Point(row=14, col=5), Player.black): 9170736908319707667,
    (Point(row=14, col=5), Player.white): 8157716472308239765,
    (Point(row=14, col=6), None): 9127591636991004115,
    (Point(row=14, col=6), Player.black): 8553988984151679985,
    (Point(row=14, col=6), Player.white): 3595760737797885503,
    (Point(row=14, col=7), None): 1896388225362279120,
    (Point(row=14, col=7), Player.black): 3388393064217003987,
    (Point(row=14, col=7), Player.white): 5982924053750156430,
    (Point(row=14, col=8), None): 8488955562486628728,
    (Point(row=14, col=8), Player.black): 4430149526543853589,
    (Point(row=14, col=8), Player.white): 589358262895497862,
    (Point(row=14, col=9), None): 5094885697468763828,
    (Point(row=14, col=9), Player.black): 3924875976814968297,
    (Point(row=14, col=9), Player.white): 4942665333157821234,
    (Point(row=14, col=10), None): 1853765541778675567,
    (Point(row=14, col=10), Player.black): 5157776988038317631,
    (Point(row=14, col=10), Player.white): 8894139698979471552,
    (Point(row=14, col=11), None): 8276276752242437094,
    (Point(row=14, col=11), Player.black): 1712434757353801480,
    (Point(row=14, col=11), Player.white): 4430875325437008132,
    (Point(row=14, col=12), None): 633211671489224297,
    (Point(row=14, col=12), Player.black): 2423972347987555636,
    (Point(row=14, col=12), Player.white): 4982003464785248113,
    (Point(row=14, col=13), None): 1455897010152965212,
    (Point(row=14, col=13), Player.black): 5990676008476260550,
    (Point(row=14, col=13), Player.white): 5948555690484532858,
    (Point(row=14, col=14), None): 45571391617678556,
    (Point(row=14, col=14), Player.black): 5891862584535141559,
    (Point(row=14, col=14), Player.white): 1655958229996472327,
    (Point(row=14, col=15), None): 7201995285566814564,
    (Point(row=14, col=15), Player.black): 1164434582398556396,
    (Point(row=14, col=15), Player.white): 9137252823921928857,
    (Point(row=14, col=16), None): 8398812954491651707,
    (Point(row=14, col=16), Player.black): 7158380753572660517,
    (Point(row=14, col=16), Player.white): 2919600128219603548,
    (Point(row=14, col=17), None): 2638364743456066939,
    (Point(row=14, col=17), Player.black): 4754547756158887302,
    (Point(row=14, col=17), Player.white): 3683865529495517349,
    (Point(row=14, col=18), None): 2763947302778301266,
    (Point(row=14, col=18), Player.black): 7982191564416298564,
    (Point(row=14, col=18), Player.white): 5724108146299245994,
    (Point(row=14, col=19), None): 5029224255005275855,
    (Point(row=14, col=19), Player.black): 8369981889629046893,
    (Point(row=14, col=19), Player.white): 2106229158156248332,
    (Point(row=15, col=1), None): 3695814377337407650,
    (Point(row=15, col=1), Player.black): 2824765415531952878,
    (Point(row=15, col=1), Player.white): 4304376583012719009,
    (Point(row=15, col=2), None): 559440285168245620,
    (Point(row=15, col=2), Player.black): 2829198594161735723,
    (Point(row=15, col=2), Player.white): 3681073675191092315,
    (Point(row=15, col=3), None): 7958035312199534015,
    (Point(row=15, col=3), Player.black): 2744463086825769409,
    (Point(row=15, col=3), Player.white): 1307789817599072517,
    (Point(row=15, col=4), None): 8292626046000801061,
    (Point(row=15, col=4), Player.black): 499288175507925346,
    (Point(row=15, col=4), Player.white): 2767303834909169069,
    (Point(row=15, col=5), None): 2768015215358729492,
    (Point(row=15, col=5), Player.black): 1900476276820973409,
    (Point(row=15, col=5), Player.white): 6000617549740611128,
    (Point(row=15, col=6), None): 190127789512067484,
    (Point(row=15, col=6), Player.black): 476506784555826453,
    (Point(row=15, col=6), Player.white): 7841992253484654488,
    (Point(row=15, col=7), None): 6064717872149114589,
    (Point(row=15, col=7), Player.black): 5025657037185572036,
    (Point(row=15, col=7), Player.white): 1593025057691383167,
    (Point(row=15, col=8), None): 8889043158614408017,
    (Point(row=15, col=8), Player.black): 1344241588881809433,
    (Point(row=15, col=8), Player.white): 7436388024531754317,
    (Point(row=15, col=9), None): 3316941732766980859,
    (Point(row=15, col=9), Player.black): 8693436778635940057,
    (Point(row=15, col=9), Player.white): 4222451007888114449,
    (Point(row=15, col=10), None): 2856934085838021984,
    (Point(row=15, col=10), Player.black): 8269178505160279305,
    (Point(row=15, col=10), Player.white): 2708925433670574812,
    (Point(row=15, col=11), None): 1816577702794068821,
    (Point(row=15, col=11), Player.black): 699628081286636611,
    (Point(row=15, col=11), Player.white): 4774438318290499046,
    (Point(row=15, col=12), None): 2519577279611409858,
    (Point(row=15, col=12), Player.black): 9098570826037071490,
    (Point(row=15, col=12), Player.white): 4525792468928396876,
    (Point(row=15, col=13), None): 152567039000779306,
    (Point(row=15, col=13), Player.black): 6632833182873019743,
    (Point(row=15, col=13), Player.white): 8296968868767209078,
    (Point(row=15, col=14), None): 1179731223239320298,
    (Point(row=15, col=14), Player.black): 6417527581079112602,
    (Point(row=15, col=14), Player.white): 2735412218078816203,
    (Point(row=15, col=15), None): 7158904931281848290,
    (Point(row=15, col=15), Player.black): 3037990753756932057,
    (Point(row=15, col=15), Player.white): 2575142184971188782,
    (Point(row=15, col=16), None): 7954312537263882514,
    (Point(row=15, col=16), Player.black): 4853786914859126714,
    (Point(row=15, col=16), Player.white): 871491622534020517,
    (Point(row=15, col=17), None): 845639277023479984,
    (Point(row=15, col=17), Player.black): 3004498214503789471,
    (Point(row=15, col=17), Player.white): 7475105201999176790,
    (Point(row=15, col=18), None): 8326145418908984949,
    (Point(row=15, col=18), Player.black): 638223301657396582,
    (Point(row=15, col=18), Player.white): 7870543091117240104,
    (Point(row=15, col=19), None): 1901824973311358564,
    (Point(row=15, col=19), Player.black): 6025637348477202710,
    (Point(row=15, col=19), Player.white): 6021279260637212889,
    (Point(row=16, col=1), None): 63418289697342000,
    (Point(row=16, col=1), Player.black): 6005308587574209253,
    (Point(row=16, col=1), Player.white): 141815923476575382,
    (Point(row=16, col=2), None): 7520279425792732521,
    (Point(row=16, col=2), Player.black): 4678350554899237929,
    (Point(row=16, col=2), Player.white): 99914903149182931,
    (Point(row=16, col=3), None): 8045555575212985725,
    (Point(row=16, col=3), Player.black): 1868134992371030578,
    (Point(row=16, col=3), Player.white): 4877324281340396360,
    (Point(row=16, col=4), None): 138790162492422340,
    (Point(row=16, col=4), Player.black): 2965499348454622600,
    (Point(row=16, col=4), Player.white): 2120530813701809613,
    (Point(row=16, col=5), None): 2862051214406236770,
    (Point(row=16, col=5), Player.black): 7102132810509293011,
    (Point(row=16, col=5), Player.white): 6716795891908952129,
    (Point(row=16, col=6), None): 8736274202494929061,
    (Point(row=16, col=6), Player.black): 5238685826782945619,
    (Point(row=16, col=6), Player.white): 5754571568307836913,
    (Point(row=16, col=7), None): 4026482809138750750,
    (Point(row=16, col=7), Player.black): 1551452668457118015,
    (Point(row=16, col=7), Player.white): 7606007004673553992,
    (Point(row=16, col=8), None): 6696906349599937159,
    (Point(row=16, col=8), Player.black): 2796370176184006406,
    (Point(row=16, col=8), Player.white): 3367545440607911013,
    (Point(row=16, col=9), None): 7818293396446702093,
    (Point(row=16, col=9), Player.black): 7261741847385437316,
    (Point(row=16, col=9), Player.white): 1431062183305205963,
    (Point(row=16, col=10), None): 5699557428305720979,
    (Point(row=16, col=10), Player.black): 5526148479484615913,
    (Point(row=16, col=10), Player.white): 8432838145730234481,
    (Point(row=16, col=11), None): 2857371703149257273,
    (Point(row=16, col=11), Player.black): 6528548906295531905,
    (Point(row=16, col=11), Player.white): 8952441312316475632,
    (Point(row=16, col=12), None): 7108335889521371102,
    (Point(row=16, col=12), Player.black): 1698277204516027072,
    (Point(row=16, col=12), Player.white): 3992252510507940498,
    (Point(row=16, col=13), None): 2715422982171936936,
    (Point(row=16, col=13), Player.black): 5831441303878268071,
    (Point(row=16, col=13), Player.white): 5294265204337034868,
    (Point(row=16, col=14), None): 5664653410221961425,
    (Point(row=16, col=14), Player.black): 7523931257761030857,
    (Point(row=16, col=14), Player.white): 2572398946643828712,
    (Point(row=16, col=15), None): 2029722322765667601,
    (Point(row=16, col=15), Player.black): 8227181148418565161,
    (Point(row=16, col=15), Player.white): 5087635102086817660,
    (Point(row=16, col=16), None): 3742344294226756567,
    (Point(row=16, col=16), Player.black): 5830524854178236548,
    (Point(row=16, col=16), Player.white): 7899644578742902204,
    (Point(row=16, col=17), None): 4572375874718002489,
    (Point(row=16, col=17), Player.black): 1945206792180120307,
    (Point(row=16, col=17), Player.white): 4012542965825901256,
    (Point(row=16, col=18), None): 5499090110254866725,
    (Point(row=16, col=18), Player.black): 3180688156321952190,
    (Point(row=16, col=18), Player.white): 1743586980736794016,
    (Point(row=16, col=19), None): 5758216237824441823,
    (Point(row=16, col=19), Player.black): 8427133184213264711,
    (Point(row=16, col=19), Player.white): 6114165880103072183,
    (Point(row=17, col=1), None): 8441806805330595190,
    (Point(row=17, col=1), Player.black): 3697378558286727481,
    (Point(row=17, col=1), Player.white): 1479509984884809730,
    (Point(row=17, col=2), None): 9020951479611472876,
    (Point(row=17, col=2), Player.black): 7700376692920090830,
    (Point(row=17, col=2), Player.white): 1096357954505791250,
    (Point(row=17, col=3), None): 1653321346115170208,
    (Point(row=17, col=3), Player.black): 1987753975823026539,
    (Point(row=17, col=3), Player.white): 7166715719772757904,
    (Point(row=17, col=4), None): 7499965069729015256,
    (Point(row=17, col=4), Player.black): 4199189251700530595,
    (Point(row=17, col=4), Player.white): 7500622874895058204,
    (Point(row=17, col=5), None): 3445427540165637015,
    (Point(row=17, col=5), Player.black): 5995390733349708105,
    (Point(row=17, col=5), Player.white): 3148744511271582542,
    (Point(row=17, col=6), None): 6934170705579076545,
    (Point(row=17, col=6), Player.black): 7473924651035762130,
    (Point(row=17, col=6), Player.white): 6181740879394888348,
    (Point(row=17, col=7), None): 1129257150414509625,
    (Point(row=17, col=7), Player.black): 7837080304459486236,
    (Point(row=17, col=7), Player.white): 6630742848769860547,
    (Point(row=17, col=8), None): 7780319767594628354,
    (Point(row=17, col=8), Player.black): 1568939125443457874,
    (Point(row=17, col=8), Player.white): 7539696692589538778,
    (Point(row=17, col=9), None): 7665243387305842563,
    (Point(row=17, col=9), Player.black): 1152044929834717917,
    (Point(row=17, col=9), Player.white): 1356966134381737991,
    (Point(row=17, col=10), None): 8591149540843297096,
    (Point(row=17, col=10), Player.black): 4638878886562009810,
    (Point(row=17, col=10), Player.white): 823236778883739009,
    (Point(row=17, col=11), None): 4268100182799318292,
    (Point(row=17, col=11), Player.black): 1107551630289505326,
    (Point(row=17, col=11), Player.white): 7891156526586667863,
    (Point(row=17, col=12), None): 1017534715675133812,
    (Point(row=17, col=12), Player.black): 2764196596402379721,
    (Point(row=17, col=12), Player.white): 7814498804558769025,
    (Point(row=17, col=13), None): 4343761027723194683,
    (Point(row=17, col=13), Player.black): 4587348376063515832,
    (Point(row=17, col=13), Player.white): 3098880685670063124,
    (Point(row=17, col=14), None): 4714815619581536994,
    (Point(row=17, col=14), Player.black): 6022180712585355373,
    (Point(row=17, col=14), Player.white): 4624313891953312417,
    (Point(row=17, col=15), None): 6277652250742384738,
    (Point(row=17, col=15), Player.black): 5572961275408903576,
    (Point(row=17, col=15), Player.white): 4556636261634728459,
    (Point(row=17, col=16), None): 2519421800755257805,
    (Point(row=17, col=16), Player.black): 6625995300496615026,
    (Point(row=17, col=16), Player.white): 3766529353827289747,
    (Point(row=17, col=17), None): 7709325169544137820,
    (Point(row=17, col=17), Player.black): 7834990150996276207,
    (Point(row=17, col=17), Player.white): 5146084843107956917,
    (Point(row=17, col=18), None): 6473740237232049560,
    (Point(row=17, col=18), Player.black): 7798500689966044709,
    (Point(row=17, col=18), Player.white): 979728246686254105,
    (Point(row=17, col=19), None): 2295316706164181841,
    (Point(row=17, col=19), Player.black): 5343992794278052781,
    (Point(row=17, col=19), Player.white): 5617537198351198193,
    (Point(row=18, col=1), None): 2852527910458903125,
    (Point(row=18, col=1), Player.black): 5702351658945321848,
    (Point(row=18, col=1), Player.white): 2307312766262434562,
    (Point(row=18, col=2), None): 7959065854038660184,
    (Point(row=18, col=2), Player.black): 8287676777453109455,
    (Point(row=18, col=2), Player.white): 4575724552813277813,
    (Point(row=18, col=3), None): 671937270355112936,
    (Point(row=18, col=3), Player.black): 2440766395808033752,
    (Point(row=18, col=3), Player.white): 7118047060049340747,
    (Point(row=18, col=4), None): 4925390829841058751,
    (Point(row=18, col=4), Player.black): 7116955615350911195,
    (Point(row=18, col=4), Player.white): 5794584278517411516,
    (Point(row=18, col=5), None): 560938052143465936,
    (Point(row=18, col=5), Player.black): 4422934017122900805,
    (Point(row=18, col=5), Player.white): 2429545316433048310,
    (Point(row=18, col=6), None): 1418295625793656731,
    (Point(row=18, col=6), Player.black): 246971316675793814,
    (Point(row=18, col=6), Player.white): 6406334685921997221,
    (Point(row=18, col=7), None): 1057828042802571687,
    (Point(row=18, col=7), Player.black): 1245032227956452648,
    (Point(row=18, col=7), Player.white): 4577549140829242055,
    (Point(row=18, col=8), None): 4048319218448622202,
    (Point(row=18, col=8), Player.black): 4813958021549961218,
    (Point(row=18, col=8), Player.white): 8959053605228008149,
    (Point(row=18, col=9), None): 5833846065435472931,
    (Point(row=18, col=9), Player.black): 551230692104665915,
    (Point(row=18, col=9), Player.white): 7067879093010925380,
    (Point(row=18, col=10), None): 8831632376765181341,
    (Point(row=18, col=10), Player.black): 8956405856183023513,
    (Point(row=18, col=10), Player.white): 898017337068290183,
    (Point(row=18, col=11), None): 6472562625815440134,
    (Point(row=18, col=11), Player.black): 789680811119095113,
    (Point(row=18, col=11), Player.white): 8007624127553370205,
    (Point(row=18, col=12), None): 3118865153020698221,
    (Point(row=18, col=12), Player.black): 5042376213925182208,
    (Point(row=18, col=12), Player.white): 6304712403596414542,
    (Point(row=18, col=13), None): 9117650062772795788,
    (Point(row=18, col=13), Player.black): 6848405432401399431,
    (Point(row=18, col=13), Player.white): 6609680246615401929,
    (Point(row=18, col=14), None): 6712816502502173995,
    (Point(row=18, col=14), Player.black): 2464790282343097352,
    (Point(row=18, col=14), Player.white): 6741159888686121927,
    (Point(row=18, col=15), None): 498751852477083716,
    (Point(row=18, col=15), Player.black): 2410153702000293832,
    (Point(row=18, col=15), Player.white): 9077127464663422150,
    (Point(row=18, col=16), None): 5319379521180058988,
    (Point(row=18, col=16), Player.black): 2919319678259757914,
    (Point(row=18, col=16), Player.white): 6879386338666367958,
    (Point(row=18, col=17), None): 343773699873737702,
    (Point(row=18, col=17), Player.black): 1182866646348208526,
    (Point(row=18, col=17), Player.white): 4357043470635359147,
    (Point(row=18, col=18), None): 5602743241684595183,
    (Point(row=18, col=18), Player.black): 4980560856299911210,
    (Point(row=18, col=18), Player.white): 1366448322011038711,
    (Point(row=18, col=19), None): 3798746032546640743,
    (Point(row=18, col=19), Player.black): 2501535748016108797,
    (Point(row=18, col=19), Player.white): 8000730661503177215,
    (Point(row=19, col=1), None): 3964565225046925932,
    (Point(row=19, col=1), Player.black): 3688682836876582637,
    (Point(row=19, col=1), Player.white): 2933345924569920095,
    (Point(row=19, col=2), None): 6317504246489826376,
    (Point(row=19, col=2), Player.black): 162041962383794032,
    (Point(row=19, col=2), Player.white): 4101094869868032024,
    (Point(row=19, col=3), None): 4232524418025068419,
    (Point(row=19, col=3), Player.black): 7405505712579410538,
    (Point(row=19, col=3), Player.white): 7309562979137683430,
    (Point(row=19, col=4), None): 8354916097429750798,
    (Point(row=19, col=4), Player.black): 2635692319009519358,
    (Point(row=19, col=4), Player.white): 1008847460848132416,
    (Point(row=19, col=5), None): 2086877937836048353,
    (Point(row=19, col=5), Player.black): 7626575161044796374,
    (Point(row=19, col=5), Player.white): 803042858960679504,
    (Point(row=19, col=6), None): 3702613267489725371,
    (Point(row=19, col=6), Player.black): 9140224129698370101,
    (Point(row=19, col=6), Player.white): 3586524001457867376,
    (Point(row=19, col=7), None): 8805848995628234819,
    (Point(row=19, col=7), Player.black): 2346671883088990896,
    (Point(row=19, col=7), Player.white): 6349683170997670037,
    (Point(row=19, col=8), None): 3873957112984296489,
    (Point(row=19, col=8), Player.black): 8628502859474536349,
    (Point(row=19, col=8), Player.white): 1973407973971264790,
    (Point(row=19, col=9), None): 728350317280396533,
    (Point(row=19, col=9), Player.black): 131683094041568791,
    (Point(row=19, col=9), Player.white): 6052634543723987111,
    (Point(row=19, col=10), None): 5853392869762672561,
    (Point(row=19, col=10), Player.black): 1086119019384209081,
    (Point(row=19, col=10), Player.white): 2219690733961592219,
    (Point(row=19, col=11), None): 7914124506266617390,
    (Point(row=19, col=11), Player.black): 990951296077837777,
    (Point(row=19, col=11), Player.white): 3187824147999054400,
    (Point(row=19, col=12), None): 3736516329573577537,
    (Point(row=19, col=12), Player.black): 9049982189695762597,
    (Point(row=19, col=12), Player.white): 7798002030810868572,
    (Point(row=19, col=13), None): 4659397407330573358,
    (Point(row=19, col=13), Player.black): 4017565196765571993,
    (Point(row=19, col=13), Player.white): 2141579299272985618,
    (Point(row=19, col=14), None): 5047170360332733135,
    (Point(row=19, col=14), Player.black): 8962575634273478093,
    (Point(row=19, col=14), Player.white): 4296311445796021255,
    (Point(row=19, col=15), None): 4117646698597337977,
    (Point(row=19, col=15), Player.black): 5660517384525053349,
    (Point(row=19, col=15), Player.white): 338807852370812433,
    (Point(row=19, col=16), None): 4897576553623686965,
    (Point(row=19, col=16), Player.black): 5070388705121445392,
    (Point(row=19, col=16), Player.white): 2769952719111012473,
    (Point(row=19, col=17), None): 3653566787938539919,
    (Point(row=19, col=17), Player.black): 6102949954824408729,
    (Point(row=19, col=17), Player.white): 5491214004620863874,
    (Point(row=19, col=18), None): 6765637400696884466,
    (Point(row=19, col=18), Player.black): 7701640673264018069,
    (Point(row=19, col=18), Player.white): 8991707637069145211,
    (Point(row=19, col=19), None): 5029762135737944944,
    (Point(row=19, col=19), Player.black): 5697973289473310863,
    (Point(row=19, col=19), Player.white): 8026543586373257731,
}

EMPTY_BOARD = 3127802437738363466
