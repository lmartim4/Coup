import random
from abc import ABC, abstractmethod
from typing import Any
from game_state import GameStateView, PendingDecision
from influences import Influence

class Player:
    def __init__(self, name: str, influences: list[Influence]):
        self.name: str = name
        self.influences: list[Influence] = influences
        self.revealed_influences: list[Influence] = []
        self.coins: int = 2
    
class PlayerAgent(ABC):
    @abstractmethod
    def decide(self, state: GameStateView, decision: PendingDecision) -> Any:
        pass
    
class BotAgent(PlayerAgent):
    def __init__(self, name: str = "Bot"):
        self.name: str = name

    def decide(self, state: GameStateView, decision: PendingDecision) -> Any:
        choice = random.choice(decision.options)
        return choice