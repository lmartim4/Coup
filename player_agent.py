from abc import ABC, abstractmethod
from game_state import GameStateView, PendingDecision


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
