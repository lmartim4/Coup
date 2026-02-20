from abc import ABC


class ActionEffect(ABC):
    """
    Pure game mechanic, decoupled from which Influence card enables it.
    Different cards can reuse the same effect with different blocker rules.
    """

    def requires_target(self) -> bool:
        return False

    def can_use(self, player) -> bool:
        return True

    def apply_cost(self, player):
        """Upfront cost paid when declaring the action (before defense resolves)."""
        pass

    def causes_influence_loss(self) -> bool:
        return False

    def is_challengeable(self) -> bool:
        """True se a ação requer reivindicar uma carta específica (pode ser duvidada)."""
        return True

    def is_open_blockable(self) -> bool:
        """True se qualquer jogador (não só o alvo) pode bloquear a ação."""
        return False

    def apply_effect(self, player, target=None):
        """Effect applied after the action resolves (not blocked)."""
        pass

    def apply(self, player, target=None):
        """Full effect for actions that skip the defense phase."""
        self.apply_effect(player, target)


class AssassinationEffect(ActionEffect):
    """Pay 3 coins to force a target to lose an influence."""

    def requires_target(self) -> bool:
        return True

    def can_use(self, player) -> bool:
        return player.coins >= 3

    def apply_cost(self, player):
        player.coins -= 3

    def causes_influence_loss(self) -> bool:
        return True


class StealEffect(ActionEffect):
    """Take up to 2 coins from a target."""

    def requires_target(self) -> bool:
        return True

    def apply_effect(self, player, target=None):
        assert target is not None
        stolen = min(2, target.coins)
        player.coins += stolen
        target.coins -= stolen

    def apply(self, player, target=None):
        self.apply_effect(player, target)


class TaxEffect(ActionEffect):
    """Collect 3 coins from the treasury."""

    def apply(self, player, target=None):
        player.coins += 3


class IncomeEffect(ActionEffect):
    """Pega 1 moeda do tesouro. Sem carta, sem bloqueio."""

    def is_challengeable(self) -> bool:
        return False

    def apply(self, player, target=None):
        player.coins += 1


class ForeignAidEffect(ActionEffect):
    """Pega 2 moedas do tesouro. Bloqueável pelo Duque (qualquer jogador)."""

    def is_challengeable(self) -> bool:
        return False

    def is_open_blockable(self) -> bool:
        return True

    def apply_effect(self, player, target=None):
        player.coins += 2


class CoupEffect(ActionEffect):
    """Paga 7 moedas para forçar o alvo a perder uma influência. Sem bloqueio."""

    def requires_target(self) -> bool:
        return True

    def can_use(self, player) -> bool:
        return player.coins >= 7

    def apply_cost(self, player):
        player.coins -= 7

    def causes_influence_loss(self) -> bool:
        return True

    def is_challengeable(self) -> bool:
        return False
