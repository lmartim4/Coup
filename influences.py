from abc import ABC, abstractmethod

class Influence(ABC):

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    def requires_target(self) -> bool:
        return False

    def can_use(self, player) -> bool:
        return True

    def has_defense(self) -> bool:
        return False

    def get_block_name(self) -> str | None:
        """Card name that blocks this action, or None if unblockable."""
        return None

    def apply(self, player, target=None):
        """Full effect for actions that have no defense phase."""
        pass

    def apply_cost(self, player):
        """Upfront cost paid when declaring the action (before defense resolves)."""
        pass

    def apply_effect(self, player, target=None):
        """Effect applied when the action is not blocked."""
        pass


class Assassin(Influence):

    def get_name(self):
        return "Assassino"

    def get_description(self):
        return "Assassina a influencia de alguem (custa 3 moedas)"

    def requires_target(self):
        return True

    def has_defense(self) -> bool:
        return True

    def get_block_name(self):
        return "Condessa"

    def can_use(self, player) -> bool:
        return player.coins >= 3

    def apply_cost(self, player):
        player.coins -= 3

    def apply_effect(self, player, target=None):
        pass  # influence removal not yet implemented


class Duke(Influence):

    def get_name(self):
        return "Duque"

    def get_description(self):
        return "Coleta 3 moedas do tesouro"

    def apply(self, player, target=None):
        player.coins += 3


class Countess(Influence):

    def get_name(self):
        return "Condessa"

    def get_description(self):
        return "Bloqueia o Principe e o Assassino"


class Captain(Influence):

    def get_name(self):
        return "Capitao"

    def get_description(self):
        return "Rouba 2 moedas de outro jogador"

    def requires_target(self):
        return True

    def has_defense(self) -> bool:
        return True

    def get_block_name(self):
        return "Capitao"

    def apply_cost(self, player):
        pass  # no upfront cost; steal only happens if action goes through

    def apply_effect(self, player, target=None):
        assert target is not None
        stolen = min(2, target.coins)
        player.coins += stolen
        target.coins -= stolen

    def apply(self, player, target=None):
        self.apply_effect(player, target)
