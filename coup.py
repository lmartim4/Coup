import pygame
import random
from influences import Assassin, Duke, Countess, Captain
from player import Player

# --- Deck setup ---
def build_deck():
    deck = (
        [Assassin()] * 3 +
        [Duke()]     * 3 +
        [Countess()] * 3 +
        [Captain()]  * 3
    )
    random.shuffle(deck)
    return deck

def deal_players(names: list[str], deck: list):
    players = []
    for name in names:
        influences = [deck.pop(), deck.pop()]
        players.append(Player(name, influences))
    return players

# --- Constants ---
CARD_W  = 50
CARD_H  = 80
ROW_H   = 110
ROW_PAD = 15
CARD_GAP = 12

CARD_COLOR       = (200, 170, 100)
CARD_BORDER      = (80,  60,  30)
TEXT_COLOR       = (255, 255, 255)
BG_COLOR         = (40,  40,  60)
ACTIVE_ROW_COLOR = (60,  80,  60)
TARGET_ROW_COLOR = (80,  60,  40)

ACTION_W      = 120
ACTION_H      = 36
ACTION_GAP    = 8
ACTION_COLOR  = (70,  100, 140)
ACTION_HOVER  = (100, 140, 190)
ACTION_BORDER = (150, 200, 255)

TARGET_W      = 100
TARGET_H      = 36
TARGET_COLOR  = (140, 70,  70)
TARGET_HOVER  = (190, 110, 110)
TARGET_BORDER = (255, 160, 160)

DEFENSE_W        = 160
DEFENSE_H        = 36
DEFENSE_GAP      = 10
DEFENSE_BORDER   = (220, 220, 220)
BLOCK_COLOR      = (50,  110, 70)
BLOCK_HOVER      = (80,  150, 100)
ACCEPT_COLOR     = (140, 60,  60)
ACCEPT_HOVER     = (180, 100, 100)
DEFENSE_ROW_COLOR = (50,  50,  90)

DOUBT_ROW_COLOR  = (80,  50,  80)
LOSE_ROW_COLOR   = (100, 30,  30)
REVEAL_ROW_COLOR = (40,  70,  110)
DOUBT_COLOR      = (120, 60,  160)
DOUBT_HOVER      = (160, 90,  210)
PASS_COLOR       = (60,  60,  60)
PASS_HOVER       = (90,  90,  90)

ALL_ACTIONS = [Assassin(), Duke(), Captain()]

# --- Drawing helpers ---
def draw_card(surface, font, x, y, influence):
    rect = pygame.Rect(x, y, CARD_W, CARD_H)
    pygame.draw.rect(surface, CARD_COLOR, rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, rect, width=2, border_radius=6)
    label = pygame.transform.rotate(font.render(influence.get_name(), True, (40, 40, 40)), 90)
    surface.blit(label, (x + (CARD_W - label.get_width()) // 2,
                         y + (CARD_H - label.get_height()) // 2))

def draw_button(surface, font, x, y, w, h, text, hovered, color, hover_color, border_color):
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, hover_color if hovered else color, rect, border_radius=5)
    pygame.draw.rect(surface, border_color, rect, width=1, border_radius=5)
    label = font.render(text, True, TEXT_COLOR)
    surface.blit(label, (x + (w - label.get_width()) // 2, y + (h - label.get_height()) // 2))
    return rect

def draw_players(surface, font, players, current_turn, pending_action, pending_defense, pending_doubt, pending_lose_influence, pending_reveal, pending_action_challenge, mouse_pos):
    """
    Returns:
      action_rects      — [(rect, action)]
      target_rects      — [(rect, index)]
      defense_rects     — [(rect, 'block'|'accept')]
      doubt_rects       — [(rect, 'doubt'|'pass')]  also used for pending_action_challenge
      card_choice_rects — [(rect, card_index)]  when pending_lose_influence is set
      reveal_rects      — [(rect, 'reveal'|'refuse')]  when pending_reveal is set
    """
    action_rects      = []
    target_rects      = []
    defense_rects     = []
    doubt_rects       = []
    card_choice_rects = []
    reveal_rects      = []

    for i, player in enumerate(players):
        row_y = ROW_PAD + i * (ROW_H + ROW_PAD)
        is_active     = (i == current_turn)
        is_targetable = pending_action and i != current_turn

        # Row background
        if pending_reveal is not None and i == pending_reveal['challenged_player']:
            pygame.draw.rect(surface, REVEAL_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))
        elif pending_action_challenge is not None:
            ac_queue = pending_action_challenge['queue']
            if i == pending_action_challenge['actor']:
                pygame.draw.rect(surface, ACTIVE_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))
            elif ac_queue and i == ac_queue[0]:
                pygame.draw.rect(surface, DOUBT_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))
        elif pending_lose_influence is not None and i == pending_lose_influence['target']:
            pygame.draw.rect(surface, LOSE_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))
        elif pending_doubt is not None:
            queue = pending_doubt['queue']
            if i == pending_doubt['target']:
                pygame.draw.rect(surface, DEFENSE_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))
            elif queue and i == queue[0]:
                row_col = ACTIVE_ROW_COLOR if i == current_turn else DOUBT_ROW_COLOR
                pygame.draw.rect(surface, row_col, (0, row_y, surface.get_width(), ROW_H))
        elif pending_defense is not None and i == pending_defense[0]:
            pygame.draw.rect(surface, DEFENSE_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))
        elif is_active:
            pygame.draw.rect(surface, ACTIVE_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))
        elif is_targetable:
            pygame.draw.rect(surface, TARGET_ROW_COLOR, (0, row_y, surface.get_width(), ROW_H))

        # Player name
        name_surf = font.render(player.name, True, TEXT_COLOR)
        surface.blit(name_surf, (ROW_PAD, row_y + ROW_H // 2 - name_surf.get_height()))

        # Coins
        coins_surf = font.render(f"Moedas: {player.coins}", True, (255, 215, 0))
        surface.blit(coins_surf, (ROW_PAD, row_y + ROW_H // 2))

        # Influence cards
        card_start_x = ROW_PAD + 140
        for j, influence in enumerate(player.influences):
            draw_card(surface, font, card_start_x + j * (CARD_W + CARD_GAP),
                      row_y + (ROW_H - CARD_H) // 2, influence)

        buttons_x = card_start_x + 2 * (CARD_W + CARD_GAP) + 20

        if pending_reveal is not None:
            if i == pending_reveal['challenged_player']:
                hint = font.render(f"Provam que você tem {pending_reveal['card_name']}:", True, (180, 210, 255))
                surface.blit(hint, (buttons_x, row_y + 5))
                by = row_y + ROW_H // 2
                hov = pygame.Rect(buttons_x, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, buttons_x, by, DEFENSE_W, DEFENSE_H,
                                   "Revelar", hov, BLOCK_COLOR, BLOCK_HOVER, DEFENSE_BORDER)
                reveal_rects.append((rect, "reveal"))
                bx2 = buttons_x + DEFENSE_W + DEFENSE_GAP
                hov = pygame.Rect(bx2, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, bx2, by, DEFENSE_W, DEFENSE_H,
                                   "Recusar", hov, ACCEPT_COLOR, ACCEPT_HOVER, DEFENSE_BORDER)
                reveal_rects.append((rect, "refuse"))

        elif pending_action_challenge is not None:
            ac_queue = pending_action_challenge['queue']
            ac_actor = pending_action_challenge['actor']
            if ac_queue and i == ac_queue[0]:
                by = row_y + (ROW_H - DEFENSE_H) // 2
                hov = pygame.Rect(buttons_x, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, buttons_x, by, DEFENSE_W, DEFENSE_H,
                                   "Duvidar", hov, DOUBT_COLOR, DOUBT_HOVER, DEFENSE_BORDER)
                doubt_rects.append((rect, "doubt"))
                bx_pass = buttons_x + DEFENSE_W + DEFENSE_GAP
                hov = pygame.Rect(bx_pass, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, bx_pass, by, DEFENSE_W, DEFENSE_H,
                                   "Passar", hov, PASS_COLOR, PASS_HOVER, DEFENSE_BORDER)
                doubt_rects.append((rect, "pass"))
            elif i == ac_actor:
                reminder = font.render("Aguardando decisão dos jogadores...", True, (200, 200, 200))
                surface.blit(reminder, (buttons_x, row_y + (ROW_H - reminder.get_height()) // 2))

        elif pending_lose_influence is not None:
            if i == pending_lose_influence['target']:
                reminder = font.render("Escolha uma carta para perder:", True, (255, 150, 150))
                surface.blit(reminder, (buttons_x, row_y + 5))
                for j, inf in enumerate(player.influences):
                    bx = buttons_x + j * (ACTION_W + ACTION_GAP)
                    by = row_y + ROW_H // 2
                    hov = pygame.Rect(bx, by, ACTION_W, ACTION_H).collidepoint(mouse_pos)
                    rect = draw_button(surface, font, bx, by, ACTION_W, ACTION_H,
                                       inf.get_name(), hov, ACCEPT_COLOR, ACCEPT_HOVER, DEFENSE_BORDER)
                    card_choice_rects.append((rect, j))

        elif pending_doubt is not None:
            queue = pending_doubt['queue']
            if queue and i == queue[0]:
                # Active doubter: show Duvidar / Passar
                by = row_y + (ROW_H - DEFENSE_H) // 2
                hov = pygame.Rect(buttons_x, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, buttons_x, by, DEFENSE_W, DEFENSE_H,
                                   "Duvidar", hov, DOUBT_COLOR, DOUBT_HOVER, DEFENSE_BORDER)
                doubt_rects.append((rect, "doubt"))
                bx_pass = buttons_x + DEFENSE_W + DEFENSE_GAP
                hov = pygame.Rect(bx_pass, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, bx_pass, by, DEFENSE_W, DEFENSE_H,
                                   "Passar", hov, PASS_COLOR, PASS_HOVER, DEFENSE_BORDER)
                doubt_rects.append((rect, "pass"))
            elif i == pending_doubt['target']:
                reminder = font.render("Aguardando decisão dos jogadores...", True, (200, 200, 200))
                surface.blit(reminder, (buttons_x, row_y + (ROW_H - reminder.get_height()) // 2))

        elif pending_defense is not None:
            def_target_idx, def_action = pending_defense
            if i == current_turn:
                reminder = font.render(
                    f"Aguardando {players[def_target_idx].name} responder...", True, (255, 220, 100))
                surface.blit(reminder, (buttons_x, row_y + (ROW_H - reminder.get_height()) // 2))
            elif i == def_target_idx:
                by = row_y + (ROW_H - DEFENSE_H) // 2
                block_label = f"Bloquear ({def_action.get_block_name()})"
                hov = pygame.Rect(buttons_x, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, buttons_x, by, DEFENSE_W, DEFENSE_H,
                                   block_label, hov, BLOCK_COLOR, BLOCK_HOVER, DEFENSE_BORDER)
                defense_rects.append((rect, "block"))
                bx_dou = buttons_x + DEFENSE_W + DEFENSE_GAP
                hov = pygame.Rect(bx_dou, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, bx_dou, by, DEFENSE_W, DEFENSE_H,
                                   "Duvidar", hov, DOUBT_COLOR, DOUBT_HOVER, DEFENSE_BORDER)
                defense_rects.append((rect, "doubt_action"))
                bx_acc = bx_dou + DEFENSE_W + DEFENSE_GAP
                hov = pygame.Rect(bx_acc, by, DEFENSE_W, DEFENSE_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, bx_acc, by, DEFENSE_W, DEFENSE_H,
                                   "Aceitar", hov, ACCEPT_COLOR, ACCEPT_HOVER, DEFENSE_BORDER)
                defense_rects.append((rect, "accept"))

        elif is_active and not pending_action:
            for k, action in enumerate(ALL_ACTIONS):
                bx = buttons_x + k * (ACTION_W + ACTION_GAP)
                by = row_y + (ROW_H - ACTION_H) // 2
                hovered = pygame.Rect(bx, by, ACTION_W, ACTION_H).collidepoint(mouse_pos)
                rect = draw_button(surface, font, bx, by, ACTION_W, ACTION_H,
                                   action.get_name(), hovered,
                                   ACTION_COLOR, ACTION_HOVER, ACTION_BORDER)
                action_rects.append((rect, action))

        elif is_targetable:
            by = row_y + (ROW_H - TARGET_H) // 2
            hovered = pygame.Rect(buttons_x, by, TARGET_W, TARGET_H).collidepoint(mouse_pos)
            rect = draw_button(surface, font, buttons_x, by, TARGET_W, TARGET_H,
                               "Selecionar", hovered,
                               TARGET_COLOR, TARGET_HOVER, TARGET_BORDER)
            target_rects.append((rect, i))

        elif is_active and pending_action:
            reminder = font.render(f"Usando: {pending_action.get_name()} — escolha um alvo", True, (255, 220, 100))
            surface.blit(reminder, (buttons_x, row_y + (ROW_H - reminder.get_height()) // 2))

    return action_rects, target_rects, defense_rects, doubt_rects, card_choice_rects, reveal_rects

# --- Main ---
pygame.init()
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("Coup")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 22)

deck = build_deck()
players = deal_players(["Alice", "Bob", "Carol", "Dave"], deck)

current_turn          = 0
pending_action        = None   # Influence object waiting for a target
pending_defense       = None   # (target_idx, action) waiting for defender response
pending_doubt         = None   # {'attacker', 'target', 'action', 'queue'} waiting for doubt/pass
pending_lose_influence = None  # {'target': idx, 'next_turn': idx} target chooses which card to lose
pending_reveal           = None  # {'challenged_player', 'card_name', 'context', 'attacker', 'target', 'action', 'next_turn'}
pending_action_challenge = None  # {'actor': idx, 'action': Influence, 'queue': [idx, ...]} pre-action challenge window

running = True
while running:
    mouse_pos = pygame.mouse.get_pos()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            action_rects, target_rects, defense_rects, doubt_rects, card_choice_rects, reveal_rects = draw_players(
                screen, font, players, current_turn, pending_action, pending_defense, pending_doubt, pending_lose_influence, pending_reveal, pending_action_challenge, mouse_pos)

            if pending_reveal is not None:
                # Phase: challenged player decides to reveal their card or refuse
                for rect, choice in reveal_rects:
                    if rect.collidepoint(event.pos):
                        ctx          = pending_reveal['context']
                        challenged   = players[pending_reveal['challenged_player']]
                        card_name    = pending_reveal['card_name']
                        attacker     = players[pending_reveal['attacker']]
                        target       = players[pending_reveal['target']]
                        action       = pending_reveal['action']
                        next_turn    = pending_reveal['next_turn']
                        attacker_idx = pending_reveal['attacker']
                        target_idx   = pending_reveal['target']
                        doubter_idx  = pending_reveal.get('doubter', -1)
                        pending_reveal = None

                        if choice == "reveal":
                            has_card = any(inf.get_name() == card_name for inf in challenged.influences)
                        else:  # refuse — treated as bluff regardless of actual hand
                            has_card = False

                        if ctx == 'doubt_action':
                            # challenged_player is the attacker
                            if has_card:
                                print(f"{challenged.name} revelou {card_name}! Challenge falhou. Ação executada.")
                                if action.causes_influence_loss():
                                    # Target loses 2 (failed challenge + assassination) — auto-eliminate
                                    for card in list(target.influences):
                                        print(f"{target.name} perdeu: {card.get_name()}")
                                    target.influences.clear()
                                    print(f"{target.name} foi eliminado!")
                                    current_turn = next_turn
                                else:
                                    action.apply_effect(attacker, target)
                                    current_turn = next_turn
                            else:
                                msg = "não tinha" if choice == "reveal" else "recusou revelar."
                                print(f"{challenged.name} {msg} {card_name}. Ação cancelada.")
                                if len(challenged.influences) <= 1:
                                    lost = challenged.influences.pop(0)
                                    print(f"{challenged.name} perdeu: {lost.get_name()} por blefe!")
                                    print(f"{challenged.name} foi eliminado!")
                                    current_turn = next_turn
                                else:
                                    pending_lose_influence = {'target': attacker_idx, 'next_turn': next_turn}

                        elif ctx == 'doubt_block':
                            # challenged_player is the blocker
                            if has_card:
                                print(f"{challenged.name} revelou {card_name}! Bloqueio mantido. {players[doubter_idx].name} perde uma carta.")
                                doubter = players[doubter_idx]
                                if len(doubter.influences) <= 1:
                                    lost = doubter.influences.pop(0)
                                    print(f"{doubter.name} perdeu: {lost.get_name()} por duvidar errado!")
                                    if not doubter.influences:
                                        print(f"{doubter.name} foi eliminado!")
                                    current_turn = next_turn
                                else:
                                    pending_lose_influence = {'target': doubter_idx, 'next_turn': next_turn}
                            else:
                                msg = "não tinha" if choice == "reveal" else "recusou revelar."
                                print(f"{challenged.name} {msg} {card_name}. Bloqueio falhou. Ação executada.")
                                if action.causes_influence_loss():
                                    if len(challenged.influences) <= 1:
                                        for card in list(challenged.influences):
                                            print(f"{challenged.name} perdeu: {card.get_name()}")
                                        challenged.influences.clear()
                                        print(f"{challenged.name} foi eliminado!")
                                        current_turn = next_turn
                                    else:
                                        pending_lose_influence = {'target': target_idx, 'next_turn': next_turn}
                                else:
                                    action.apply_effect(attacker, challenged)
                                    current_turn = next_turn

                        elif ctx == 'doubt_open':
                            # challenged_player is the actor of a non-targeted action (e.g. Duke)
                            if has_card:
                                print(f"{challenged.name} revelou {card_name}! Challenge falhou. Ação executada.")
                                action.apply(challenged)
                                print(f"{challenged.name} usou: {action.get_name()} — {action.get_description()}")
                                doubter = players[doubter_idx]
                                if len(doubter.influences) <= 1:
                                    lost = doubter.influences.pop(0)
                                    print(f"{doubter.name} perdeu: {lost.get_name()} por duvidar errado!")
                                    if not doubter.influences:
                                        print(f"{doubter.name} foi eliminado!")
                                    current_turn = next_turn
                                else:
                                    pending_lose_influence = {'target': doubter_idx, 'next_turn': next_turn}
                            else:
                                msg = "não tinha" if choice == "reveal" else "recusou revelar."
                                print(f"{challenged.name} {msg} {card_name}. Ação cancelada.")
                                if len(challenged.influences) <= 1:
                                    lost = challenged.influences.pop(0)
                                    print(f"{challenged.name} perdeu: {lost.get_name()} por blefe!")
                                    if not challenged.influences:
                                        print(f"{challenged.name} foi eliminado!")
                                    current_turn = next_turn
                                else:
                                    pending_lose_influence = {'target': attacker_idx, 'next_turn': next_turn}
                        break

            elif pending_lose_influence is not None:
                # Phase: target chooses which influence card to lose
                for rect, card_idx in card_choice_rects:
                    if rect.collidepoint(event.pos):
                        target = players[pending_lose_influence['target']]
                        lost_card = target.influences.pop(card_idx)
                        print(f"{target.name} perdeu: {lost_card.get_name()}")
                        if not target.influences:
                            print(f"{target.name} foi eliminado!")
                        next_turn = pending_lose_influence['next_turn']
                        pending_lose_influence = None
                        current_turn = next_turn
                        break

            elif pending_action_challenge is not None:
                # Pre-action challenge: other players decide to doubt or pass before the action executes
                for rect, choice in doubt_rects:
                    if rect.collidepoint(event.pos):
                        actor_idx = pending_action_challenge['actor']
                        ac_action = pending_action_challenge['action']
                        ac_queue  = pending_action_challenge['queue']
                        actor     = players[actor_idx]
                        doubter_idx = ac_queue[0]
                        doubter     = players[doubter_idx]

                        if choice == "doubt":
                            card_name = ac_action.get_name()
                            has_card  = any(inf.get_name() == card_name for inf in actor.influences)
                            print(f"{doubter.name} desafia {actor.name} a provar que tem {card_name}!")
                            pending_action_challenge = None
                            if has_card:
                                pending_reveal = {
                                    'challenged_player': actor_idx,
                                    'card_name':         card_name,
                                    'context':           'doubt_open',
                                    'attacker':          actor_idx,
                                    'target':            actor_idx,
                                    'action':            ac_action,
                                    'next_turn':         (actor_idx + 1) % len(players),
                                    'doubter':           doubter_idx,
                                }
                            else:
                                print(f"{actor.name} não tem {card_name}. Ação cancelada.")
                                if len(actor.influences) <= 1:
                                    lost = actor.influences.pop(0)
                                    print(f"{actor.name} perdeu: {lost.get_name()} por blefe!")
                                    if not actor.influences:
                                        print(f"{actor.name} foi eliminado!")
                                    current_turn = (actor_idx + 1) % len(players)
                                else:
                                    pending_lose_influence = {'target': actor_idx, 'next_turn': (actor_idx + 1) % len(players)}
                        elif choice == "pass":
                            ac_queue.pop(0)
                            if not ac_queue:
                                # Nobody doubted — execute the action
                                ac_action.apply(actor)
                                print(f"{actor.name} usou: {ac_action.get_name()} — {ac_action.get_description()}")
                                pending_action_challenge = None
                                current_turn = (actor_idx + 1) % len(players)
                        break

            elif pending_doubt is not None:
                # Phase 4: each non-blocker decides to doubt or pass
                for rect, choice in doubt_rects:
                    if rect.collidepoint(event.pos):
                        queue      = pending_doubt['queue']
                        attacker   = pending_doubt['attacker']
                        target_idx = pending_doubt['target']
                        d_action   = pending_doubt['action']
                        doubter    = players[queue[0]]
                        target     = players[target_idx]
                        player     = players[attacker]
                        if choice == "doubt":
                            block_card = d_action.get_block_name()
                            has_card = any(inf.get_name() == block_card for inf in target.influences)
                            print(f"{doubter.name} desafia {target.name} a provar que tem {block_card}!")
                            pending_doubt = None
                            if has_card:
                                # Blocker has the card — let them choose to reveal or bluff
                                pending_reveal = {
                                    'challenged_player': target_idx,
                                    'card_name':         block_card,
                                    'context':           'doubt_block',
                                    'attacker':          attacker,
                                    'target':            target_idx,
                                    'action':            d_action,
                                    'next_turn':         (attacker + 1) % len(players),
                                    'doubter':           queue[0],
                                }
                            else:
                                # Blocker doesn't have the card — block fails immediately
                                print(f"{target.name} não tem {block_card}. Bloqueio falhou. Ação executada.")
                                if d_action.causes_influence_loss():
                                    if len(target.influences) <= 1:
                                        for card in list(target.influences):
                                            print(f"{target.name} perdeu: {card.get_name()}")
                                        target.influences.clear()
                                        print(f"{target.name} foi eliminado!")
                                        current_turn = (attacker + 1) % len(players)
                                    else:
                                        pending_lose_influence = {'target': target_idx, 'next_turn': (attacker + 1) % len(players)}
                                else:
                                    d_action.apply_effect(player, target)
                                    current_turn = (attacker + 1) % len(players)
                        elif choice == "pass":
                            queue.pop(0)
                            if not queue:
                                print(f"Ninguém duvidou. Bloqueio de {target.name} aceito.")
                                pending_doubt = None
                                current_turn = (attacker + 1) % len(players)
                        break

            elif pending_defense is not None:
                # Phase 3: defender chooses to block or accept
                for rect, choice in defense_rects:
                    if rect.collidepoint(event.pos):
                        player         = players[current_turn]
                        def_target_idx = pending_defense[0]
                        def_action     = pending_defense[1]
                        target         = players[def_target_idx]
                        if choice == "block":
                            # Only the original attacker can doubt the block
                            pending_doubt = {
                                'attacker': current_turn,
                                'target':   def_target_idx,
                                'action':   def_action,
                                'queue':    [current_turn],
                            }
                            pending_defense = None
                        elif choice == "doubt_action":
                            action_card = def_action.get_name()
                            has_card = any(inf.get_name() == action_card for inf in player.influences)
                            print(f"{target.name} desafia {player.name} a provar que tem {action_card}!")
                            pending_defense = None
                            if has_card:
                                # Attacker has the card — let them choose to reveal or bluff
                                pending_reveal = {
                                    'challenged_player': current_turn,
                                    'card_name':         action_card,
                                    'context':           'doubt_action',
                                    'attacker':          current_turn,
                                    'target':            def_target_idx,
                                    'action':            def_action,
                                    'next_turn':         (current_turn + 1) % len(players),
                                }
                            else:
                                # Attacker doesn't have the card — directly lose an influence
                                print(f"{player.name} não tem {action_card}. Ação cancelada.")
                                if len(player.influences) <= 1:
                                    lost = player.influences.pop(0)
                                    print(f"{player.name} perdeu: {lost.get_name()} por blefe!")
                                    print(f"{player.name} foi eliminado!")
                                    current_turn = (current_turn + 1) % len(players)
                                else:
                                    pending_lose_influence = {'target': current_turn, 'next_turn': (current_turn + 1) % len(players)}
                        else:  # accept
                            print(f"{target.name} aceitou. {player.name} executou {def_action.get_name()} em {target.name}!")
                            pending_defense = None
                            if def_action.causes_influence_loss():
                                if len(target.influences) <= 1:
                                    for card in list(target.influences):
                                        print(f"{target.name} perdeu: {card.get_name()}")
                                    target.influences.clear()
                                    print(f"{target.name} foi eliminado!")
                                    current_turn = (current_turn + 1) % len(players)
                                else:
                                    pending_lose_influence = {'target': def_target_idx, 'next_turn': (current_turn + 1) % len(players)}
                            else:
                                def_action.apply_effect(player, target)
                                current_turn = (current_turn + 1) % len(players)
                        break

            elif pending_action is None:
                # Phase 1: pick an action
                for rect, action in action_rects:
                    if rect.collidepoint(event.pos):
                        player = players[current_turn]
                        if not action.can_use(player):
                            print(f"{player.name} não tem moedas suficientes para usar {action.get_name()}")
                            break
                        if action.requires_target():
                            pending_action = action
                        else:
                            # Open challenge window for all other players before executing
                            n = len(players)
                            queue = [(current_turn + k) % n for k in range(1, n)]
                            print(f"{player.name} anuncia: {action.get_name()}!")
                            pending_action_challenge = {
                                'actor':  current_turn,
                                'action': action,
                                'queue':  queue,
                            }
                        break

            else:
                # Phase 2: pick a target
                for rect, target_idx in target_rects:
                    if rect.collidepoint(event.pos):
                        player = players[current_turn]
                        target = players[target_idx]
                        if pending_action.has_defense():
                            pending_action.apply_cost(player)
                            pending_defense = (target_idx, pending_action)
                            pending_action = None
                        else:
                            pending_action.apply(player, target)
                            print(f"{player.name} usou: {pending_action.get_name()} em {target.name} — {pending_action.get_description()}")
                            pending_action = None
                            current_turn = (current_turn + 1) % len(players)
                        break

    screen.fill(BG_COLOR)
    draw_players(screen, font, players, current_turn, pending_action, pending_defense, pending_doubt, pending_lose_influence, pending_reveal, pending_action_challenge, mouse_pos)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
