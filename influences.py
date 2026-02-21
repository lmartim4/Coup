from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, TYPE_CHECKING

from actions import (ActionEffect, AssassinationEffect, StealEffect, TaxEffect,
                     IncomeEffect, ForeignAidEffect, CoupEffect)

if TYPE_CHECKING:
    from game_agent import Player


class Influence(ABC):

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other)

    def __hash__(self) -> int:
        return hash(type(self))

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    def get_action(self) -> Optional[ActionEffect]:
        """The action this card enables, or None if purely defensive."""
        return None

    def get_blockers(self) -> List[type[Influence]]:
        """Influence types that can block this card's action. Empty = unblockable."""
        return []

    def requires_target(self) -> bool:
        action = self.get_action()
        return action.requires_target() if action else False

    def can_use(self, player: Player) -> bool:
        action = self.get_action()
        return action.can_use(player) if action else True

    def has_defense(self) -> bool:
        return bool(self.get_blockers())

    def get_block_name(self) -> str:
        """Derived from get_blockers() for backward compatibility with the engine."""
        blockers = self.get_blockers()
        return blockers[0]().get_name() if blockers else ''

    def apply(self, player: Player, target: Optional[Player]= None) -> None:
        action = self.get_action()
        if action:
            action.apply(player, target)

    def apply_cost(self, player: Player) -> None:
        action = self.get_action()
        if action:
            action.apply_cost(player)

    def causes_influence_loss(self) -> bool:
        action = self.get_action()
        return action.causes_influence_loss() if action else False

    def is_challengeable(self) -> bool:
        """True se requer reivindicar uma carta (pode ser duvidada)."""
        action = self.get_action()
        return action.is_challengeable() if action else True

    def is_open_blockable(self) -> bool:
        """True se qualquer jogador pode bloquear (não só o alvo)."""
        action = self.get_action()
        return action.is_open_blockable() if action else False

    def apply_effect(self, player: Player, target: Optional[Player]= None) -> None:
        action = self.get_action()
        if action:
            action.apply_effect(player, target)


class Countess(Influence):

    def get_name(self) -> str:
        return "Condessa"

    def get_description(self) -> str:
        return "Bloqueia o Príncipe e o Assassino"

    def get_value(self) -> int:
        return 2


class Assassin(Influence):

    def get_name(self) -> str:
        return "Assassino"

    def get_description(self) -> str:
        return "Assassina a influência de alguém (custa 3 moedas)"

    def get_value(self) -> int:
        return 3

    def get_action(self) -> AssassinationEffect:
        return AssassinationEffect()

    def get_blockers(self) -> List[type[Influence]]:
        return [Countess]


class Duke(Influence):

    def get_name(self) -> str:
        return "Duque"

    def get_description(self) -> str:
        return "Coleta 3 moedas do tesouro"

    def get_value(self) -> int:
        return 4

    def get_action(self) -> TaxEffect:
        return TaxEffect()


class Captain(Influence):

    def get_name(self) -> str:
        return "Capitao"

    def get_description(self) -> str:
        return "Rouba 2 moedas de outro jogador"

    def get_value(self) -> int:
        return 3

    def get_action(self) -> StealEffect:
        return StealEffect()

    def get_blockers(self) -> List[type[Influence]]:
        return [Captain]


class IncomeAction(Influence):

    def get_name(self) -> str:
        return "Renda"

    def get_description(self) -> str:
        return "Pega 1 moeda do tesouro"

    def get_action(self) -> IncomeEffect:
        return IncomeEffect()


class ForeignAidAction(Influence):

    def get_name(self) -> str:
        return "Ajuda Externa"

    def get_description(self) -> str:
        return "Pega 2 moedas (bloqueável pelo Duque)"

    def get_action(self) -> ForeignAidEffect:
        return ForeignAidEffect()

    def get_blockers(self) -> List[type[Influence]]:
        return [Duke]


class CoupAction(Influence):

    def get_name(self) -> str:
        return "Golpe"

    def get_description(self) -> str:
        return "Paga 7 moedas para eliminar uma influência do alvo"

    def get_action(self) -> CoupEffect:
        return CoupEffect()


# Map card name → strategic keep-value, derived from each card's own definition.
CARD_VALUE: Dict[str, int] = {
    cls().get_name(): cls().get_value()
    for cls in (Countess, Assassin, Duke, Captain)
    if hasattr(cls(), "get_value")
}
