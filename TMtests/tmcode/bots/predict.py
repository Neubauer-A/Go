import os
import h5py
import tempfile
import numpy as np
from keras.models import load_model

from tmcode import board
from tmcode.board import Player, Point
from tmcode.encoders import base

def is_point_an_eye(board, point, color):
    if board.get(point) is not None:
        return False
    for neighbor in board.neighbors(point):
        neighbor_color = board.get(neighbor)
        if neighbor_color != color:
            return False
    friendly_corners = 0
    off_board_corners = 0
    corners = [
        Point(point.row - 1, point.col - 1),
        Point(point.row - 1, point.col + 1),
        Point(point.row + 1, point.col - 1),
        Point(point.row + 1, point.col + 1),
    ]
    for corner in corners:
        if board.is_on_grid(corner):
            corner_color = board.get(corner)
            if corner_color == color:
                friendly_corners += 1
        else:
            off_board_corners += 1
    if off_board_corners > 0:
        return off_board_corners + friendly_corners == 4
    return friendly_corners >= 3


class TestNN():
    def __init__(self, model, encoder):
        self.model = model
        self.encoder = encoder
        self.own_color = "black" if self == Player.black else "white"

    def should_pass(self, game_state):
        if game_state.last_move and game_state.last_move.is_pass:
            return True
        return False

    def predict(self, game_state):
        encoded_state = self.encoder.encode(game_state)
        input_tensor = np.array([encoded_state])
        return self.model.predict(input_tensor)[0]

    def select_move(self, game_state):
        if self.should_pass(game_state):
            return board.Move.pass_turn()
        num_moves = self.encoder.board_width * self.encoder.board_height
        move_probs = self.predict(game_state)

        move_probs = move_probs ** 3  
        eps = 1e-6
        move_probs = np.clip(move_probs, eps, 1 - eps)
        move_probs = move_probs / np.sum(move_probs)

        candidates = np.arange(num_moves)  
        ranked_moves = np.random.choice(
            candidates, num_moves, replace=False, p=move_probs) 
        for point_idx in ranked_moves:
            point = self.encoder.decode_point_index(point_idx)
            if game_state.is_valid_move(board.Move.play(point)) and \
                    not is_point_an_eye(game_state.board, point, game_state.next_player): 
                return board.Move.play(point)
        return board.Move.pass_turn() 

def load_bot(h5file):
    model = load_model_from_hdf5_group(h5file['model'])
    encoder_name = h5file['encoder'].attrs['name']
    if not isinstance(encoder_name, str):
        encoder_name = encoder_name.decode('ascii')
    board_width = h5file['encoder'].attrs['board_width']
    board_height = h5file['encoder'].attrs['board_height']
    encoder = base.get_encoder_by_name(
        encoder_name, (board_width, board_height))
    return TestNN(model, encoder)

def load_model_from_hdf5_group(f, custom_objects=None):
    tempfd, tempfname = tempfile.mkstemp(prefix='tmp-kerasmodel')
    try:
        os.close(tempfd)
        serialized_model = h5py.File(tempfname, 'w')
        root_item = f.get('kerasmodel')
        for attr_name, attr_value in root_item.attrs.items():
            serialized_model.attrs[attr_name] = attr_value
        for k in root_item.keys():
            f.copy(root_item.get(k), serialized_model, k)
        serialized_model.close()
        return load_model(tempfname, custom_objects=custom_objects)
    finally:
        os.unlink(tempfname)
