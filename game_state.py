from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ── Internal engine phases ────────────────────────────────────────────────────
#
# Each _phase_* attribute in GameEngine holds exactly one of these dataclasses
# (or None). Using typed dataclasses instead of raw dicts / tuples lets the
# code (and type-checkers) know exactly what fields to expect in each phase.

class RevealContext(str, Enum):
    """Why a player is being asked to reveal (or refuse) a card."""
    DOUBT_ACTION = 'doubt_action'  # defender doubted the attacker's claimed card
    DOUBT_BLOCK  = 'doubt_block'   # attacker doubted the blocker's claimed card
    DOUBT_OPEN   = 'doubt_open'    # a bystander doubted a non-targeted action (e.g. Duke)


@dataclass
class PhaseAction:
    """Current player picked an action that needs a target — waiting for target."""
    action: Any  # Influence


@dataclass
class PhaseDefense:
    """Target player must decide how to react to an incoming action."""
    target_idx: int
    action: Any  # Influence


@dataclass
class PhaseChallenge:
    """Other players can doubt an announced card-action (e.g. Duke tax).
    queue: remaining player indices that haven't passed yet."""
    actor: int
    action: Any  # Influence
    queue: list[int]


@dataclass
class PhaseDoubtBlock:
    """Players can challenge a claimed block.
    queue: remaining player indices that haven't passed yet."""
    attacker: int
    target: int   # the blocker
    action: Any   # Influence (the original action being blocked)
    queue: list[int]


@dataclass
class PhaseBlockOpen:
    """Any player may block an open action (e.g. Foreign Aid → Duke).
    queue: remaining player indices that haven't passed yet."""
    actor: int
    action: Any   # Influence
    queue: list[int]


@dataclass
class PhaseLoseInfluence:
    """A player must discard one of their influence cards."""
    target_idx: int
    next_turn: int


@dataclass
class PhaseReveal:
    """A challenged player must show (or refuse to show) the claimed card.
    doubter is None only when context == RevealContext.DOUBT_ACTION."""
    challenged_player: int
    card_name: str
    context: RevealContext
    attacker: int
    target: int
    action: Any  # Influence
    next_turn: int
    doubter: Optional[int] = None


# ── Public game-state views ───────────────────────────────────────────────────

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
