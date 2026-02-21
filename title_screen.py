"""
title_screen.py  –  Coup game title screen

Shows the main menu (Play Solo / Host Game / Join Game) and collects
the player's name (and server IP for Join mode).

Returns a dict:
  {"mode": "solo"|"host"|"join", "name": str, "host_ip": str, "host_port": int}
"""

from typing import Any

import pygame

# ── palette (mirrors renderer.py) ─────────────────────────────────────────────
BG_COLOR      = (40,  40,  60)
PANEL_BG      = (50,  50,  75)
PANEL_BORDER  = (95, 100, 130)
TEXT_COLOR    = (255, 255, 255)
TEXT_DIM      = (160, 160, 180)
TEXT_HINT     = (255, 220, 100)

BTN_BORDER    = (200, 200, 220)
INPUT_BG      = (30,  30,  50)
INPUT_BORDER_ACTIVE = (255, 220, 100)
INPUT_BORDER_IDLE   = (95, 100, 130)

# Button colours per mode
_BTN_COLORS = {
    "solo": ((50, 110,  70), (80, 150, 100)),
    "host": ((70, 100, 140), (100, 140, 190)),
    "join": ((120, 60, 160), (160,  90, 210)),
    "confirm": ((70, 100, 140), (100, 140, 190)),
}


class TitleScreen:
    """
    Pygame title/menu screen.  Call .run() to display it;
    returns config dict when the user confirms a mode.
    """

    BTN_W     = 280
    BTN_H     = 54
    BTN_GAP   = 22
    INPUT_W   = 340
    INPUT_H   = 42
    CONFIRM_W = 160
    CONFIRM_H = 48

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self.screen = screen
        self.clock  = clock

        self._font_title   = pygame.font.SysFont(None, 100)
        self._font_sub     = pygame.font.SysFont(None, 34)
        self._font_btn     = pygame.font.SysFont(None, 30)
        self._font_label   = pygame.font.SysFont(None, 24)

        self._state        = "main"   # "main" | "input"
        self._mode: str | None = None
        self._name_buf     = ""
        self._ip_buf       = "localhost"
        self._active_field = "name"   # "name" | "ip"
        self._confirm_flag = False    # set by Enter key

    # ── public ────────────────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Blocking loop; returns config dict when user confirms."""
        while True:
            mouse = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit

                elif event.type == pygame.WINDOWRESIZED:
                    self.screen = pygame.display.get_surface()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self._on_click(event.pos, mouse)
                    if result is not None:
                        return result

                elif event.type == pygame.KEYDOWN:
                    self._on_key(event)

            # Enter-key confirmation
            if self._confirm_flag and self._state == "input":
                self._confirm_flag = False
                return self._make_result()

            self.screen.fill(BG_COLOR)
            if self._state == "main":
                self._draw_main(mouse)
            else:
                self._draw_input(mouse)
            pygame.display.flip()
            self.clock.tick(60)

    # ── event handlers ────────────────────────────────────────────────────────

    def _on_click(self, pos: tuple[int, int], mouse: tuple[int, int]) -> dict[str, Any] | None:
        W, H = self.screen.get_size()

        if self._state == "main":
            cx    = W // 2
            bx    = cx - self.BTN_W // 2
            total = 3 * self.BTN_H + 2 * self.BTN_GAP
            sy    = H // 2 - total // 2 + 50

            for i, mode in enumerate(("solo", "host", "join")):
                rect = pygame.Rect(bx, sy + i * (self.BTN_H + self.BTN_GAP),
                                   self.BTN_W, self.BTN_H)
                if rect.collidepoint(pos):
                    self._mode         = mode
                    self._state        = "input"
                    self._name_buf     = ""
                    self._ip_buf       = "localhost"
                    self._active_field = "name"
                    return None

        else:  # input state
            cx = W // 2

            # Confirm button
            confirm_rect = self._confirm_rect(W, H)
            if confirm_rect.collidepoint(pos):
                return self._make_result()

            # Field focus (join mode has two fields)
            name_rect = self._name_field_rect(cx, H)
            if name_rect.collidepoint(pos):
                self._active_field = "name"
                return None

            if self._mode == "join":
                ip_rect = self._ip_field_rect(cx, H)
                if ip_rect.collidepoint(pos):
                    self._active_field = "ip"

        return None

    def _on_key(self, event: pygame.event.Event) -> None:
        if self._state == "main":
            return

        if event.key == pygame.K_ESCAPE:
            self._state = "main"
            self._mode  = None
            return

        if event.key == pygame.K_RETURN:
            self._confirm_flag = True
            return

        if event.key == pygame.K_TAB and self._mode == "join":
            self._active_field = "ip" if self._active_field == "name" else "name"
            return

        if event.key == pygame.K_BACKSPACE:
            if self._active_field == "name":
                self._name_buf = self._name_buf[:-1]
            else:
                self._ip_buf = self._ip_buf[:-1]
            return

        ch = event.unicode
        if ch and ch.isprintable():
            if self._active_field == "name" and len(self._name_buf) < 20:
                self._name_buf += ch
            elif self._active_field == "ip" and len(self._ip_buf) < 50:
                self._ip_buf += ch

    # ── drawing ───────────────────────────────────────────────────────────────

    def _draw_main(self, mouse: tuple[int, int]) -> None:
        W, H = self.screen.get_size()
        cx = W // 2

        # Title
        title_surf = self._font_title.render("COUP", True, (255, 220, 0))
        self.screen.blit(title_surf, (cx - title_surf.get_width() // 2, 70))

        sub_surf = self._font_sub.render("A Game of Deception", True, TEXT_DIM)
        self.screen.blit(sub_surf, (cx - sub_surf.get_width() // 2, 185))

        # Buttons
        bx    = cx - self.BTN_W // 2
        total = 3 * self.BTN_H + 2 * self.BTN_GAP
        sy    = H // 2 - total // 2 + 50

        labels = ("Play Solo", "Host Game", "Join Game")
        modes  = ("solo", "host", "join")
        for i, (label, mode) in enumerate(zip(labels, modes)):
            y    = sy + i * (self.BTN_H + self.BTN_GAP)
            rect = pygame.Rect(bx, y, self.BTN_W, self.BTN_H)
            self._draw_btn(rect, label, mode, mouse)

    def _draw_input(self, mouse: tuple[int, int]) -> None:
        W, H = self.screen.get_size()
        cx = W // 2

        # Mode heading
        heading = {"solo": "Play Solo", "host": "Host Game", "join": "Join Game"}
        h_surf = self._font_sub.render(heading[self._mode], True, TEXT_HINT)
        self.screen.blit(h_surf, (cx - h_surf.get_width() // 2, 80))

        esc_surf = self._font_label.render("Esc to go back", True, TEXT_DIM)
        self.screen.blit(esc_surf, (cx - esc_surf.get_width() // 2, 124))

        # Name field
        name_rect = self._name_field_rect(cx, H)
        self._draw_field(name_rect, "Your Name", self._name_buf,
                         active=(self._active_field == "name"),
                         placeholder="Type your name…")

        # IP field (join only)
        if self._mode == "join":
            ip_rect = self._ip_field_rect(cx, H)
            self._draw_field(ip_rect, "Server IP", self._ip_buf,
                             active=(self._active_field == "ip"),
                             placeholder="localhost")
            tab_s = self._font_label.render("Tab to switch fields · Enter to confirm",
                                            True, TEXT_DIM)
            self.screen.blit(tab_s, (cx - tab_s.get_width() // 2,
                                     ip_rect.bottom + 14))
        else:
            enter_s = self._font_label.render("Enter to confirm", True, TEXT_DIM)
            self.screen.blit(enter_s, (cx - enter_s.get_width() // 2,
                                       name_rect.bottom + 14))

        # Confirm button
        confirm_rect = self._confirm_rect(W, H)
        go_label = "Start" if self._mode in ("solo", "host") else "Connect"
        self._draw_btn(confirm_rect, go_label, "confirm", mouse)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _name_field_rect(self, cx: int, H: int) -> pygame.Rect:
        y = H // 2 - (self.INPUT_H + 30) // 2 - (20 if self._mode == "join" else 0)
        return pygame.Rect(cx - self.INPUT_W // 2, y, self.INPUT_W, self.INPUT_H)

    def _ip_field_rect(self, cx: int, H: int) -> pygame.Rect:
        base = self._name_field_rect(cx, H)
        return pygame.Rect(base.x, base.bottom + 50, self.INPUT_W, self.INPUT_H)

    def _confirm_rect(self, W: int, H: int) -> pygame.Rect:
        return pygame.Rect(W // 2 - self.CONFIRM_W // 2,
                           H - 110,
                           self.CONFIRM_W, self.CONFIRM_H)

    def _draw_field(self, rect: pygame.Rect, label: str, buf: str,
                    active: bool, placeholder: str) -> None:
        lbl_s = self._font_label.render(label + ":", True, TEXT_COLOR)
        self.screen.blit(lbl_s, (rect.x, rect.y - 22))

        pygame.draw.rect(self.screen, INPUT_BG, rect, border_radius=6)
        border = INPUT_BORDER_ACTIVE if active else INPUT_BORDER_IDLE
        pygame.draw.rect(self.screen, border, rect, width=2, border_radius=6)

        display = buf + ("|" if active else "")
        if display:
            surf = self._font_btn.render(display, True, TEXT_COLOR)
        else:
            surf = self._font_btn.render(placeholder, True, TEXT_DIM)
        self.screen.blit(surf, (rect.x + 10,
                                rect.centery - surf.get_height() // 2))

    def _draw_btn(self, rect: pygame.Rect, label: str,
                  mode: str, mouse: tuple[int, int]) -> None:
        color, hover = _BTN_COLORS.get(mode, _BTN_COLORS["confirm"])
        hovered = rect.collidepoint(mouse)
        pygame.draw.rect(self.screen, hover if hovered else color,
                         rect, border_radius=8)
        pygame.draw.rect(self.screen, BTN_BORDER, rect, width=1, border_radius=8)
        surf = self._font_btn.render(label, True, TEXT_COLOR)
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                rect.centery - surf.get_height() // 2))

    def _make_result(self) -> dict[str, Any]:
        return {
            "mode":      self._mode,
            "name":      (self._name_buf.strip() or "Player")[:20],
            "host_ip":   self._ip_buf.strip() or "localhost",
            "host_port": 1235,
        }
