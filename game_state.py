from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlayerStateView:
    """
    Visão pública de um jogador. Para o próprio jogador, 'influences' contém
    os nomes das cartas. Para os adversários, 'influences' é vazio (cartas
    viradas para baixo) e só 'influence_count' é visível.
    """
    index: int
    name: str
    coins: int
    influence_count: int       # visível a todos
    influences: list[str]      # nomes das cartas na mão — só para o próprio jogador
    revealed_influences: list[str]  # cartas reveladas (viradas na mesa) — visíveis a todos
    is_eliminated: bool

    def to_dict(self) -> dict:
        return {
            'index':               self.index,
            'name':                self.name,
            'coins':               self.coins,
            'influence_count':     self.influence_count,
            'influences':          self.influences,
            'revealed_influences': self.revealed_influences,
            'is_eliminated':       self.is_eliminated,
        }


@dataclass
class PendingDecision:
    """
    Decisão que um jogador específico precisa tomar agora.

    decision_type / options:
        'pick_action'      – list[str]   nomes das ações disponíveis
        'pick_target'      – list[int]   índices dos jogadores alvejáveis
        'defend'           – list[str]   subconjunto de ['block','doubt_action','accept']
        'challenge_action' – ['doubt', 'pass']
        'challenge_block'  – ['doubt', 'pass']
        'lose_influence'   – list[int]   índices das cartas que o jogador ainda tem
        'reveal'           – ['reveal', 'refuse']
    """
    player_index: int
    decision_type: str
    options: list
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'player_index':  self.player_index,
            'decision_type': self.decision_type,
            'options':       self.options,
            'context':       self.context,
        }


@dataclass
class GameStateView:
    """
    Estado serializado do jogo do ponto de vista de um jogador específico.
    Pode ser convertido para dict e enviado via rede no futuro.
    """
    players: list[PlayerStateView]
    current_turn: int
    pending_decision: Optional[PendingDecision]
    viewer_index: int

    def to_dict(self) -> dict:
        return {
            'players':          [p.to_dict() for p in self.players],
            'current_turn':     self.current_turn,
            'pending_decision': self.pending_decision.to_dict() if self.pending_decision else None,
            'viewer_index':     self.viewer_index,
        }
