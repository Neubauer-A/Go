import numpy as np
from tmcode.encoders.base import Encoder
from tmcode.board import Point, Player, Move

# Channel 0 represents the current player's stone color.
# Channel 1 represents black and white stones.
# Channel 2 represents string liberties.
# Channel 3 represents liberties a stone would have if played.
# Channel 4 represents number of own stones in atari if played.
# Channel 5 represents number of opponent stones captured if played.

class TMTestEncoder(Encoder):
    def __init__(self, board_size):
        self.board_width, self.board_height = board_size
        self.num_planes = 6

    def name(self):
        return 'tmtest'

    def encode(self, game_state):
        board_tensor = np.zeros(self.shape())        
        for row in range(self.board_height):
            for col in range(self.board_width):
                p = Point(row=row + 1, col=col + 1)
                go_string = game_state.board.get_go_string(p)
                move = Move.play(p)

                if game_state.next_player == Player.black:
                    board_tensor[row][col][0] = 1
                else:
                    board_tensor[row][col][0] = -1              

                if go_string:                                            
                    if go_string.color == Player.black:
                        board_tensor[row][col][1] = 1
                    else:
                        board_tensor[row][col][1] = -1
                    
                    if go_string.num_liberties < 10:
                        board_tensor[row][col][2] = go_string.num_liberties / 10
                    else:
                        board_tensor[row][col][2] = 1
                
                if game_state.is_valid_move(move):
                      new_state = game_state.apply_move(move)
                      new_string = new_state.board.get_go_string(p)
                      if new_string.num_liberties < 10:
                        board_tensor[row][col][3] = new_string.num_liberties / 10
                      else:
                          board_tensor[row][col][3] = 1
                      
                      if new_string.num_liberties == 1:
                          if len(new_string.stones) < 10:                      
                              board_tensor[row][col][4] = len(new_string.stones) / 10
                          else:
                              board_tensor[row][col][4] = 1

                      adjacent_strings = [game_state.board.get_go_string(nb)  
                                        for nb in p.neighbors()]            #<8>
                      capture_count = 0
                      for s in adjacent_strings:
                          other_p = game_state.next_player.other
                          if s and s.num_liberties == 1 and s.color == other_p:
                              capture_count += len(s.stones)
                      if capture_count < 10:                   
                          board_tensor[row][col][5] = capture_count / 10
                      else:             
                          board_tensor[row][col][5] = 1

        return board_tensor

    def encode_point(self, point):
        return self.board_width * (point.row - 1) + (point.col - 1)

    def decode_point_index(self, index):
        row = index // self.board_width
        col = index % self.board_width
        return Point(row=row + 1, col=col + 1)

    def num_points(self):
        return self.board_width * self.board_height

    def shape(self):
        return self.board_height, self.board_width, self.num_planes

def create(board_size):
    return TMTestEncoder(board_size)
