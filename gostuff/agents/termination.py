from gostuff import goboard
from gostuff.agents.base import Agent
from gostuff import scoring
from gostuff.gotypes import Player

class TerminationStrategy:

    def __init__(self):
        pass

    def should_pass(self, game_state):
        return False

    def should_resign(self, game_state):
        return False

class PassWhenOpponentPasses(TerminationStrategy):

    def should_pass(self, game_state):
        if game_state.last_move is not None:
            return True if game_state.last_move.is_pass else False

class ResignLargeMargin(TerminationStrategy):

    def __init__(self):
        TerminationStrategy.__init__(self)
        self.own_color = "black" if self == Player.black else "white"
        self.cut_off_move = 160
        self.margin = 90

        self.moves_played = 0

    def should_pass(self, game_state):
        if game_state.last_move is not None:
            return True if game_state.last_move.is_pass else False

    def should_resign(self, game_state):
        self.moves_played += 1
        if self.moves_played >= self.cut_off_move:
            game_result = scoring.compute_game_result(game_state)
            if game_result.winner != self.own_color and game_result.winning_margin >= self.margin:
                return True
        return False

class TerminationAgent(Agent):

    def __init__(self, agent, strategy=None):
        Agent.__init__(self)
        self.agent = agent
        self.strategy = strategy if strategy is not None \
            else TerminationStrategy()

    def select_move(self, game_state):
        if self.strategy.should_pass(game_state):
            return goboard.Move.pass_turn()
        elif self.strategy.should_resign(game_state):
            return goboard.Move.resign()
        else:
            return self.agent.select_move(game_state)

def get(termination):
    if termination == 'opponent_passes':
        return PassWhenOpponentPasses()
    else:
        return ResignLargeMargin()