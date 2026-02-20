import random
from abc import ABC, abstractmethod
from game_state import GameStateView, PendingDecision

class Player:
    def __init__(self, name: str, influences: list):
        self.name = name
        self.influences = influences          # cartas na mão
        self.revealed_influences = []        # cartas reveladas (viradas na mesa)
        self.coins = 2


class PlayerAgent(ABC):
    """
    Interface de um jogador. Recebe a visão do estado do jogo e a decisão
    pendente e retorna uma das opções válidas.

    Em multiplayer real, cada cliente implementará sua própria versão:
    - HumanAgent: exibe UI e aguarda input
    - BotAgent: lógica automática
    - NetworkAgent: aguarda mensagem do cliente remoto
    """

    @abstractmethod
    def decide(self, state: GameStateView, decision: PendingDecision):
        """Retorna um valor que esteja em decision.options."""
        pass


class BotAgent(PlayerAgent):
    """Bot que escolhe aleatoriamente entre as opções disponíveis."""

    def __init__(self, name: str = "Bot"):
        self.name = name

    def decide(self, state: GameStateView, decision: PendingDecision):
        choice = random.choice(decision.options)
        return choice