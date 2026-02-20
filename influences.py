from abc import ABC, abstractmethod
from actions import (ActionEffect, AssassinationEffect, StealEffect, TaxEffect,
                     IncomeEffect, ForeignAidEffect, CoupEffect)


class Influence(ABC):

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    def get_action(self) -> ActionEffect | None:
        """The action this card enables, or None if purely defensive."""
        return None

    def get_blockers(self) -> list[type['Influence']]:
        """Influence types that can block this card's action. Empty = unblockable."""
        return []

    # --- Delegation to action (keeps coup.py interface unchanged) ---

    def requires_target(self) -> bool:
        action = self.get_action()
        return action.requires_target() if action else False

    def can_use(self, player) -> bool:
        action = self.get_action()
        return action.can_use(player) if action else True

    def has_defense(self) -> bool:
        return bool(self.get_blockers())

    def get_block_name(self) -> str | None:
        """Derived from get_blockers() for backward compatibility with the engine."""
        blockers = self.get_blockers()
        return blockers[0]().get_name() if blockers else None

    def apply(self, player, target=None):
        action = self.get_action()
        if action:
            action.apply(player, target)

    def apply_cost(self, player):
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

    def apply_effect(self, player, target=None):
        action = self.get_action()
        if action:
            action.apply_effect(player, target)


class Countess(Influence):

    def get_name(self):
        return "Condessa"

    def get_description(self):
        return "Bloqueia o Príncipe e o Assassino"


class Assassin(Influence):

    def get_name(self):
        return "Assassino"

    def get_description(self):
        return "Assassina a influência de alguém (custa 3 moedas)"

    def get_action(self) -> AssassinationEffect:
        return AssassinationEffect()

    def get_blockers(self) -> list[type[Influence]]:
        return [Countess]


class Duke(Influence):

    def get_name(self):
        return "Duque"

    def get_description(self):
        return "Coleta 3 moedas do tesouro"

    def get_action(self) -> TaxEffect:
        return TaxEffect()


class Captain(Influence):

    def get_name(self):
        return "Capitao"

    def get_description(self):
        return "Rouba 2 moedas de outro jogador"

    def get_action(self) -> StealEffect:
        return StealEffect()

    def get_blockers(self) -> list[type[Influence]]:
        return [Captain]


# ── Ações básicas (sem carta) ─────────────────────────────────────────────────

class IncomeAction(Influence):

    def get_name(self):
        return "Renda"

    def get_description(self):
        return "Pega 1 moeda do tesouro"

    def get_action(self) -> IncomeEffect:
        return IncomeEffect()


class ForeignAidAction(Influence):

    def get_name(self):
        return "Ajuda Externa"

    def get_description(self):
        return "Pega 2 moedas (bloqueável pelo Duque)"

    def get_action(self) -> ForeignAidEffect:
        return ForeignAidEffect()

    def get_blockers(self) -> list[type[Influence]]:
        return [Duke]


class CoupAction(Influence):

    def get_name(self):
        return "Golpe"

    def get_description(self):
        return "Paga 7 moedas para eliminar uma influência do alvo"

    def get_action(self) -> CoupEffect:
        return CoupEffect()
