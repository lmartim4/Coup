from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from influences import Influence

class DecisionType(Enum):
    PICK_ACTION      = 'pick_action'
    PICK_TARGET      = 'pick_target'
    DEFEND           = 'defend'
    CHALLENGE_ACTION = 'challenge_action'
    CHALLENGE_BLOCK  = 'challenge_block'
    BLOCK_OR_PASS    = 'block_or_pass'
    LOSE_INFLUENCE   = 'lose_influence'
    REVEAL           = 'reveal'


class DecisionResponse(Enum):
    PASS         = 'pass'
    BLOCK        = 'block'
    DOUBT        = 'doubt'
    DOUBT_ACTION = 'doubt_action'
    ACCEPT       = 'accept'
    REVEAL       = 'reveal'
    REFUSE       = 'refuse'

class RevealContext(str, Enum):
    """Why a player is being asked to reveal (or refuse) a card."""
    DOUBT_ACTION = 'doubt_action'  # defender doubted the attacker's claimed card
    DOUBT_BLOCK  = 'doubt_block'   # attacker doubted the blocker's claimed card
    DOUBT_OPEN   = 'doubt_open'    # a bystander doubted a non-targeted action (e.g. Duke)


@dataclass
class PhaseAction:
    """Current player picked an action that needs a target — waiting for target."""
    action: Influence


@dataclass
class PhaseDefense:
    """Target player must decide how to react to an incoming action."""
    target_idx: int
    action: Influence


@dataclass
class PhaseChallenge:
    """Other players can doubt an announced card-action (e.g. Duke tax).
    queue: remaining player indices that haven't passed yet."""
    actor: int
    action: Influence
    queue: List[int]


@dataclass
class PhaseDoubtBlock:
    """Players can challenge a claimed block.
    queue: remaining player indices that haven't passed yet."""
    attacker: int
    target: int   # the blocker
    action: Influence  # the original action being blocked
    queue: List[int]


@dataclass
class PhaseBlockOpen:
    """Any player may block an open action (e.g. Foreign Aid → Duke).
    queue: remaining player indices that haven't passed yet."""
    actor: int
    action: Influence
    queue: List[int]


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
    action: Influence
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
    influences: List[str]      # nomes das cartas na mão — só para o próprio jogador
    revealed_influences: List[str]  # cartas reveladas (viradas na mesa) — visíveis a todos
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
        PICK_ACTION      – List[Influence]        ações disponíveis (submeter o objeto da ação)
        PICK_TARGET      – List[int]              índices dos jogadores alvejáveis
        DEFEND           – List[DecisionResponse] subconjunto de [BLOCK, DOUBT_ACTION, ACCEPT]
        CHALLENGE_ACTION – [DOUBT, PASS]
        CHALLENGE_BLOCK  – [DOUBT, PASS]
        BLOCK_OR_PASS    – [BLOCK, PASS]
        LOSE_INFLUENCE   – List[int]              índices das cartas que o jogador ainda tem
        REVEAL           – [REVEAL, REFUSE]
    """
    player_index: int
    decision_type: DecisionType
    options: list
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        def _ser(opt):
            if isinstance(opt, DecisionResponse):
                return opt.value
            if hasattr(opt, 'get_name'):
                return opt.get_name()
            return opt

        return {
            'player_index':  self.player_index,
            'decision_type': self.decision_type.value,
            'options':       [_ser(o) for o in self.options],
            'context':       self.context,
        }


@dataclass
class GameStateView:
    """
    Estado serializado do jogo do ponto de vista de um jogador específico.
    Pode ser convertido para dict e enviado via rede no futuro.
    """
    players: List[PlayerStateView]
    current_turn: int
    pending_decision: Optional[PendingDecision]
    viewer_index: int
    cards_per_type: dict = field(default_factory=dict)
    # Recent narrative events from the engine (shown in event log panel)
    event_log: List[str] = field(default_factory=list)
    # Info about the decision that was just submitted (drives post-decision bubbles)
    last_action: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            'players':          [p.to_dict() for p in self.players],
            'current_turn':     self.current_turn,
            'pending_decision': self.pending_decision.to_dict() if self.pending_decision else None,
            'viewer_index':     self.viewer_index,
            'cards_per_type':   self.cards_per_type,
            'event_log':        self.event_log,
            'last_action':      self.last_action,
        }
