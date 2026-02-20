"""
Test suite for GameEngine — covers coins, influence losses, turn order,
all 6 actions, challenges, blocks, and edge cases across 2-4 players.

Each test function is an independent scenario.  Helper make_engine() sets up
players with the exact cards needed, so every assertion is deterministic.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from game_engine import GameEngine
from player import Player
from influences import Assassin, Duke, Countess, Captain, IncomeAction, ForeignAidAction, CoupAction


# ─── helper ───────────────────────────────────────────────────────────────────

def make_engine(player_cards: list[list]) -> GameEngine:
    """Build an engine with deterministic card layouts.  All players start with 2 coins."""
    players = [Player(name=f"P{i}", influences=cards) for i, cards in enumerate(player_cards)]
    return GameEngine(players)


def resolve_lose(eng: GameEngine, card_idx: int = 0):
    """Submit a lose_influence decision (choose card at card_idx)."""
    assert eng.pending_decision.decision_type == 'lose_influence'
    eng.submit_decision(card_idx)


# ══════════════════════════════════════════════════════════════════════════════
# 1.  RENDA (Income)
# ══════════════════════════════════════════════════════════════════════════════

def test_income_gives_one_coin():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision('Renda')
    assert eng.players[0].coins == 3

def test_income_turn_advances_2p():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision('Renda')
    assert eng.current_turn == 1

def test_income_turn_cycles_3p():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Duke(), Captain()]])
    eng.submit_decision('Renda')   # P0
    assert eng.current_turn == 1
    eng.submit_decision('Renda')   # P1
    assert eng.current_turn == 2
    eng.submit_decision('Renda')   # P2
    assert eng.current_turn == 0


# ══════════════════════════════════════════════════════════════════════════════
# 2.  AJUDA EXTERNA (Foreign Aid)
# ══════════════════════════════════════════════════════════════════════════════

def test_foreign_aid_uncontested_2p():
    """Both players pass → actor gains 2 coins."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision('Ajuda Externa')
    assert eng.pending_decision.decision_type == 'block_or_pass'
    assert eng.pending_decision.player_index == 1
    eng.submit_decision('pass')
    assert eng.players[0].coins == 4
    assert eng.current_turn == 1

def test_foreign_aid_uncontested_3p_queue():
    """P1 and P2 must both pass before FA resolves."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Duke(), Captain()]])
    eng.submit_decision('Ajuda Externa')
    assert eng.pending_decision.player_index == 1
    eng.submit_decision('pass')
    assert eng.pending_decision.player_index == 2
    eng.submit_decision('pass')
    assert eng.players[0].coins == 4
    assert eng.current_turn == 1

def test_foreign_aid_second_player_in_queue_blocks():
    """P1 passes, P2 blocks → challenge_block is asked only of the actor (P0)."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Duke(), Captain()]])
    eng.submit_decision('Ajuda Externa')
    eng.submit_decision('pass')   # P1
    eng.submit_decision('block')  # P2 blocks
    assert eng.pending_decision.decision_type == 'challenge_block'
    assert eng.pending_decision.player_index == 0   # only actor can doubt block

def test_foreign_aid_block_accepted_no_coins():
    """P1 blocks; P0 accepts → no coins gained, no cards lost."""
    eng = make_engine([[Duke(), Assassin()], [Duke(), Countess()]])
    eng.submit_decision('Ajuda Externa')
    eng.submit_decision('block')
    eng.submit_decision('pass')   # P0 accepts block
    assert eng.players[0].coins == 2
    assert len(eng.players[1].influences) == 2
    assert eng.current_turn == 1

def test_foreign_aid_blocker_no_duke_doubted_loses_card_and_fa_executes():
    """Blocker claims Duke but has none → FA executes + blocker loses a card."""
    eng = make_engine([[Duke(), Assassin()], [Assassin(), Countess()]])
    eng.submit_decision('Ajuda Externa')
    eng.submit_decision('block')   # P1 claims Duke (lie)
    eng.submit_decision('doubt')   # P0 doubts; engine finds no Duke
    assert eng.players[0].coins == 4        # FA executed
    assert eng.pending_decision.decision_type == 'lose_influence'
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_foreign_aid_blocker_has_duke_doubter_reveals_doubter_loses():
    """Blocker has Duke, reveals it → doubt fails, P0 loses a card, block stands."""
    eng = make_engine([[Duke(), Assassin()], [Duke(), Countess()]])
    eng.submit_decision('Ajuda Externa')
    eng.submit_decision('block')
    eng.submit_decision('doubt')
    assert eng.pending_decision.decision_type == 'reveal'
    assert eng.pending_decision.player_index == 1
    eng.submit_decision('reveal')
    # P0 (doubter) must lose a card
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 0
    resolve_lose(eng)
    assert eng.players[0].coins == 2    # no FA coins (block held)
    assert len(eng.players[0].influences) == 1

def test_foreign_aid_blocker_refuses_to_reveal_loses_card_and_fa_executes():
    """Blocker has Duke but refuses to reveal → treated as failed block."""
    eng = make_engine([[Duke(), Assassin()], [Duke(), Countess()]])
    eng.submit_decision('Ajuda Externa')
    eng.submit_decision('block')
    eng.submit_decision('doubt')
    assert eng.pending_decision.decision_type == 'reveal'
    eng.submit_decision('refuse')
    assert eng.players[0].coins == 4   # FA executed
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 3.  DUQUE (Tax)
# ══════════════════════════════════════════════════════════════════════════════

def test_duke_tax_uncontested_2p():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision('Duque')
    assert eng.pending_decision.decision_type == 'challenge_action'
    eng.submit_decision('pass')
    assert eng.players[0].coins == 5
    assert eng.current_turn == 1

def test_duke_tax_uncontested_3p_all_pass():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Countess(), Captain()]])
    eng.submit_decision('Duque')
    eng.submit_decision('pass')   # P1
    eng.submit_decision('pass')   # P2
    assert eng.players[0].coins == 5

def test_duke_tax_challenged_actor_has_duke_doubter_loses():
    """Doubter challenges; actor reveals Duke → doubter loses a card, tax collected."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.submit_decision('Duque')
    eng.submit_decision('doubt')
    assert eng.pending_decision.decision_type == 'reveal'
    eng.submit_decision('reveal')
    # P1 (doubter) must choose card to lose
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1
    assert eng.players[0].coins == 5   # Duke tax collected

def test_duke_tax_challenged_actor_no_duke_loses_card():
    """Actor bluffs Duke; doubter is right → actor loses a card, no tax."""
    eng = make_engine([[Assassin(), Countess()], [Captain(), Duke()]])
    eng.submit_decision('Duque')   # P0 claims Duke (lie)
    eng.submit_decision('doubt')   # P1 doubts; engine finds no Duke
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 0
    resolve_lose(eng)
    assert eng.players[0].coins == 2   # no tax
    assert len(eng.players[0].influences) == 1
    assert eng.current_turn == 1

def test_duke_tax_3p_second_player_doubts():
    """P1 passes, P2 doubts; actor has Duke → P2 loses card, tax collected."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()], [Captain(), Countess()]])
    eng.submit_decision('Duque')
    eng.submit_decision('pass')    # P1
    eng.submit_decision('doubt')   # P2
    eng.submit_decision('reveal')
    assert eng.pending_decision.player_index == 2
    resolve_lose(eng)
    assert len(eng.players[2].influences) == 1
    assert eng.players[0].coins == 5


# ══════════════════════════════════════════════════════════════════════════════
# 4.  ASSASSINO (Assassination)
# ══════════════════════════════════════════════════════════════════════════════

def test_assassination_costs_3_coins():
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision('Assassino')
    eng.submit_decision(1)
    assert eng.players[0].coins == 2   # paid 3

def test_assassination_accepted_target_loses_card():
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision('Assassino')
    eng.submit_decision(1)
    eng.submit_decision('accept')
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_assassination_target_1_card_is_eliminated():
    p0 = Player('P0', [Assassin(), Duke()])
    p1 = Player('P1', [Captain()])   # 1 card
    p0.coins = 5
    eng = GameEngine([p0, p1])
    eng.submit_decision('Assassino')
    eng.submit_decision(1)
    eng.submit_decision('accept')
    assert p1.influences == []
    assert eng.is_game_over()
    assert eng.get_winner() == 'P0'

def test_assassination_block_accepted_no_card_lost():
    """Target blocks with Countess; attacker accepts → no card lost, 3 coins spent."""
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision('Assassino')
    eng.submit_decision(1)
    eng.submit_decision('block')   # P1 claims Countess
    eng.submit_decision('pass')    # attacker accepts
    assert len(eng.players[1].influences) == 2
    assert eng.players[0].coins == 2   # cost already paid, not refunded

def test_assassination_block_no_countess_doubted_blocker_loses():
    """Blocker claims Countess (lie); attacker doubts → blocker loses a card."""
    eng = make_engine([[Assassin(), Duke()], [Captain(), Duke()]])   # P1 has no Countess
    eng.players[0].coins = 5
    eng.submit_decision('Assassino')
    eng.submit_decision(1)
    eng.submit_decision('block')   # P1 claims Countess (lie)
    eng.submit_decision('doubt')   # P0 doubts
    # P1 loses card for bluff (causes_influence_loss=True, so no apply_effect, just card loss)
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_assassination_target_doubts_attacker_no_assassin():
    """Target doubts assassination; attacker has NO Assassin → attacker loses card."""
    eng = make_engine([[Duke(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision('Assassino')
    eng.submit_decision(1)
    assert eng.players[0].coins == 2   # cost already paid
    eng.submit_decision('doubt_action')   # P1 doubts; P0 has no Assassin
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 0
    resolve_lose(eng)
    assert len(eng.players[0].influences) == 1

def test_assassination_target_doubts_attacker_has_assassin_target_loses():
    """Target doubts; attacker HAS Assassin → reveal, target loses card (assassination executes)."""
    eng = make_engine([[Assassin(), Duke()], [Captain(), Countess()]])
    eng.players[0].coins = 5
    eng.submit_decision('Assassino')
    eng.submit_decision(1)
    eng.submit_decision('doubt_action')   # P1 doubts
    assert eng.pending_decision.decision_type == 'reveal'
    eng.submit_decision('reveal')   # P0 reveals Assassin
    # doubt_action: reveal ok → assassination executes → target (P1) loses card
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 5.  CAPITÃO (Steal)
# ══════════════════════════════════════════════════════════════════════════════

def test_captain_steal_accepted_takes_2_coins():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.submit_decision('Capitao')
    eng.submit_decision(1)
    eng.submit_decision('accept')
    assert eng.players[0].coins == 4
    assert eng.players[1].coins == 0

def test_captain_steal_target_has_1_coin_takes_only_1():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.players[1].coins = 1
    eng.submit_decision('Capitao')
    eng.submit_decision(1)
    eng.submit_decision('accept')
    assert eng.players[0].coins == 3
    assert eng.players[1].coins == 0

def test_captain_steal_target_has_0_coins_takes_nothing():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.players[1].coins = 0
    eng.submit_decision('Capitao')
    eng.submit_decision(1)
    eng.submit_decision('accept')
    assert eng.players[0].coins == 2
    assert eng.players[1].coins == 0

def test_captain_steal_block_accepted_no_coins_stolen():
    eng = make_engine([[Captain(), Duke()], [Captain(), Countess()]])
    eng.submit_decision('Capitao')
    eng.submit_decision(1)
    eng.submit_decision('block')
    eng.submit_decision('pass')   # attacker accepts block
    assert eng.players[0].coins == 2
    assert eng.players[1].coins == 2

def test_captain_steal_block_no_captain_doubted_loses_card_and_steal_executes():
    """Blocker claims Captain (lie); doubted → loses card AND coins stolen."""
    eng = make_engine([[Captain(), Duke()], [Duke(), Countess()]])   # P1 has no Captain
    eng.submit_decision('Capitao')
    eng.submit_decision(1)
    eng.submit_decision('block')   # P1 claims Captain (lie)
    eng.submit_decision('doubt')
    assert eng.players[0].coins == 4   # steal executed
    assert eng.players[1].coins == 0
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 1
    resolve_lose(eng)
    assert len(eng.players[1].influences) == 1

def test_captain_steal_action_doubted_actor_no_captain():
    """Target doubts Captain; actor has NO Captain → actor loses card, no steal."""
    eng = make_engine([[Duke(), Duke()], [Captain(), Countess()]])
    eng.submit_decision('Capitao')
    eng.submit_decision(1)
    eng.submit_decision('doubt_action')   # P1 doubts; P0 has no Captain
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.player_index == 0
    resolve_lose(eng)
    assert len(eng.players[0].influences) == 1
    assert eng.players[0].coins == 2   # no coins stolen


# ══════════════════════════════════════════════════════════════════════════════
# 6.  GOLPE (Coup)
# ══════════════════════════════════════════════════════════════════════════════

def test_coup_costs_7_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision('Golpe')
    eng.submit_decision(1)
    assert eng.players[0].coins == 2

def test_coup_target_2_cards_must_choose():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision('Golpe')
    eng.submit_decision(1)
    assert eng.pending_decision.decision_type == 'lose_influence'
    assert eng.pending_decision.options == [0, 1]
    resolve_lose(eng, card_idx=0)
    assert len(eng.players[1].influences) == 1
    # Remaining card is the one at index 1 (Countess)
    assert eng.players[1].influences[0].get_name() == 'Condessa'

def test_coup_target_1_card_eliminated():
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1])
    eng.submit_decision('Golpe')
    eng.submit_decision(1)
    assert p1.influences == []
    assert eng.is_game_over()
    assert eng.get_winner() == 'P0'

def test_10_coins_forces_coup_only():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 10
    eng._emit_decision()
    assert eng.pending_decision.decision_type == 'pick_action'
    assert eng.pending_decision.options == ['Golpe']

def test_coup_skips_eliminated_player_in_turn():
    """After P1 is couped, turn should go to P2 (not the dead P1)."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])   # 1 card
    p2 = Player('P2', [Duke(), Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1, p2])
    eng.submit_decision('Golpe')
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
        eng.submit_decision('Renda')

def test_eliminated_player_skipped_4p():
    """P1 and P2 eliminated; P0 → P3 → P0."""
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [])   # already eliminated
    p2 = Player('P2', [])   # already eliminated
    p3 = Player('P3', [Captain(), Countess()])
    eng = GameEngine([p0, p1, p2, p3])
    eng.submit_decision('Renda')
    assert eng.current_turn == 3
    eng.submit_decision('Renda')
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
    opts = eng.pending_decision.options
    assert 'Renda'        in opts
    assert 'Ajuda Externa' in opts
    assert 'Duque'        in opts
    assert 'Capitao'      in opts
    assert 'Assassino'    not in opts   # needs 3 coins
    assert 'Golpe'        not in opts   # needs 7 coins

def test_assassination_available_at_3_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 3
    eng._emit_decision()
    assert 'Assassino' in eng.pending_decision.options

def test_coup_available_at_7_coins():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 7
    eng._emit_decision()
    assert 'Golpe' in eng.pending_decision.options

def test_all_actions_available_at_7_coins_except_forced_coup():
    """At 7 coins all costly actions are available, but not forced-coup yet."""
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 7
    eng._emit_decision()
    opts = eng.pending_decision.options
    assert 'Assassino' in opts
    assert 'Golpe'     in opts
    # income and foreign aid still allowed below 10
    assert 'Renda' in opts


# ══════════════════════════════════════════════════════════════════════════════
# 9.  LOSE INFLUENCE — card selection
# ══════════════════════════════════════════════════════════════════════════════

def test_lose_influence_choose_first_card():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision('Golpe')
    eng.submit_decision(1)
    assert eng.pending_decision.options == [0, 1]
    resolve_lose(eng, card_idx=0)
    assert eng.players[1].influences[0].get_name() == 'Condessa'

def test_lose_influence_choose_second_card():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    eng.players[0].coins = 9
    eng.submit_decision('Golpe')
    eng.submit_decision(1)
    resolve_lose(eng, card_idx=1)
    assert eng.players[1].influences[0].get_name() == 'Capitao'

def test_revealed_card_goes_to_revealed_list():
    p0 = Player('P0', [Duke(), Assassin()])
    p1 = Player('P1', [Captain()])
    p0.coins = 9
    eng = GameEngine([p0, p1])
    eng.submit_decision('Golpe')
    eng.submit_decision(1)
    assert p1.revealed_influences[0].get_name() == 'Capitao'


# ══════════════════════════════════════════════════════════════════════════════
# 10.  GET STATE VIEW
# ══════════════════════════════════════════════════════════════════════════════

def test_state_view_own_cards_visible():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    view = eng.get_state_view(0)
    assert view.players[0].influences == ['Duque', 'Assassino']

def test_state_view_opponent_cards_hidden():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    view = eng.get_state_view(0)
    assert view.players[1].influences == []

def test_state_view_influence_count_always_visible():
    eng = make_engine([[Duke(), Assassin()], [Captain(), Countess()]])
    view = eng.get_state_view(0)
    assert view.players[0].influence_count == 2
    assert view.players[1].influence_count == 2

def test_state_view_revealed_cards_always_public():
    eng = make_engine([[Duke(), Assassin()], [Captain()]])
    eng.players[1].revealed_influences = [Duke()]
    view = eng.get_state_view(0)
    assert 'Duque' in view.players[1].revealed_influences

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
