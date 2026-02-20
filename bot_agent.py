import random
from player_agent import PlayerAgent
from game_state import GameStateView, PendingDecision


class BotAgent(PlayerAgent):
    """Bot que escolhe aleatoriamente entre as opções disponíveis."""

    def __init__(self, name: str = "Bot"):
        self.name = name

    def decide(self, state: GameStateView, decision: PendingDecision):
        choice = random.choice(decision.options)
        return choice
