import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from game_engine import GameEngine
from game_agent import Player
from influences import Assassin, Duke, Countess, Captain, IncomeAction, ForeignAidAction, CoupAction
from actions import IncomeEffect, ForeignAidEffect, TaxEffect, AssassinationEffect, StealEffect, CoupEffect
from game_state import (
    PhaseLoseInfluence, PhaseReveal, RevealContext,
    PendingDecision, PlayerStateView, GameStateView,
    DecisionType, DecisionResponse,
)

def make_engine(player_cards: list[list]) -> GameEngine:
    """Build an engine with deterministic card layouts.  All players start with 2 coins."""
    players = [Player(name=f"P{i}", influences=cards) for i, cards in enumerate(player_cards)]
    return GameEngine(players)


def pd(eng: GameEngine) -> PendingDecision:
    """Return the active pending decision, asserting it exists."""
    assert eng.pending_decision is not None
    return eng.pending_decision


def resolve_lose(eng: GameEngine, card_idx: int = 0):
    """Submit a lose_influence decision (choose card at card_idx)."""
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    eng.submit_decision(card_idx)


# ══════════════════════════════════════════════════════════════════════════════
# 1.  RENDA (Income)
# ══════════════════════════════════════════════════════════════════════════════

def test_income_gives_one_coin():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision(IncomeAction())
    assert eng.players[0].coins == 3

def test_income_turn_advances_2p():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision(IncomeAction())
    assert eng.current_turn == 1

def test_income_turn_cycles_3p():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Duke(), Captain()]])
    eng.submit_decision(IncomeAction())   # P0
    assert eng.current_turn == 1
    eng.submit_decision(IncomeAction())   # P1
    assert eng.current_turn == 2
    eng.submit_decision(IncomeAction())   # P2
    assert eng.current_turn == 0


# ══════════════════════════════════════════════════════════════════════════════
# 2.  AJUDA EXTERNA (Foreign Aid)
# ══════════════════════════════════════════════════════════════════════════════

def test_foreign_aid_uncontested_2p():
    """Both players pass → actor gains 2 coins."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision(ForeignAidAction())
    assert pd(eng).decision_type == DecisionType.BLOCK_OR_PASS
    assert pd(eng).player_index == 1
    eng.submit_decision(DecisionResponse.PASS)
    assert eng.players[0].coins == 4
    assert eng.current_turn == 1

def test_foreign_aid_uncontested_3p_queue():
    """P1 and P2 must both pass before FA resolves."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Duke(), Captain()]])
    eng.submit_decision(ForeignAidAction())
    assert pd(eng).player_index == 1
    eng.submit_decision(DecisionResponse.PASS)
    assert pd(eng).player_index == 2
    eng.submit_decision(DecisionResponse.PASS)
    assert eng.players[0].coins == 4
    assert eng.current_turn == 1

def test_foreign_aid_second_player_in_queue_blocks():
    """P1 passes, P2 blocks → challenge_block is asked only of the actor (P0)."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Duke(), Captain()]])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.PASS)   # P1
    eng.submit_decision(DecisionResponse.BLOCK)  # P2 blocks
    assert pd(eng).decision_type == DecisionType.CHALLENGE_BLOCK
    assert pd(eng).player_index == 0   # only actor can doubt block

def test_foreign_aid_block_accepted_no_coins():
    """P1 blocks; P0 accepts → no coins gained, no cards lost."""
    eng = make_engine([[Duke(), Assassin()], [Duke(), Countess()]])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.BLOCK)
    eng.submit_decision(DecisionResponse.PASS)   # P0 accepts block
    assert eng.players[0].coins == 2
    assert len(eng.players[1].influences) == 2
    assert eng.current_turn == 1

def test_foreign_aid_blocker_no_duke_doubted_loses_card_and_fa_executes():
    """Blocker claims Duke but has none → FA executes + blocker loses a card."""
    eng = make_engine([[Duke(), Assassin()], [Assassin(), Countess()]])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.BLOCK)   # P1 claims Duke (lie)
    eng.submit_decision(DecisionResponse.DOUBT)   # P0 doubts; engine finds no Duke
    assert eng.players[0].coins == 4        # FA executed
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_foreign_aid_blocker_has_duke_doubter_reveals_doubter_loses():
    """Blocker has Duke, reveals it → doubt fails, P0 loses a card, block stands."""
    eng = make_engine([[Duke(), Assassin()], [Duke(), Countess()]])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.BLOCK)
    eng.submit_decision(DecisionResponse.DOUBT)
    assert pd(eng).decision_type == DecisionType.REVEAL
    assert pd(eng).player_index == 1
    eng.submit_decision(DecisionResponse.REVEAL)
    # P0 (doubter) must lose a card
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0
    resolve_lose(eng)
    assert eng.players[0].coins == 2    # no FA coins (block held)
    assert len(eng.players[0].influences) == 1

def test_foreign_aid_blocker_refuses_to_reveal_loses_card_and_fa_executes():
    """Blocker has Duke but refuses to reveal → treated as failed block."""
    eng = make_engine([[Duke(), Assassin()], [Duke(), Countess()]])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.BLOCK)
    eng.submit_decision(DecisionResponse.DOUBT)
    assert pd(eng).decision_type == DecisionType.REVEAL
    eng.submit_decision(DecisionResponse.REFUSE)
    assert eng.players[0].coins == 4   # FA executed
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 3.  DUQUE (Tax)
# ══════════════════════════════════════════════════════════════════════════════

def test_duke_tax_uncontested_2p():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision(Duke())
    assert pd(eng).decision_type == DecisionType.CHALLENGE_ACTION
    eng.submit_decision(DecisionResponse.PASS)
    assert eng.players[0].coins == 5
    assert eng.current_turn == 1

def test_duke_tax_uncontested_3p_all_pass():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Countess(), Captain()]])
    eng.submit_decision(Duke())
    eng.submit_decision(DecisionResponse.PASS)   # P1
    eng.submit_decision(DecisionResponse.PASS)   # P2
    assert eng.players[0].coins == 5

def test_duke_tax_challenged_actor_has_duke_doubter_loses():
    """Doubter challenges; actor reveals Duke → doubter loses a card, tax collected."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision(Duke())
    eng.submit_decision(DecisionResponse.DOUBT)
    assert pd(eng).decision_type == DecisionType.REVEAL
    eng.submit_decision(DecisionResponse.REVEAL)
    # P1 (doubter) must choose card to lose
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1
    assert eng.players[0].coins == 5   # Duke tax collected

def test_duke_tax_challenged_actor_no_duke_loses_card():
    """Actor bluffs Duke; doubter is right → actor loses a card, no tax."""
    eng = make_engine([[Assassin(), Countess()], [Captain(), Duke()]])
    eng.submit_decision(Duke())   # P0 claims Duke (lie)
    eng.submit_decision(DecisionResponse.DOUBT)   # P1 doubts; engine finds no Duke
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0
    resolve_lose(eng)
    assert eng.players[0].coins == 2   # no tax
    assert len(eng.players[0].influences) == 1
    assert eng.current_turn == 1

def test_duke_tax_3p_second_player_doubts():
    """P1 passes, P2 doubts; actor has Duke → P2 loses card, tax collected."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Captain(), Countess()]])
    eng.submit_decision(Duke())
    eng.submit_decision(DecisionResponse.PASS)    # P1
    eng.submit_decision(DecisionResponse.DOUBT)   # P2
    eng.submit_decision(DecisionResponse.REVEAL)
    assert pd(eng).player_index == 2
    resolve_lose(eng)
    assert len(eng.players[2].influences) == 1
    assert eng.players[0].coins == 5


# ══════════════════════════════════════════════════════════════════════════════
# 4.  ASSASSINO (Assassination)
# ══════════════════════════════════════════════════════════════════════════════

def test_assassination_costs_3_coins():
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    assert eng.players[0].coins == 2   # paid 3

def test_assassination_accepted_target_loses_card():
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.ACCEPT)
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_assassination_target_1_card_is_eliminated():
    p0 = Player('P0', [Assassin(), Duke()])
    p1 = Player('P1', [Captain()])   # 1 card
    p0.coins = 5
    eng = GameEngine([p0, p1])
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.ACCEPT)
    assert p1.influences == []
    assert eng.is_game_over()
    assert eng.get_winner() == 'P0'

def test_assassination_block_accepted_no_card_lost():
    """Target blocks with Countess; attacker accepts → no card lost, 3 coins spent."""
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.BLOCK)   # P1 claims Countess
    eng.submit_decision(DecisionResponse.PASS)    # attacker accepts
    assert len(eng.players[1].influences) == 2
    assert eng.players[0].coins == 2   # cost already paid, not refunded

def test_assassination_block_no_countess_doubted_blocker_loses():
    """Blocker claims Countess (lie); attacker doubts → blocker loses a card."""
    eng = make_engine([[Assassin(), Duke()], [Captain(), Duke()]])   # P1 has no Countess
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.BLOCK)   # P1 claims Countess (lie)
    eng.submit_decision(DecisionResponse.DOUBT)   # P0 doubts
    # P1 loses card for bluff (causes_influence_loss=True, so no apply_effect, just card loss)
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_assassination_target_doubts_attacker_no_assassin():
    """Target doubts assassination; attacker has NO Assassin → attacker loses card."""
    eng = make_engine([[Duke(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    assert eng.players[0].coins == 2   # cost already paid
    eng.submit_decision(DecisionResponse.DOUBT_ACTION)   # P1 doubts; P0 has no Assassin
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0
    resolve_lose(eng)
    assert len(eng.players[0].influences) == 1

def test_assassination_target_doubts_attacker_has_assassin_target_loses():
    """Target doubts; attacker HAS Assassin → reveal, target loses card (assassination executes)."""
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.DOUBT_ACTION)   # P1 doubts
    assert pd(eng).decision_type == DecisionType.REVEAL
    eng.submit_decision(DecisionResponse.REVEAL)   # P0 reveals Assassin
    # doubt_action: reveal ok → assassination executes → target (P1) loses card
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 5.  CAPITÃO (Steal)
# ══════════════════════════════════════════════════════════════════════════════

def test_captain_steal_accepted_takes_2_coins():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.ACCEPT)
    assert eng.players[0].coins == 4
    assert eng.players[1].coins == 0

def test_captain_steal_target_has_1_coin_takes_only_1():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.players[1].coins = 1
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.ACCEPT)
    assert eng.players[0].coins == 3
    assert eng.players[1].coins == 0

def test_captain_steal_target_has_0_coins_takes_nothing():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.players[1].coins = 0
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.ACCEPT)
    assert eng.players[0].coins == 2
    assert eng.players[1].coins == 0

def test_captain_steal_block_accepted_no_coins_stolen():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.BLOCK)
    eng.submit_decision(DecisionResponse.PASS)   # attacker accepts block
    assert eng.players[0].coins == 2
    assert eng.players[1].coins == 2

def test_captain_steal_block_no_captain_doubted_loses_card_and_steal_executes():
    """Blocker claims Captain (lie); doubted → loses card AND coins stolen."""
    eng = make_engine([[Captain(), Duke()], [Duke(), Countess()]])   # P1 has no Captain
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.BLOCK)   # P1 claims Captain (lie)
    eng.submit_decision(DecisionResponse.DOUBT)
    assert eng.players[0].coins == 4   # steal executed
    assert eng.players[1].coins == 0
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_captain_steal_action_doubted_actor_no_captain():
    """Target doubts Captain; actor has NO Captain → actor loses card, no steal."""
    eng = make_engine([[Duke(), Duke()], [Captain(), Countess()]])
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.DOUBT_ACTION)   # P1 doubts; P0 has no Captain
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0
    resolve_lose(eng)
    assert len(eng.players[0].influences) == 1
    assert eng.players[0].coins == 2   # no coins stolen


# ══════════════════════════════════════════════════════════════════════════════
# 6.  GOLPE (Coup)
# ══════════════════════════════════════════════════════════════════════════════

def test_coup_costs_7_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    assert eng.players[0].coins == 2

def test_coup_target_2_cards_must_choose():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).options == [0, 1]
    resolve_lose(eng, card_idx=0)
    assert len(eng.players[1].influences) == 1
    # Remaining card is the one at index 1 (Countess)
    assert eng.players[1].influences[0] == Countess()

def test_coup_target_1_card_eliminated():
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1])
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    assert p1.influences == []
    assert eng.is_game_over()
    assert eng.get_winner() == 'P0'

def test_10_coins_forces_coup_only():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 10
    eng._emit_pending_decision()
    assert pd(eng).decision_type == DecisionType.PICK_ACTION
    
    print(isinstance(pd(eng).options, list))
    
    assert pd(eng).options == [CoupAction()]

def test_coup_skips_eliminated_player_in_turn():
    """After P1 is couped, turn should go to P2 (not the dead P1)."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])   # 1 card
    p2 = Player('P2', [Duke(), Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1, p2])
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)   # coup P1 (auto-eliminated)
    assert eng.current_turn == 2


# ══════════════════════════════════════════════════════════════════════════════
# 7.  TURN ORDER & ELIMINATION
# ══════════════════════════════════════════════════════════════════════════════

def test_turn_order_4p():
    eng = make_engine([
        [Duke(), Assassin()],
        [Captain(), Countess()],
        [Duke(), Captain()],
        [Assassin(), Countess()],
    ])
    for expected in [0, 1, 2, 3, 0]:
        assert eng.current_turn == expected
        eng.submit_decision(IncomeAction())

def test_eliminated_player_skipped_4p():
    """P1 and P2 eliminated; P0 → P3 → P0."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [])   # already eliminated
    p2 = Player('P2', [])   # already eliminated
    p3 = Player('P3', [Captain(), Countess()])
    eng = GameEngine([p0, p1, p2, p3])
    eng.submit_decision(IncomeAction())
    assert eng.current_turn == 3
    eng.submit_decision(IncomeAction())
    assert eng.current_turn == 0

def test_game_over_one_survivor():
    p0 = Player('P0', [Duke()])
    p1 = Player('P1', [])
    eng = GameEngine([p0, p1])
    assert eng.is_game_over()
    assert eng.get_winner() == 'P0'

def test_game_not_over_multiple_alive():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    assert not eng.is_game_over()
    assert eng.get_winner() is None

def test_game_not_over_3p():
    eng = make_engine([[Duke()], [Captain()], [Assassin()]])
    assert not eng.is_game_over()


# ══════════════════════════════════════════════════════════════════════════════
# 8.  AVAILABLE ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_available_actions_at_2_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    opts = pd(eng).options
    assert IncomeAction()     in opts
    assert ForeignAidAction() in opts
    assert Duke()             in opts
    assert Captain()          in opts
    assert Assassin()         not in opts   # needs 3 coins
    assert CoupAction()       not in opts   # needs 7 coins

def test_assassination_available_at_3_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 3
    eng._emit_pending_decision()
    assert Assassin() in pd(eng).options

def test_coup_available_at_7_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 7
    eng._emit_pending_decision()
    assert CoupAction() in pd(eng).options

def test_all_actions_available_at_7_coins_except_forced_coup():
    """At 7 coins all costly actions are available, but not forced-coup yet."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 7
    eng._emit_pending_decision()
    opts = pd(eng).options
    assert Assassin()     in opts
    assert CoupAction()   in opts
    # income and foreign aid still allowed below 10
    assert IncomeAction() in opts


# ══════════════════════════════════════════════════════════════════════════════
# 9.  LOSE INFLUENCE — card selection
# ══════════════════════════════════════════════════════════════════════════════

def test_lose_influence_choose_first_card():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    assert pd(eng).options == [0, 1]
    resolve_lose(eng, card_idx=0)
    assert eng.players[1].influences[0] == Countess()

def test_lose_influence_choose_second_card():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    resolve_lose(eng, card_idx=1)
    assert eng.players[1].influences[0] == Captain()

def test_revealed_card_goes_to_revealed_list():
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1])
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    assert p1.revealed_influences[0] == Captain()


# ══════════════════════════════════════════════════════════════════════════════
# 10.  GET STATE VIEW
# ══════════════════════════════════════════════════════════════════════════════

def test_state_view_opponent_cards_hidden():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    view = eng.get_state_view(0)
    assert view.players[1].influences == []

def test_state_view_influence_count_always_visible():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    view = eng.get_state_view(0)
    assert view.players[0].influence_count == 2
    assert view.players[1].influence_count == 2

def test_state_view_coins_visible():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[1].coins = 5
    view = eng.get_state_view(0)
    assert view.players[1].coins == 5

def test_state_view_serialises_to_dict():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    d = eng.get_state_view(0).to_dict()
    assert 'players' in d
    assert 'pending_decision' in d
    assert d['current_turn'] == 0


# ══════════════════════════════════════════════════════════════════════════════
# 11.  PLAYER CLASS (player.py)
# ══════════════════════════════════════════════════════════════════════════════

def test_player_starts_with_two_coins():
    p = Player('Alice', [Duke(), Assassin()])
    assert p.coins == 2

def test_player_stores_name():
    p = Player('Bob', [Duke()])
    assert p.name == 'Bob'

def test_player_stores_influences():
    cards = [Duke(), Assassin()]
    p = Player('P', cards)
    assert p.influences is cards

def test_player_revealed_starts_empty():
    p = Player('P', [Duke()])
    assert p.revealed_influences == []

def test_player_alive_when_has_cards():
    p = Player('P', [Duke()])
    assert bool(p.influences) is True

def test_player_eliminated_when_no_cards():
    p = Player('P', [])
    assert bool(p.influences) is False


# ══════════════════════════════════════════════════════════════════════════════
# 12.  ACTION EFFECTS (actions.py)
# ══════════════════════════════════════════════════════════════════════════════

# -- IncomeEffect --

def test_income_effect_apply_adds_one_coin():
    p = Player('P', [Duke()])
    IncomeEffect().apply(p)
    assert p.coins == 3

def test_income_effect_not_challengeable():
    assert IncomeEffect().is_challengeable() is False

def test_income_effect_not_open_blockable():
    assert IncomeEffect().is_open_blockable() is False

def test_income_effect_can_use_always():
    p = Player('P', [Duke()])
    p.coins = 0
    assert IncomeEffect().can_use(p) is True

def test_income_effect_does_not_require_target():
    assert IncomeEffect().requires_target() is False

def test_income_effect_does_not_cause_loss():
    assert IncomeEffect().causes_influence_loss() is False

# -- ForeignAidEffect --

def test_foreignaid_effect_not_challengeable():
    assert ForeignAidEffect().is_challengeable() is False

def test_foreignaid_effect_open_blockable():
    assert ForeignAidEffect().is_open_blockable() is True

def test_foreignaid_effect_apply_effect_adds_two_coins():
    p = Player('P', [Duke()])
    ForeignAidEffect().apply_effect(p)
    assert p.coins == 4

def test_foreignaid_effect_does_not_cause_loss():
    assert ForeignAidEffect().causes_influence_loss() is False

# -- TaxEffect --

def test_tax_effect_apply_adds_three_coins():
    p = Player('P', [Duke()])
    TaxEffect().apply(p)
    assert p.coins == 5

def test_tax_effect_is_challengeable():
    assert TaxEffect().is_challengeable() is True

def test_tax_effect_does_not_require_target():
    assert TaxEffect().requires_target() is False

def test_tax_effect_does_not_cause_loss():
    assert TaxEffect().causes_influence_loss() is False

# -- AssassinationEffect --

def test_assassination_effect_requires_target():
    assert AssassinationEffect().requires_target() is True

def test_assassination_effect_can_use_with_three_coins():
    p = Player('P', [Duke()])
    p.coins = 3
    assert AssassinationEffect().can_use(p) is True

def test_assassination_effect_cannot_use_with_two_coins():
    p = Player('P', [Duke()])
    p.coins = 2
    assert AssassinationEffect().can_use(p) is False

def test_assassination_effect_costs_three_coins():
    p = Player('P', [Duke()])
    p.coins = 5
    AssassinationEffect().apply_cost(p)
    assert p.coins == 2

def test_assassination_effect_causes_influence_loss():
    assert AssassinationEffect().causes_influence_loss() is True

def test_assassination_effect_is_challengeable():
    assert AssassinationEffect().is_challengeable() is True

# -- StealEffect --

def test_steal_effect_requires_target():
    assert StealEffect().requires_target() is True

def test_steal_effect_steals_two_coins():
    actor  = Player('A', [Captain()])
    target = Player('T', [Captain()])
    StealEffect().apply_effect(actor, target)
    assert actor.coins  == 4
    assert target.coins == 0

def test_steal_effect_steals_one_when_target_has_one():
    actor  = Player('A', [Captain()])
    target = Player('T', [Captain()])
    target.coins = 1
    StealEffect().apply_effect(actor, target)
    assert actor.coins  == 3
    assert target.coins == 0

def test_steal_effect_steals_nothing_when_target_broke():
    actor  = Player('A', [Captain()])
    target = Player('T', [Captain()])
    target.coins = 0
    StealEffect().apply_effect(actor, target)
    assert actor.coins  == 2
    assert target.coins == 0

def test_steal_effect_does_not_cause_loss():
    assert StealEffect().causes_influence_loss() is False

def test_steal_effect_is_challengeable():
    assert StealEffect().is_challengeable() is True

# -- CoupEffect --

def test_coup_effect_requires_target():
    assert CoupEffect().requires_target() is True

def test_coup_effect_can_use_with_seven_coins():
    p = Player('P', [Duke()])
    p.coins = 7
    assert CoupEffect().can_use(p) is True

def test_coup_effect_cannot_use_with_six_coins():
    p = Player('P', [Duke()])
    p.coins = 6
    assert CoupEffect().can_use(p) is False

def test_coup_effect_costs_seven_coins():
    p = Player('P', [Duke()])
    p.coins = 9
    CoupEffect().apply_cost(p)
    assert p.coins == 2

def test_coup_effect_not_challengeable():
    assert CoupEffect().is_challengeable() is False

def test_coup_effect_causes_influence_loss():
    assert CoupEffect().causes_influence_loss() is True


# ══════════════════════════════════════════════════════════════════════════════
# 13.  INFLUENCE CLASSES (influences.py)
# ══════════════════════════════════════════════════════════════════════════════

# -- Duke --

def test_duke_collects_three_coins():
    p = Player('P', [Duke()])
    Duke().apply(p)
    assert p.coins == 5

def test_duke_is_challengeable():
    assert Duke().is_challengeable() is True

def test_duke_has_no_blockers():
    assert Duke().get_blockers() == []

def test_duke_does_not_require_target():
    assert Duke().requires_target() is False

def test_duke_does_not_cause_loss():
    assert Duke().causes_influence_loss() is False

# -- Assassin --

def test_assassin_is_challengeable():
    assert Assassin().is_challengeable() is True

def test_assassin_requires_target():
    assert Assassin().requires_target() is True

def test_assassin_causes_influence_loss():
    assert Assassin().causes_influence_loss() is True

def test_assassin_blocked_by_countess():
    blockers = Assassin().get_blockers()
    assert len(blockers) == 1
    assert blockers[0]() == Countess()

def test_assassin_cannot_use_with_two_coins():
    p = Player('P', [Assassin()])
    assert Assassin().can_use(p) is False

def test_assassin_can_use_with_three_coins():
    p = Player('P', [Assassin()])
    p.coins = 3
    assert Assassin().can_use(p) is True

def test_assassin_has_defense():
    assert Assassin().has_defense() is True

# -- Captain --

def test_captain_is_challengeable():
    assert Captain().is_challengeable() is True

def test_captain_requires_target():
    assert Captain().requires_target() is True

def test_captain_does_not_cause_influence_loss():
    assert Captain().causes_influence_loss() is False

def test_captain_blocked_by_captain():
    blockers = Captain().get_blockers()
    assert len(blockers) == 1
    assert blockers[0]() == Captain()

def test_captain_has_defense():
    assert Captain().has_defense() is True

# -- Countess --

def test_countess_has_no_action():
    assert Countess().get_action() is None

def test_countess_no_blockers():
    assert Countess().get_blockers() == []

def test_countess_does_not_require_target():
    assert Countess().requires_target() is False

def test_countess_does_not_cause_loss():
    assert Countess().causes_influence_loss() is False

def test_countess_has_no_defense():
    assert Countess().has_defense() is False

# -- IncomeAction --

def test_incomeaction_not_challengeable():
    assert IncomeAction().is_challengeable() is False

def test_incomeaction_not_open_blockable():
    assert IncomeAction().is_open_blockable() is False

def test_incomeaction_does_not_require_target():
    assert IncomeAction().requires_target() is False

# -- ForeignAidAction --

def test_foreignaidaction_open_blockable():
    assert ForeignAidAction().is_open_blockable() is True

def test_foreignaidaction_not_challengeable():
    assert ForeignAidAction().is_challengeable() is False

def test_foreignaidaction_blocked_by_duke():
    blockers = ForeignAidAction().get_blockers()
    assert len(blockers) == 1
    assert blockers[0]() == Duke()

# -- CoupAction --

def test_coupaction_not_challengeable():
    assert CoupAction().is_challengeable() is False

def test_coupaction_requires_target():
    assert CoupAction().requires_target() is True

def test_coupaction_causes_loss():
    assert CoupAction().causes_influence_loss() is True

def test_coupaction_no_blockers():
    assert CoupAction().get_blockers() == []


# ══════════════════════════════════════════════════════════════════════════════
# 14.  GAME STATE DATACLASSES (game_state.py)
# ══════════════════════════════════════════════════════════════════════════════

def test_pending_decision_to_dict_has_all_fields():
    pd = PendingDecision(player_index=0, decision_type=DecisionType.PICK_ACTION, options=[IncomeAction()])
    d = pd.to_dict()
    for key in ('player_index', 'decision_type', 'options', 'context'):
        assert key in d

def test_pending_decision_default_context_empty():
    pd = PendingDecision(player_index=0, decision_type=DecisionType.PICK_ACTION, options=[])
    assert pd.context == {}

def test_player_state_view_to_dict_has_all_fields():
    psv = PlayerStateView(index=0, name='P0', coins=3, influence_count=2,
                          influences=['Duque'], revealed_influences=[], is_eliminated=False)
    d = psv.to_dict()
    for key in ('index', 'name', 'coins', 'influence_count',
                 'influences', 'revealed_influences', 'is_eliminated'):
        assert key in d

def test_game_state_view_to_dict_pending_none():
    psv = PlayerStateView(index=0, name='P0', coins=2, influence_count=2,
                          influences=[], revealed_influences=[], is_eliminated=False)
    gsv = GameStateView(players=[psv], current_turn=0, pending_decision=None, viewer_index=0)
    assert gsv.to_dict()['pending_decision'] is None

def test_game_state_view_to_dict_has_correct_player_count():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    d = eng.get_state_view(0).to_dict()
    assert len(d['players']) == 2

def test_phase_reveal_doubter_defaults_none():
    pr = PhaseReveal(
        challenged_player=0, card_name='Duque',
        context=RevealContext.DOUBT_ACTION,
        attacker=0, target=1, action=Duke(), next_turn=1,
    )
    assert pr.doubter is None

def test_phase_lose_influence_fields():
    pli = PhaseLoseInfluence(target_idx=2, next_turn=3)
    assert pli.target_idx == 2
    assert pli.next_turn == 3


# ══════════════════════════════════════════════════════════════════════════════
# 15.  4-PLAYER ENGINE SCENARIOS
# ══════════════════════════════════════════════════════════════════════════════

def test_4p_foreign_aid_all_pass_actor_gains_two():
    """All three opponents pass → FA executes."""
    eng = make_engine([
        [Duke(), Assassin()],
        [Captain(), Countess()],
        [Duke(), Captain()],
        [Assassin(), Countess()],
    ])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.PASS)  # P1
    eng.submit_decision(DecisionResponse.PASS)  # P2
    eng.submit_decision(DecisionResponse.PASS)  # P3
    assert eng.players[0].coins == 4

def test_4p_foreign_aid_third_player_blocks():
    """P1 and P2 pass; P3 blocks → challenge_block for P0 only."""
    eng = make_engine([
        [Duke(), Assassin()],
        [Captain(), Countess()],
        [Captain(), Countess()],
        [Duke(), Captain()],
    ])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.PASS)   # P1
    eng.submit_decision(DecisionResponse.PASS)   # P2
    eng.submit_decision(DecisionResponse.BLOCK)  # P3 blocks
    assert pd(eng).decision_type == DecisionType.CHALLENGE_BLOCK
    assert pd(eng).player_index == 0   # only actor challenges block

def test_4p_duke_tax_all_pass():
    """P1, P2, P3 all pass → P0 gains 3 coins."""
    eng = make_engine([
        [Duke(), Assassin()],
        [Captain(), Countess()],
        [Duke(), Captain()],
        [Assassin(), Countess()],
    ])
    eng.submit_decision(Duke())
    eng.submit_decision(DecisionResponse.PASS)  # P1
    eng.submit_decision(DecisionResponse.PASS)  # P2
    eng.submit_decision(DecisionResponse.PASS)  # P3
    assert eng.players[0].coins == 5

def test_4p_duke_tax_p1_passes_p2_doubts_actor_has_duke():
    """P1 passes, P2 doubts; actor reveals Duke → P2 loses card, tax collected."""
    eng = make_engine([
        [Duke(), Assassin()],
        [Captain(), Countess()],
        [Captain(), Countess()],
        [Assassin(), Duke()],
    ])
    eng.submit_decision(Duke())
    eng.submit_decision(DecisionResponse.PASS)    # P1
    eng.submit_decision(DecisionResponse.DOUBT)   # P2 doubts
    eng.submit_decision(DecisionResponse.REVEAL)  # P0 reveals Duke
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 2
    resolve_lose(eng)
    assert eng.players[0].coins == 5

def test_4p_duke_tax_p3_doubts_actor_no_duke():
    """P1, P2 pass; P3 doubts; actor has no Duke → actor loses card, no tax."""
    eng = make_engine([
        [Assassin(), Countess()],
        [Captain(), Duke()],
        [Captain(), Countess()],
        [Assassin(), Duke()],
    ])
    eng.submit_decision(Duke())   # P0 bluffs Duke
    eng.submit_decision(DecisionResponse.PASS)    # P1
    eng.submit_decision(DecisionResponse.PASS)    # P2
    eng.submit_decision(DecisionResponse.DOUBT)   # P3 doubts — correct!
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0
    resolve_lose(eng)
    assert eng.players[0].coins == 2   # no tax

def test_4p_skips_two_pre_eliminated_players():
    """P1 and P2 pre-eliminated; after P0 takes income, turn goes to P3."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [])   # eliminated
    p2 = Player('P2', [])   # eliminated
    p3 = Player('P3', [Captain(), Countess()])
    eng = GameEngine([p0, p1, p2, p3])
    eng.submit_decision(IncomeAction())
    assert eng.current_turn == 3

def test_4p_turn_order_full_cycle():
    """4 players, each takes income; verify 0→1→2→3→0→1."""
    eng = make_engine([
        [Duke(), Assassin()],
        [Captain(), Countess()],
        [Duke(), Captain()],
        [Assassin(), Countess()],
    ])
    for expected in [0, 1, 2, 3, 0, 1]:
        assert eng.current_turn == expected
        eng.submit_decision(IncomeAction())

def test_3p_coup_eliminates_p1_turn_goes_to_p2():
    """P0 coups P1 (1 card); turn advances to P2, skipping dead P1."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])   # 1 card — auto-eliminated by coup
    p2 = Player('P2', [Duke(), Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1, p2])
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    assert eng.current_turn == 2

def test_fa_queue_skips_pre_eliminated_player():
    """FA block queue only includes alive players."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [])   # eliminated — must NOT appear in queue
    p2 = Player('P2', [Captain(), Countess()])
    p3 = Player('P3', [Duke(), Captain()])
    eng = GameEngine([p0, p1, p2, p3])
    eng.submit_decision(ForeignAidAction())
    # P1 is eliminated; first in queue should be P2
    assert pd(eng).player_index == 2

def test_challenge_queue_skips_pre_eliminated_player():
    """Duke tax challenge queue only includes alive players."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [])   # eliminated
    p2 = Player('P2', [Captain(), Countess()])
    eng = GameEngine([p0, p1, p2])
    eng.submit_decision(Duke())
    # Only P2 should be in queue (P1 is dead)
    assert pd(eng).player_index == 2


# ══════════════════════════════════════════════════════════════════════════════
# 16.  REVEAL SEQUENCES (all three RevealContext paths)
# ══════════════════════════════════════════════════════════════════════════════

# ── DOUBT_ACTION (targeted action doubted by the target) ─────────────────────

def test_doubt_action_actor_refuses_action_cancelled_actor_loses():
    """Target doubts Assassin; attacker refuses to reveal → action cancelled, attacker loses card."""
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.DOUBT_ACTION)
    eng.submit_decision(DecisionResponse.REFUSE)   # attacker refuses even though they have Assassin
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0
    resolve_lose(eng)
    assert len(eng.players[0].influences) == 1
    assert len(eng.players[1].influences) == 2   # target untouched

def test_doubt_action_captain_actor_reveals_steal_executes_doubter_loses():
    """Target doubts Captain steal; actor reveals Captain → doubt fails, target loses card."""
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.DOUBT_ACTION)   # P1 doubts
    assert pd(eng).decision_type == DecisionType.REVEAL
    eng.submit_decision(DecisionResponse.REVEAL)         # P0 reveals Captain — doubt fails → steal executes
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1
    assert eng.players[0].coins == 4      # steal executed

# ── DOUBT_BLOCK (attacker doubts a claimed block) ────────────────────────────

def test_doubt_block_blocker_has_captain_reveals_doubter_loses_no_steal():
    """P0 steals; P1 blocks with Captain (has it); P0 doubts; P1 reveals → P0 loses, no steal."""
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.BLOCK)   # P1 blocks with Captain (legit)
    eng.submit_decision(DecisionResponse.DOUBT)   # P0 doubts
    assert pd(eng).decision_type == DecisionType.REVEAL
    assert pd(eng).player_index == 1
    eng.submit_decision(DecisionResponse.REVEAL)  # P1 reveals Captain — doubt fails
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0   # doubter loses
    resolve_lose(eng)
    assert len(eng.players[0].influences) == 1
    assert eng.players[0].coins == 2   # no steal (block succeeded)
    assert eng.players[1].coins == 2   # no coins lost

def test_doubt_block_blocker_has_duke_refuses_fa_executes_blocker_loses():
    """FA blocked; attacker doubts; blocker HAS Duke but refuses → FA executes + blocker loses."""
    eng = make_engine([[Duke(), Assassin()], [Duke(), Countess()]])
    eng.submit_decision(ForeignAidAction())
    eng.submit_decision(DecisionResponse.BLOCK)   # P1 blocks (has Duke)
    eng.submit_decision(DecisionResponse.DOUBT)   # P0 doubts
    eng.submit_decision(DecisionResponse.REFUSE)  # P1 refuses to reveal even though they have Duke
    assert eng.players[0].coins == 4   # FA executed
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_doubt_block_no_card_immediate_steal_executes():
    """Captain steal block doubted; blocker has no Captain → steal executes immediately."""
    eng = make_engine([[Captain(), Duke()], [Duke(), Countess()]])   # P1 has no Captain
    eng.submit_decision(Captain())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.BLOCK)   # P1 claims Captain (lie)
    eng.submit_decision(DecisionResponse.DOUBT)   # P0 doubts; no reveal phase
    assert eng.players[0].coins == 4
    assert eng.players[1].coins == 0
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1

# ── DOUBT_OPEN (non-targeted card action challenged by any player) ────────────

def test_doubt_open_actor_has_duke_reveals_doubter_loses_tax_collected():
    """P1 doubts Duke tax; P0 reveals Duke → P1 loses card, tax collected."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision(Duke())
    eng.submit_decision(DecisionResponse.DOUBT)   # DOUBT_OPEN context
    eng.submit_decision(DecisionResponse.REVEAL)  # P0 reveals Duke
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 1
    resolve_lose(eng)
    assert eng.players[0].coins == 5

def test_doubt_open_actor_refuses_loses_card_no_tax():
    """P1 doubts Duke tax; actor refuses to reveal → actor loses card, no tax."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision(Duke())
    eng.submit_decision(DecisionResponse.DOUBT)
    eng.submit_decision(DecisionResponse.REFUSE)   # P0 refuses even though they have Duke
    assert pd(eng).decision_type == DecisionType.LOSE_INFLUENCE
    assert pd(eng).player_index == 0
    resolve_lose(eng)
    assert eng.players[0].coins == 2   # no tax


# ══════════════════════════════════════════════════════════════════════════════
# 17.  EDGE CASES & COIN BOUNDARIES
# ══════════════════════════════════════════════════════════════════════════════

def test_income_accumulates_over_multiple_rounds():
    """Three rounds of income for P0 → 2 + 3 = 5 coins."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    for _ in range(3):
        eng.submit_decision(IncomeAction())  # P0
        eng.submit_decision(IncomeAction())  # P1
    assert eng.players[0].coins == 5

def test_assassination_unavailable_at_2_coins():
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    assert Assassin() not in pd(eng).options

def test_assassination_available_at_exactly_3_coins():
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 3
    eng._emit_pending_decision()
    assert Assassin() in pd(eng).options

def test_coup_unavailable_at_6_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 6
    eng._emit_pending_decision()
    assert CoupAction() not in pd(eng).options

def test_coup_available_at_exactly_7_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 7
    eng._emit_pending_decision()
    assert CoupAction() in pd(eng).options

def test_no_pending_decision_when_game_already_over():
    """Game starts over (P1 dead) → pending_decision is None."""
    p0 = Player('P0', [Duke()])
    p1 = Player('P1', [])
    eng = GameEngine([p0, p1])
    assert eng.pending_decision is None

def test_get_winner_returns_none_when_two_alive():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    assert eng.get_winner() is None

def test_get_winner_returns_correct_name():
    p0 = Player('Alice', [Duke()])
    p1 = Player('Bob', [])
    eng = GameEngine([p0, p1])
    assert eng.get_winner() == 'Alice'

def test_is_game_over_false_when_two_alive():
    eng = make_engine([[Duke()], [Captain()]])
    assert eng.is_game_over() is False

def test_is_game_over_true_when_one_alive():
    p0 = Player('P0', [Duke()])
    p1 = Player('P1', [])
    eng = GameEngine([p0, p1])
    assert eng.is_game_over() is True

def test_state_view_viewer_index_stored():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    assert eng.get_state_view(1).viewer_index == 1

def test_state_view_is_eliminated_flag_correct():
    p0 = Player('P0', [Duke()])
    p1 = Player('P1', [])   # eliminated
    eng = GameEngine([p0, p1])
    view = eng.get_state_view(0)
    assert view.players[0].is_eliminated is False
    assert view.players[1].is_eliminated is True

def test_coup_kills_last_card_game_ends_no_pending():
    """Coup on a 1-card player ends the game; pending_decision becomes None."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1])
    eng.submit_decision(CoupAction())
    eng.submit_decision(1)
    assert eng.is_game_over()
    assert eng.pending_decision is None

def test_assassination_coins_not_refunded_when_doubted_and_no_card():
    """Attacker bluffs Assassin, gets doubted, loses card — 3 coins already spent, not refunded."""
    eng = make_engine([[Duke(), Countess()], [Captain(), Duke()]])   # P0 has no Assassin
    eng.players[0].coins = 5
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    assert eng.players[0].coins == 2   # 5 - 3 = 2 (cost paid upfront)
    eng.submit_decision(DecisionResponse.DOUBT_ACTION)   # P1 doubts; P0 has no Assassin
    resolve_lose(eng)
    assert eng.players[0].coins == 2   # no refund

def test_3p_fa_queue_order_p1_before_p2():
    """Verify FA queue asks P1 first, then P2 in a 3-player game."""
    eng = make_engine([
        [Duke(), Assassin()],
        [Captain(), Countess()],
        [Duke(), Captain()],
    ])
    eng.submit_decision(ForeignAidAction())
    assert pd(eng).player_index == 1
    eng.submit_decision(DecisionResponse.PASS)
    assert pd(eng).player_index == 2

def test_assassination_3p_target_eliminated_game_continues():
    """P0 assassinates P1 (1-card); game continues (P2 still alive)."""
    p0 = Player('P0', [Assassin(), Duke()])
    p1 = Player('P1', [Captain()])   # 1 card
    p2 = Player('P2', [Duke(), Countess()])
    p0.coins = 5
    eng = GameEngine([p0, p1, p2])
    eng.submit_decision(Assassin())
    eng.submit_decision(1)
    eng.submit_decision(DecisionResponse.ACCEPT)
    # P1 auto-eliminated (1 card); game NOT over (P2 still alive)
    assert not eng.is_game_over()
    assert eng.current_turn == 2   # skips dead P1

