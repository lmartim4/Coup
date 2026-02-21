import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from game_state import GameStateView, PendingDecision, DecisionType, DecisionResponse
from influences import CARD_VALUE


class Player:
    def __init__(self, name: str, influences: list):
        self.name = name
        self.influences = influences
        self.revealed_influences = []
        self.coins = 2


class PlayerAgent(ABC):
    @abstractmethod
    def decide(self, state: GameStateView, decision: PendingDecision) -> object:
        pass



@dataclass
class BotPersonality:
    bluff_rate: float = 0.20
    base_doubt_rate: float = 0.20
    early_caution_factor: float = 0.15
    early_game_threshold: int = 2
    block_with_card_rate: float = 0.90
    block_bluff_rate: float = 0.10
    card_counting_weight: float = 0.50
    aggression: float = 0.50

    @classmethod
    def random(cls) -> "BotPersonality":
        return cls(
            bluff_rate=random.uniform(0.05, 0.50),
            base_doubt_rate=random.uniform(0.05, 0.40),
            early_caution_factor=random.uniform(0.05, 0.35),
            early_game_threshold=random.randint(1, 3),
            block_with_card_rate=random.uniform(0.70, 1.00),
            block_bluff_rate=random.uniform(0.00, 0.25),
            card_counting_weight=random.uniform(0.20, 0.80),
            aggression=random.uniform(0.10, 0.90),
        )

    def __repr__(self) -> str:
        return (
            f"BotPersonality("
            f"bluff={self.bluff_rate:.2f}, "
            f"doubt={self.base_doubt_rate:.2f}, "
            f"early_caution={self.early_caution_factor:.2f}@{self.early_game_threshold}rev, "
            f"block={self.block_with_card_rate:.2f}/bluff={self.block_bluff_rate:.2f}, "
            f"cc_weight={self.card_counting_weight:.2f}, "
            f"aggr={self.aggression:.2f})"
        )


class BotAgent(PlayerAgent):
    def __init__(self, name: str = "Bot", personality: Optional[BotPersonality] = None):
        self.name = name
        self.personality = personality if personality is not None else BotPersonality.random()
        print(f"  [Bot] {name}: {self.personality}")

    def _my_cards(self, state: GameStateView) -> List[str]:
        return list(state.players[state.viewer_index].influences)

    def _has_card(self, card_name: str, state: GameStateView) -> bool:
        return card_name in self._my_cards(state)

    def _is_early_game(self, state: GameStateView) -> bool:
        total_revealed = sum(len(p.revealed_influences) for p in state.players)
        return total_revealed < self.personality.early_game_threshold

    def _count_known(self, card_name: str, state: GameStateView) -> int:
        count = sum(1 for c in self._my_cards(state) if c == card_name)
        for p in state.players:
            count += sum(1 for c in p.revealed_influences if c == card_name)
        return count

    def _doubt_probability(
        self,
        card_name: str,
        state: GameStateView,
        apply_early_caution: bool = True,
    ) -> float:
        p = self.personality
        doubt = p.base_doubt_rate

        if apply_early_caution and self._is_early_game(state):
            doubt *= p.early_caution_factor

        max_copies = state.cards_per_type.get(card_name, 3)
        known = self._count_known(card_name, state)
        plausible = max(0, max_copies - known)

        if plausible <= 0:
            return 1.0

        scarcity = (max_copies - plausible) / max_copies
        counting_boost = scarcity * p.card_counting_weight
        return min(1.0, doubt + counting_boost)

    def _pick_action(self, state: GameStateView, decision: PendingDecision):
        p = self.personality
        me = state.players[state.viewer_index]
        my_cards = self._my_cards(state)
        opt_map = {o.get_name(): o for o in decision.options}

        if "Golpe" in opt_map and me.coins >= 10:
            return opt_map["Golpe"]

        if "Golpe" in opt_map and me.coins >= 7 and random.random() < p.aggression:
            return opt_map["Golpe"]

        if "Duque" in opt_map and "Duque" in my_cards:
            return opt_map["Duque"]

        if "Assassino" in opt_map and "Assassino" in my_cards and me.coins >= 3:
            if random.random() < p.aggression:
                return opt_map["Assassino"]

        if "Capitao" in opt_map and "Capitao" in my_cards:
            if random.random() < p.aggression:
                return opt_map["Capitao"]

        if random.random() < p.bluff_rate:
            bluff_candidates = [
                n for n in ("Duque", "Assassino", "Capitao")
                if n in opt_map
                and n not in my_cards
                and (n != "Assassino" or me.coins >= 3)
            ]
            if bluff_candidates:
                return opt_map[random.choice(bluff_candidates)]

        if "Ajuda Externa" in opt_map:
            return opt_map["Ajuda Externa"]
        if "Renda" in opt_map:
            return opt_map["Renda"]

        return random.choice(decision.options)

    def _pick_target(self, state: GameStateView, decision: PendingDecision) -> int:
        p = self.personality
        targets: List[int] = decision.options

        one_card = [i for i in targets if state.players[i].influence_count == 1]
        if one_card and random.random() < p.aggression:
            return random.choice(one_card)

        if random.random() < p.aggression:
            return max(targets, key=lambda i: state.players[i].coins)

        return random.choice(targets)

    def _lose_influence(self, state: GameStateView, decision: PendingDecision) -> int:
        my_cards = self._my_cards(state)
        card_indices: List[int] = decision.options

        return min(card_indices, key=lambda i: CARD_VALUE.get(
            my_cards[i] if i < len(my_cards) else "", 0
        ))

    def _challenge_action(self, state: GameStateView, decision: PendingDecision):
        card_name = decision.context.get("action_name", "")
        doubt_prob = self._doubt_probability(card_name, state, apply_early_caution=True)

        if DecisionResponse.DOUBT in decision.options and random.random() < doubt_prob:
            return DecisionResponse.DOUBT
        return DecisionResponse.PASS

    def _challenge_block(self, state: GameStateView, decision: PendingDecision):
        card_name = decision.context.get("block_card", "")
        doubt_prob = self._doubt_probability(card_name, state, apply_early_caution=False)

        if DecisionResponse.DOUBT in decision.options and random.random() < doubt_prob:
            return DecisionResponse.DOUBT
        return DecisionResponse.PASS

    def _block_or_pass(self, state: GameStateView, decision: PendingDecision):
        block_card = decision.context.get("block_card", "")
        p = self.personality

        if block_card and self._has_card(block_card, state):
            if DecisionResponse.BLOCK in decision.options and random.random() < p.block_with_card_rate:
                return DecisionResponse.BLOCK
        elif random.random() < p.block_bluff_rate:
            if DecisionResponse.BLOCK in decision.options:
                return DecisionResponse.BLOCK

        return DecisionResponse.PASS

    def _defend(self, state: GameStateView, decision: PendingDecision):
        block_card = decision.context.get("block_card", "")
        action_name = decision.context.get("action_name", "")
        p = self.personality

        if block_card and self._has_card(block_card, state):
            if DecisionResponse.BLOCK in decision.options and random.random() < p.block_with_card_rate:
                return DecisionResponse.BLOCK

        if DecisionResponse.DOUBT_ACTION in decision.options:
            doubt_prob = self._doubt_probability(action_name, state, apply_early_caution=False)
            if random.random() < doubt_prob:
                return DecisionResponse.DOUBT_ACTION

        if block_card and DecisionResponse.BLOCK in decision.options:
            if random.random() < p.block_bluff_rate:
                return DecisionResponse.BLOCK

        return DecisionResponse.ACCEPT

    def _reveal(self, state: GameStateView, decision: PendingDecision):
        card_name = decision.context.get("card_name", "")
        if self._has_card(card_name, state):
            return DecisionResponse.REVEAL
        return DecisionResponse.REFUSE

    def decide(self, state: GameStateView, decision: PendingDecision):
        dt = decision.decision_type
        try:
            if dt == DecisionType.PICK_ACTION:
                return self._pick_action(state, decision)
            elif dt == DecisionType.PICK_TARGET:
                return self._pick_target(state, decision)
            elif dt == DecisionType.LOSE_INFLUENCE:
                return self._lose_influence(state, decision)
            elif dt == DecisionType.CHALLENGE_ACTION:
                return self._challenge_action(state, decision)
            elif dt == DecisionType.CHALLENGE_BLOCK:
                return self._challenge_block(state, decision)
            elif dt == DecisionType.BLOCK_OR_PASS:
                return self._block_or_pass(state, decision)
            elif dt == DecisionType.DEFEND:
                return self._defend(state, decision)
            elif dt == DecisionType.REVEAL:
                return self._reveal(state, decision)
        except Exception:
            pass

        return random.choice(decision.options)
