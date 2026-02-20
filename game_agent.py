import random
from abc import ABC, abstractmethod
from game_state import GameStateView, PendingDecision

class Player:
    def __init__(self, name: str, influences: list):
        self.name = name
        self.influences = influences
        self.revealed_influences = []
        self.coins = 2


class PlayerAgent(ABC):
    @abstractmethod
    def decide(self, state: GameStateView, decision: PendingDecision):
        pass


class BotAgent(PlayerAgent):
    def __init__(self, name: str = "Bot"):
        self.name = name

    def decide(self, state: GameStateView, decision: PendingDecision):
        choice = random.choice(decision.options)
        return choice