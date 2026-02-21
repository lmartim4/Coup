import math
from typing import Any, List, Optional, Tuple

import pygame
from game_state import GameStateView, PendingDecision, PlayerStateView, DecisionType, DecisionResponse


# ── helpers ───────────────────────────────────────────────────────────────────

def _elastic_out(t: float) -> float:
    """Elastic ease-out: fast grow with a slight bounce overshoot."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1


# ── SpeechBubble ──────────────────────────────────────────────────────────────

class SpeechBubble:
    """Comic-book style animated speech bubble tied to a player panel."""

    POPUP_MS   = 280
    DISPLAY_MS = 2200
    FADEOUT_MS = 400

    PAD_X  = 12
    PAD_Y  = 9
    RADIUS = 14
    TAIL_W = 12   # half-width of tail base
    TAIL_H = 16   # length of tail triangle
    BORDER = 3

    BG_COLOR     = (255, 252, 220)
    BORDER_COLOR = (25,  20,  20)

    def __init__(self, text: str, anchor_x: int, anchor_y: int,
                 tail_dir: str, color: Tuple[int, int, int]):
        """
        anchor_x/y : pixel position of the tail tip (the panel edge the bubble points at).
        tail_dir   : 'up' | 'down' | 'left' | 'right' — direction the tail points.
        color      : player colour used for the bubble text.
        """
        self.text     = text
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y
        self.tail_dir = tail_dir
        self.color    = color
        self._start   = pygame.time.get_ticks()
        self.done     = False

    # ── animation ──────────────────────────────────────────────────────────

    def _anim(self) -> Tuple[float, int]:
        elapsed = pygame.time.get_ticks() - self._start
        total   = self.POPUP_MS + self.DISPLAY_MS + self.FADEOUT_MS
        if elapsed >= total:
            self.done = True
            return 1.0, 0
        if elapsed < self.POPUP_MS:
            scale = _elastic_out(elapsed / self.POPUP_MS)
            alpha = 255
        elif elapsed < self.POPUP_MS + self.DISPLAY_MS:
            scale, alpha = 1.0, 255
        else:
            t     = (elapsed - self.POPUP_MS - self.DISPLAY_MS) / self.FADEOUT_MS
            scale = 1.0
            alpha = int(255 * (1 - t))
        return scale, alpha

    # ── drawing ─────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        scale, alpha = self._anim()
        if alpha <= 0 or scale < 0.05:
            return

        lbl    = font.render(self.text, True, self.color)
        tw, th = lbl.get_size()

        bw  = max(80, tw + self.PAD_X * 2)
        bh  = th + self.PAD_Y * 2
        sbw = max(8, int(bw * scale))
        sbh = max(8, int(bh * scale))

        B  = self.BORDER
        R  = max(4, int(self.RADIUS * scale))
        TW = max(4, int(self.TAIL_W * scale))
        TH = max(4, int(self.TAIL_H * scale))

        bg_a = (*self.BG_COLOR,     alpha)
        bd_a = (*self.BORDER_COLOR, alpha)

        # ── geometry (surface size + key points) per direction ──────────
        if self.tail_dir == 'down':
            sw, sh = sbw + B * 2, sbh + TH + B * 2
            s      = pygame.Surface((sw, sh), pygame.SRCALPHA)
            body   = pygame.Rect(B, B, sbw, sbh)
            tx     = sw // 2
            o_tail = [(tx - TW - B, body.bottom), (tx + TW + B, body.bottom), (tx, sh - 1)]
            i_tail = [(tx - TW,     body.bottom - 1), (tx + TW,     body.bottom - 1), (tx, sh - B - 1)]
            blit_x = self.anchor_x - sw // 2
            blit_y = self.anchor_y - sh

        elif self.tail_dir == 'up':
            sw, sh = sbw + B * 2, sbh + TH + B * 2
            s      = pygame.Surface((sw, sh), pygame.SRCALPHA)
            body   = pygame.Rect(B, TH + B, sbw, sbh)
            tx     = sw // 2
            o_tail = [(tx, 0), (tx - TW - B, body.top), (tx + TW + B, body.top)]
            i_tail = [(tx, B), (tx - TW,     body.top + 1), (tx + TW,     body.top + 1)]
            blit_x = self.anchor_x - sw // 2
            blit_y = self.anchor_y

        elif self.tail_dir == 'right':
            sw, sh = sbw + TH + B * 2, sbh + B * 2
            s      = pygame.Surface((sw, sh), pygame.SRCALPHA)
            body   = pygame.Rect(B, B, sbw, sbh)
            ty     = sh // 2
            o_tail = [(body.right, ty - TW - B), (body.right, ty + TW + B), (sw - 1, ty)]
            i_tail = [(body.right - 1, ty - TW), (body.right - 1, ty + TW), (sw - B - 1, ty)]
            blit_x = self.anchor_x - sw
            blit_y = self.anchor_y - sh // 2

        else:  # 'left'
            sw, sh = sbw + TH + B * 2, sbh + B * 2
            s      = pygame.Surface((sw, sh), pygame.SRCALPHA)
            body   = pygame.Rect(TH + B, B, sbw, sbh)
            ty     = sh // 2
            o_tail = [(0, ty), (body.left, ty - TW - B), (body.left, ty + TW + B)]
            i_tail = [(B, ty), (body.left + 1, ty - TW), (body.left + 1, ty + TW)]
            blit_x = self.anchor_x
            blit_y = self.anchor_y - sh // 2

        # ── draw border layer ──────────────────────────────────────────
        outer_body = body.inflate(B * 2, B * 2)
        pygame.draw.rect(s,    bd_a, outer_body, border_radius=R + B)
        pygame.draw.polygon(s, bd_a, o_tail)

        # ── draw fill layer ────────────────────────────────────────────
        pygame.draw.rect(s,    bg_a, body, border_radius=R)
        pygame.draw.polygon(s, bg_a, i_tail)

        # cover the seam between body fill and tail fill
        if self.tail_dir == 'down':
            seam = pygame.Rect(tx - TW, body.bottom - 1, TW * 2, 2)
        elif self.tail_dir == 'up':
            seam = pygame.Rect(tx - TW, body.top - 1, TW * 2, 2)
        elif self.tail_dir == 'right':
            seam = pygame.Rect(body.right - 1, ty - TW, 2, TW * 2)
        else:
            seam = pygame.Rect(body.left - 1, ty - TW, 2, TW * 2)
        pygame.draw.rect(s, bg_a, seam)

        # ── draw text ──────────────────────────────────────────────────
        stw = max(1, int(tw * scale))
        sth = max(1, int(th * scale))
        ls  = pygame.transform.smoothscale(lbl, (stw, sth))
        ls.set_alpha(alpha)
        s.blit(ls, (body.x + (sbw - stw) // 2, body.y + (sbh - sth) // 2))

        surface.blit(s, (blit_x, blit_y))

# Mesa centralizada no centro da tela
_TABLE_CX_RATIO = 0.50
_TABLE_CY_RATIO = 0.50


class Renderer:

    # Dimensões das cartas
    CARD_W   = 50
    CARD_H   = 80
    CARD_GAP = 10

    # Painel por jogador
    PANEL_W    = 280
    INFO_H     = 44      # altura da área de texto (nome + moedas)
    CARD_ROW_H = 95      # CARD_H + padding vertical
    PANEL_PAD  = 12

    # Botões
    BTN_W   = 150
    BTN_H   = 36
    BTN_GAP = 10

    # --- Paleta ---
    BG_COLOR             = (40,  40,  60)
    TABLE_COLOR          = (30,  75,  40)
    TABLE_BORDER         = (20,  55,  28)

    PANEL_BG             = (50,  50,  75)
    PANEL_ACTIVE         = (55,  80,  55)
    PANEL_DECIDING       = (75,  55, 110)
    PANEL_ELIMINATED     = (28,  28,  38)
    PANEL_BORDER         = (95, 100, 130)

    CARD_FACE_COLOR      = (200, 170, 100)
    CARD_BACK_COLOR      = (60,   80, 130)
    CARD_REVEALED_COLOR  = (80,   45,  45)   # fundo da carta morta
    CARD_BORDER          = (80,   60,  30)
    CARD_REVEALED_BORDER = (150,  50,  50)

    TEXT_COLOR           = (255, 255, 255)

    PLAYER_COLORS = [
        (220,  80,  80),   # 0 vermelho
        ( 80, 140, 220),   # 1 azul
        ( 80, 200,  80),   # 2 verde
        (220, 180,  60),   # 3 amarelo
        (200,  80, 200),   # 4 roxo
        ( 60, 200, 200),   # 5 ciano
    ]

    ACTION_COLOR  = (70,  100, 140)
    ACTION_HOVER  = (100, 140, 190)
    TARGET_COLOR  = (140,  70,  70)
    TARGET_HOVER  = (190, 110, 110)
    BLOCK_COLOR   = (50,  110,  70)
    BLOCK_HOVER   = (80,  150, 100)
    DOUBT_COLOR   = (120,  60, 160)
    DOUBT_HOVER   = (160,  90, 210)
    ACCEPT_COLOR  = (140,  60,  60)
    ACCEPT_HOVER  = (180, 100, 100)
    PASS_COLOR    = (60,   60,  60)
    PASS_HOVER    = (90,   90,  90)
    BTN_BORDER    = (200, 200, 220)

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font):
        self.screen       = screen
        self.font         = font
        self._bubble_font = pygame.font.SysFont(None, 22, bold=True)
        self._bubbles: List[SpeechBubble] = []

    def clear(self):
        self.screen.fill(self.BG_COLOR)

    def _player_color(self, idx: int) -> Tuple[int, int, int]:
        return self.PLAYER_COLORS[idx % len(self.PLAYER_COLORS)]

    # ------------------------------------------------------------------ layout

    def _panel_height(self, player: PlayerStateView) -> int:
        return self.PANEL_PAD + self.INFO_H + self.CARD_ROW_H + self.PANEL_PAD

    def _seat_positions(self, n: int, viewer_idx: int, W: int, H: int) -> List[Tuple[int, int]]:
        """
        Calcula a posição central do painel de cada jogador distribuindo-os
        simetricamente ao redor de uma elipse.
        O viewer fica sempre na posição inferior (ângulo π/2 nas coordenadas pygame).
        """
        tcx = W * _TABLE_CX_RATIO
        tcy = H * _TABLE_CY_RATIO
        rx  = W * 0.38
        ry  = H * 0.30

        positions = []
        for i in range(n):
            offset = (i - viewer_idx) % n
            # π/2 = parte inferior da tela; cada jogador ocupa um arco de 2π/n
            angle = math.pi / 2 + offset * (2 * math.pi / n)
            x = tcx + rx * math.cos(angle)
            y = tcy + ry * math.sin(angle)
            positions.append((int(x), int(y)))
        return positions

    # ------------------------------------------------------------------ draw principal

    def draw(self, state: GameStateView, mouse_pos: Tuple[int, int]) -> List[Tuple[pygame.Rect, Any]]:
        clickable = []
        W, H = self.screen.get_size()
        decision       = state.pending_decision
        is_my_decision = (decision is not None and
                          decision.player_index == state.viewer_index)

        tcx = int(W * _TABLE_CX_RATIO)
        tcy = int(H * _TABLE_CY_RATIO)

        # Mesa decorativa + cartas reveladas sobre ela
        self._draw_table(tcx, tcy, W, H)
        self._draw_table_cards(state, tcx, tcy)

        seats = self._seat_positions(len(state.players), state.viewer_index, W, H)

        for i, player in enumerate(state.players):
            cx, cy   = seats[i]
            is_viewer = (i == state.viewer_index)
            ph        = self._panel_height(player)
            px        = cx - self.PANEL_W // 2
            py        = cy - ph // 2

            # Fundo do painel
            if player.is_eliminated:
                bg = self.PANEL_ELIMINATED
            elif decision is not None and i == decision.player_index:
                bg = self.PANEL_DECIDING
            elif i == state.current_turn:
                bg = self.PANEL_ACTIVE
            else:
                bg = self.PANEL_BG

            pygame.draw.rect(self.screen, bg,
                             (px, py, self.PANEL_W, ph), border_radius=10)
            pygame.draw.rect(self.screen, self.PANEL_BORDER,
                             (px, py, self.PANEL_W, ph), width=2, border_radius=10)

            # Texto de info
            self._draw_player_info(player, px, py)

            # Cartas na mão
            hand_y = py + self.PANEL_PAD + self.INFO_H
            self._draw_hand_cards(player, px, hand_y, is_viewer)

            # Thinking indicator for other deciding players
            if (decision is not None and i == decision.player_index
                    and not is_viewer):
                self._draw_thinking_dots(cx, py + ph + 14)

            # Botão "Selecionar" na linha de cada alvo possível
            if (is_my_decision and decision.decision_type == DecisionType.PICK_TARGET
                    and i != state.viewer_index and i in decision.options):
                bx = cx - self.BTN_W // 2
                by = py + ph + 8
                rect = self._btn(bx, by, self.BTN_W, self.BTN_H,
                                 "Selecionar", mouse_pos,
                                 self.TARGET_COLOR, self.TARGET_HOVER)
                clickable.append((rect, i))

        # Botões de decisão do viewer (acima do painel dele)
        if is_my_decision:
            vcx, vcy = seats[state.viewer_index]
            vph      = self._panel_height(state.players[state.viewer_index])
            btn_y    = vcy - vph // 2 - self.BTN_H - 14

            if decision.decision_type == DecisionType.PICK_TARGET:
                action_name = decision.context.get('action_name', '')
                self._text(f"Usando: {action_name} — escolha um alvo",
                           (W // 2 - 145, btn_y + 10),
                           color=(255, 220, 100))
            else:
                new = self._draw_decision_btns(decision, state, btn_y, mouse_pos)
                clickable.extend(new)

        # Speech bubbles (drawn on top of everything)
        self._draw_bubbles()

        # Game over
        if state.pending_decision is None:
            self._draw_game_over(state)

        return clickable

    # ------------------------------------------------------------------ sub-renders

    def _draw_table(self, cx: int, cy: int, W: int, H: int):
        rx = int(W * 0.22)
        ry = int(H * 0.17)
        rect = pygame.Rect(cx - rx, cy - ry, 2 * rx, 2 * ry)
        pygame.draw.ellipse(self.screen, self.TABLE_COLOR, rect)
        pygame.draw.ellipse(self.screen, self.TABLE_BORDER, rect, width=4)

    def _draw_player_info(self, player: PlayerStateView, px: int, py: int):
        ty  = py + self.PANEL_PAD
        col = self._player_color(player.index)
        # Bolinha colorida do jogador
        pygame.draw.circle(self.screen, col,       (px + 13, ty + 8), 7)
        pygame.draw.circle(self.screen, (255, 255, 255), (px + 13, ty + 8), 7, 1)
        self._text(player.name, (px + 26, ty))
        self._text(f"Moedas: {player.coins}", (px + 26, ty + 22),
                   color=(255, 215, 0))
        if player.is_eliminated:
            self._text("ELIMINADO",
                       (px + self.PANEL_W - 95, ty + 8),
                       color=(255, 80, 80))

    def _draw_hand_cards(self, player: PlayerStateView, px: int, card_y: int,
                         is_viewer: bool):
        count = player.influence_count
        if count == 0:
            return
        total_w  = count * self.CARD_W + (count - 1) * self.CARD_GAP
        start_x  = px + (self.PANEL_W - total_w) // 2
        for j in range(count):
            cx = start_x + j * (self.CARD_W + self.CARD_GAP)
            if is_viewer and j < len(player.influences):
                self._draw_card_face(cx, card_y, player.influences[j])
            else:
                self._draw_card_back(cx, card_y)

    def _draw_table_cards(self, state: GameStateView, tcx: int, tcy: int):
        """Desenha na mesa central todas as cartas reveladas (perdidas), com cor do dono."""
        table_cards = [
            (player.index, card_name)
            for player in state.players
            for card_name in player.revealed_influences
        ]
        if not table_cards:
            return

        TW, TH, TG = 55, 82, 8
        MAX_ROW     = 6
        n_rows      = (len(table_cards) + MAX_ROW - 1) // MAX_ROW
        total_h     = n_rows * TH + (n_rows - 1) * TG
        start_y     = tcy - total_h // 2

        for row in range(n_rows):
            row_cards = table_cards[row * MAX_ROW : (row + 1) * MAX_ROW]
            total_w   = len(row_cards) * TW + (len(row_cards) - 1) * TG
            start_x   = tcx - total_w // 2
            for col, (pidx, card_name) in enumerate(row_cards):
                x = start_x + col * (TW + TG)
                y = start_y + row * (TH + TG)
                self._draw_table_card(x, y, card_name, self._player_color(pidx), TW, TH)

    def _draw_table_card(self, x: int, y: int, card_name: str,
                         owner_color: tuple, w: int, h: int):
        """Carta morta na mesa: fundo escuro com destaque na cor do dono original."""
        rect = pygame.Rect(x, y, w, h)
        bg   = tuple(max(0, c // 4 + 15) for c in owner_color)
        pygame.draw.rect(self.screen, bg,          rect, border_radius=5)
        pygame.draw.rect(self.screen, owner_color, rect, width=2, border_radius=5)
        label = pygame.transform.rotate(
            self.font.render(card_name, True, owner_color), 90)
        self.screen.blit(label, (
            x + (w - label.get_width())  // 2,
            y + (h - label.get_height()) // 2))
        # X na cor do dono
        pygame.draw.line(self.screen, owner_color, (x + 4, y + 4), (x + w - 4, y + h - 4), 2)
        pygame.draw.line(self.screen, owner_color, (x + w - 4, y + 4), (x + 4, y + h - 4), 2)

    # ------------------------------------------------------------------ botões por tipo de decisão

    def _draw_decision_btns(self, decision: PendingDecision, state: GameStateView,
                             by: int, mouse_pos: Tuple[int, int]) -> List[Tuple[pygame.Rect, Any]]:
        clickable = []
        dt  = decision.decision_type
        ctx = decision.context
        W   = self.screen.get_width()

        def _centered_bx(n_btns: int) -> int:
            total = n_btns * self.BTN_W + (n_btns - 1) * self.BTN_GAP
            return W // 2 - total // 2

        if dt == DecisionType.PICK_ACTION:
            bx = _centered_bx(len(decision.options))
            for k, option in enumerate(decision.options):
                x    = bx + k * (self.BTN_W + self.BTN_GAP)
                rect = self._btn(x, by, self.BTN_W, self.BTN_H, option.get_name(), mouse_pos,
                                 self.ACTION_COLOR, self.ACTION_HOVER)
                clickable.append((rect, option))

        elif dt == DecisionType.DEFEND:
            bx = _centered_bx(3)
            hint = (f"{ctx.get('attacker_name', '')} usa "
                    f"{ctx.get('action_name', '')}")
            self._text(hint, (bx, by - 18), color=(255, 220, 100))
            defs = [
                (f"Bloquear ({ctx.get('block_card', '')})", DecisionResponse.BLOCK,        self.BLOCK_COLOR,  self.BLOCK_HOVER),
                ("Duvidar ação",                            DecisionResponse.DOUBT_ACTION, self.DOUBT_COLOR,  self.DOUBT_HOVER),
                ("Aceitar",                                 DecisionResponse.ACCEPT,       self.ACCEPT_COLOR, self.ACCEPT_HOVER),
            ]
            for k, (label, key, color, hover) in enumerate(defs):
                x    = bx + k * (self.BTN_W + self.BTN_GAP)
                rect = self._btn(x, by, self.BTN_W, self.BTN_H, label, mouse_pos, color, hover)
                clickable.append((rect, key))

        elif dt == DecisionType.BLOCK_OR_PASS:
            bx = _centered_bx(2)
            hint = (f"{ctx.get('actor_name', '')} anuncia "
                    f"{ctx.get('action_name', '')}")
            self._text(hint, (bx, by - 18), color=(255, 220, 100))
            pairs = [
                (f"Bloquear ({ctx.get('block_card', '')})", DecisionResponse.BLOCK, self.BLOCK_COLOR,  self.BLOCK_HOVER),
                ("Passar",                                   DecisionResponse.PASS,  self.PASS_COLOR,   self.PASS_HOVER),
            ]
            for k, (label, key, color, hover) in enumerate(pairs):
                x    = bx + k * (self.BTN_W + self.BTN_GAP)
                rect = self._btn(x, by, self.BTN_W, self.BTN_H, label, mouse_pos, color, hover)
                clickable.append((rect, key))

        elif dt in (DecisionType.CHALLENGE_ACTION, DecisionType.CHALLENGE_BLOCK):
            bx = _centered_bx(2)
            if dt == DecisionType.CHALLENGE_ACTION:
                hint = (f"{ctx.get('actor_name', '')} anuncia "
                        f"{ctx.get('action_name', '')}")
            else:
                hint = (f"{ctx.get('blocker_name', '')} bloqueia com "
                        f"{ctx.get('block_card', '')}")
            self._text(hint, (bx, by - 18), color=(200, 180, 255))
            pairs = [
                ("Duvidar", DecisionResponse.DOUBT, self.DOUBT_COLOR, self.DOUBT_HOVER),
                ("Passar",  DecisionResponse.PASS,  self.PASS_COLOR,  self.PASS_HOVER),
            ]
            for k, (label, key, color, hover) in enumerate(pairs):
                x    = bx + k * (self.BTN_W + self.BTN_GAP)
                rect = self._btn(x, by, self.BTN_W, self.BTN_H, label, mouse_pos, color, hover)
                clickable.append((rect, key))

        elif dt == DecisionType.LOSE_INFLUENCE:
            bx = _centered_bx(len(decision.options))
            self._text("Escolha uma carta para perder:", (bx, by - 18),
                       color=(255, 150, 150))
            viewer = next(p for p in state.players if p.index == state.viewer_index)
            for k, card_idx in enumerate(decision.options):
                name = (viewer.influences[card_idx]
                        if card_idx < len(viewer.influences) else f"Carta {card_idx}")
                x    = bx + k * (self.BTN_W + self.BTN_GAP)
                rect = self._btn(x, by, self.BTN_W, self.BTN_H, name, mouse_pos,
                                 self.ACCEPT_COLOR, self.ACCEPT_HOVER)
                clickable.append((rect, card_idx))

        elif dt == DecisionType.REVEAL:
            bx = _centered_bx(2)
            self._text(f"Prove que tem {ctx.get('card_name', '')}:",
                       (bx, by - 18), color=(180, 210, 255))
            pairs = [
                ("Revelar", DecisionResponse.REVEAL, self.BLOCK_COLOR,  self.BLOCK_HOVER),
                ("Recusar", DecisionResponse.REFUSE, self.ACCEPT_COLOR, self.ACCEPT_HOVER),
            ]
            for k, (label, key, color, hover) in enumerate(pairs):
                x    = bx + k * (self.BTN_W + self.BTN_GAP)
                rect = self._btn(x, by, self.BTN_W, self.BTN_H, label, mouse_pos, color, hover)
                clickable.append((rect, key))

        return clickable

    # ------------------------------------------------------------------ primitivos

    def _draw_card_face(self, x: int, y: int, card_name: str):
        rect = pygame.Rect(x, y, self.CARD_W, self.CARD_H)
        pygame.draw.rect(self.screen, self.CARD_FACE_COLOR, rect, border_radius=6)
        pygame.draw.rect(self.screen, self.CARD_BORDER, rect, width=2, border_radius=6)
        label = pygame.transform.rotate(
            self.font.render(card_name, True, (40, 40, 40)), 90)
        self.screen.blit(label, (
            x + (self.CARD_W - label.get_width())  // 2,
            y + (self.CARD_H - label.get_height()) // 2))

    def _draw_card_back(self, x: int, y: int):
        rect = pygame.Rect(x, y, self.CARD_W, self.CARD_H)
        pygame.draw.rect(self.screen, self.CARD_BACK_COLOR, rect, border_radius=6)
        pygame.draw.rect(self.screen, self.CARD_BORDER, rect, width=2, border_radius=6)
        label = pygame.transform.rotate(
            self.font.render("?", True, (150, 150, 200)), 90)
        self.screen.blit(label, (
            x + (self.CARD_W - label.get_width())  // 2,
            y + (self.CARD_H - label.get_height()) // 2))

    def _draw_card_revealed(self, x: int, y: int, card_name: str):
        """Carta revelada: face visível mas com visual de 'morta' (fundo escuro + X)."""
        rect = pygame.Rect(x, y, self.CARD_W, self.CARD_H)
        pygame.draw.rect(self.screen, self.CARD_REVEALED_COLOR, rect, border_radius=6)
        pygame.draw.rect(self.screen, self.CARD_REVEALED_BORDER, rect, width=2, border_radius=6)
        label = pygame.transform.rotate(
            self.font.render(card_name, True, (200, 140, 140)), 90)
        self.screen.blit(label, (
            x + (self.CARD_W - label.get_width())  // 2,
            y + (self.CARD_H - label.get_height()) // 2))
        # X vermelho por cima
        pygame.draw.line(self.screen, (190, 40, 40),
                         (x + 4,  y + 4),  (x + self.CARD_W - 4, y + self.CARD_H - 4), 2)
        pygame.draw.line(self.screen, (190, 40, 40),
                         (x + self.CARD_W - 4, y + 4), (x + 4, y + self.CARD_H - 4), 2)

    def _btn(self, x: int, y: int, w: int, h: int, text: str,
             mouse_pos: Tuple[int, int], color: Tuple[int, int, int],
             hover_color: Tuple[int, int, int]) -> pygame.Rect:
        rect    = pygame.Rect(x, y, w, h)
        hovered = rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, hover_color if hovered else color, rect, border_radius=5)
        pygame.draw.rect(self.screen, self.BTN_BORDER, rect, width=1, border_radius=5)
        label = self.font.render(text, True, self.TEXT_COLOR)
        self.screen.blit(label, (
            x + (w - label.get_width())  // 2,
            y + (h - label.get_height()) // 2))
        return rect

    def _text(self, text: str, pos: Tuple[int, int], color: Optional[Tuple[int, int, int]]= None) -> None:
        surf = self.font.render(text, True, color or self.TEXT_COLOR)
        self.screen.blit(surf, pos)

    # ------------------------------------------------------------------ thinking dots

    def _draw_thinking_dots(self, cx: int, y: int):
        """Animated three-dot thinking indicator below a player panel."""
        t            = pygame.time.get_ticks()
        dot_r        = 5
        dot_spacing  = 16
        cycle_ms     = 600   # time for one dot to complete a full pulse
        for k in range(3):
            # each dot is offset by 1/3 of the cycle
            phase = ((t / cycle_ms) - k / 3.0) % 1.0
            # brightness: ramp up then down (triangle wave)
            brightness = 1.0 - abs(phase * 2 - 1.0)
            alpha = int(60 + 195 * brightness)
            color = (
                int(180 * alpha // 255),
                int(180 * alpha // 255),
                min(255, int(220 * alpha // 255)),
            )
            dx = cx + (k - 1) * dot_spacing
            pygame.draw.circle(self.screen, color, (dx, y), dot_r)

    # ------------------------------------------------------------------ speech bubbles

    def add_bubble(self, text: str, player_idx: int, state: GameStateView):
        """Spawn a comic speech bubble near player_idx's panel."""
        W, H  = self.screen.get_size()
        seats = self._seat_positions(len(state.players), state.viewer_index, W, H)
        if player_idx >= len(seats):
            return

        cx, cy = seats[player_idx]
        ph     = self._panel_height(state.players[player_idx])
        scx    = W // 2
        scy    = H // 2

        dx = cx - scx
        dy = cy - scy

        if abs(dy) >= abs(dx):
            if dy >= 0:          # player in lower half → bubble above panel
                tail_dir = 'down'
                ax, ay   = cx, cy - ph // 2
            else:                # player in upper half → bubble below panel
                tail_dir = 'up'
                ax, ay   = cx, cy + ph // 2
        else:
            if dx >= 0:          # player on right → bubble to the right, tail ←
                tail_dir = 'left'
                ax, ay   = cx + self.PANEL_W // 2 + self.PANEL_PAD, cy
            else:                # player on left  → bubble to the left,  tail →
                tail_dir = 'right'
                ax, ay   = cx - self.PANEL_W // 2 - self.PANEL_PAD, cy

        color = self._player_color(player_idx)
        self._bubbles.append(SpeechBubble(text, ax, ay, tail_dir, color))

    def _draw_bubbles(self):
        self._bubbles = [b for b in self._bubbles if not b.done]
        for b in self._bubbles:
            b.draw(self.screen, self._bubble_font)

    # ------------------------------------------------------------------ game over

    def _draw_game_over(self, state: GameStateView):
        alive = [p for p in state.players if not p.is_eliminated]
        if not alive:
            return
        winner = alive[0].name
        W, H   = self.screen.get_size()
        big    = pygame.font.SysFont(None, 64)
        surf   = big.render(f"Fim de jogo! Vencedor: {winner}", True, (255, 220, 0))
        self.screen.blit(surf, (W // 2 - surf.get_width() // 2,
                                H // 2 - surf.get_height() // 2))
