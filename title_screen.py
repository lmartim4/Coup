"""
title_screen.py  –  Coup game title screen

Shows the main menu (Play Solo / Host Game / Join Game) and collects
the player's name (and server IP for Join mode).

Returns a dict:
  {"mode": "solo"|"host"|"join", "name": str, "host_ip": str, "host_port": int}
"""

import json as _json
import socket as _socket
import threading as _threading
import time as _time
from typing import Any, Dict, List, Optional, Set, Tuple

import pygame

# ── palette (mirrors renderer.py) ─────────────────────────────────────────────
BG_COLOR      = (40,  40,  60)
PANEL_BG      = (50,  50,  75)
PANEL_BORDER  = (95, 100, 130)
TEXT_COLOR    = (255, 255, 255)
TEXT_DIM      = (160, 160, 180)
TEXT_HINT     = (255, 220, 100)

_DISCOVERY_PORT = 1235

BTN_BORDER    = (200, 200, 220)
INPUT_BG      = (30,  30,  50)
INPUT_BORDER_ACTIVE = (255, 220, 100)
INPUT_BORDER_IDLE   = (95, 100, 130)

SERVER_ROW_BG    = (35,  35,  55)
SERVER_ROW_HOVER = (55,  60,  90)
SERVER_ROW_SEL   = (40,  80,  40)

# Button colours per mode
_BTN_COLORS = {
    "solo": ((50, 110,  70), (80, 150, 100)),
    "host": ((70, 100, 140), (100, 140, 190)),
    "join": ((120, 60, 160), (160,  90, 210)),
    "confirm": ((70, 100, 140), (100, 140, 190)),
}


def _scan_lan(port: int = _DISCOVERY_PORT, timeout: float = 1.5) -> List[dict]:
    """Send a UDP broadcast and collect replies from Coup servers on the LAN."""
    results: List[dict] = []
    seen: Set[str] = set()
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM) as sock:
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_BROADCAST, 1)
            for target in ("127.0.0.1", "255.255.255.255"):
                try:
                    sock.sendto(b"COUP_DISCOVER", (target, port))
                except OSError:
                    pass
            deadline = _time.monotonic() + timeout
            while True:
                remaining = deadline - _time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    data, addr = sock.recvfrom(1024)
                except _socket.timeout:
                    break
                except OSError:
                    break
                ip = addr[0]
                if ip in seen:
                    continue
                seen.add(ip)
                try:
                    info = _json.loads(data.decode())
                    if info.get("type") == "coup_server":
                        info["ip"] = ip
                        results.append(info)
                except _json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return results


class TitleScreen:
    """
    Pygame title/menu screen.  Call .run() to display it;
    returns config dict when the user confirms a mode.
    """

    BTN_W        = 280
    BTN_H        = 54
    BTN_GAP      = 22
    INPUT_W      = 340
    INPUT_H      = 42
    CONFIRM_W    = 160
    CONFIRM_H    = 48
    LIST_ROW_H   = 38
    LIST_MAX_ROWS = 3

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self.screen = screen
        self.clock  = clock

        self._font_title   = pygame.font.SysFont(None, 100)
        self._font_sub     = pygame.font.SysFont(None, 34)
        self._font_btn     = pygame.font.SysFont(None, 30)
        self._font_label   = pygame.font.SysFont(None, 24)

        self._state        = "main"   # "main" | "input"
        self._mode: Optional[str]= None
        self._name_buf     = ""
        self._ip_buf       = "localhost"
        self._active_field = "name"   # "name" | "ip"
        self._confirm_flag = False    # set by Enter key

        # LAN discovery (join mode only)
        self._lan_servers: List[dict]             = []
        self._scan_done:   bool                   = True
        self._scan_thread: Optional[_threading.Thread]= None

    # ── public ────────────────────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
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

    def _start_scan(self) -> None:
        """Launch a background thread that UDP-broadcasts for Coup servers."""
        self._lan_servers = []
        self._scan_done   = False
        def _worker() -> None:
            self._lan_servers = _scan_lan()
            self._scan_done   = True
        self._scan_thread = _threading.Thread(target=_worker, daemon=True)
        self._scan_thread.start()

    # ── event handlers ────────────────────────────────────────────────────────

    def _on_click(self, pos: Tuple[int, int], mouse: Tuple[int, int]) -> Optional[Dict[str, Any]]:
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
                    if mode == "join":
                        self._start_scan()
                    return None

        else:  # input state
            cx = W // 2

            # Confirm button
            confirm_rect = self._confirm_rect(W, H)
            if confirm_rect.collidepoint(pos):
                return self._make_result()

            if self._mode == "join":
                # Name field
                if self._join_name_rect(cx, H).collidepoint(pos):
                    self._active_field = "name"
                    return None
                # Server list rows – clicking auto-fills the IP field
                for i, srv in enumerate(self._lan_servers[:self.LIST_MAX_ROWS]):
                    if self._join_server_row_rect(cx, H, i).collidepoint(pos):
                        self._ip_buf       = srv["ip"]
                        self._active_field = "ip"
                        return None
                # IP field
                if self._join_ip_rect(cx, H).collidepoint(pos):
                    self._active_field = "ip"
                    return None
                # Refresh button
                if self._join_refresh_rect(cx, H).collidepoint(pos) and self._scan_done:
                    self._start_scan()
            else:
                # Field focus (solo/host only have name field)
                name_rect = self._name_field_rect(cx, H)
                if name_rect.collidepoint(pos):
                    self._active_field = "name"
                    return None

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

    def _draw_main(self, mouse: Tuple[int, int]) -> None:
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

    def _draw_input(self, mouse: Tuple[int, int]) -> None:
        if self._mode == "join":
            self._draw_join_input(mouse)
            return

        W, H = self.screen.get_size()
        cx = W // 2

        # Mode heading
        heading = {"solo": "Play Solo", "host": "Host Game"}
        h_surf = self._font_sub.render(heading[self._mode], True, TEXT_HINT)
        self.screen.blit(h_surf, (cx - h_surf.get_width() // 2, 80))

        esc_surf = self._font_label.render("Esc to go back", True, TEXT_DIM)
        self.screen.blit(esc_surf, (cx - esc_surf.get_width() // 2, 124))

        # Name field
        name_rect = self._name_field_rect(cx, H)
        self._draw_field(name_rect, "Your Name", self._name_buf,
                         active=(self._active_field == "name"),
                         placeholder="Type your name…")

        enter_s = self._font_label.render("Enter to confirm", True, TEXT_DIM)
        self.screen.blit(enter_s, (cx - enter_s.get_width() // 2,
                                   name_rect.bottom + 14))

        # Confirm button
        confirm_rect = self._confirm_rect(W, H)
        self._draw_btn(confirm_rect, "Start", "confirm", mouse)

    def _draw_join_input(self, mouse: Tuple[int, int]) -> None:
        """Join-mode input screen: name field + LAN server list + IP field."""
        W, H = self.screen.get_size()
        cx   = W // 2
        base = self._join_base_y(H)

        # Heading
        h_surf = self._font_sub.render("Join Game", True, TEXT_HINT)
        self.screen.blit(h_surf, (cx - h_surf.get_width() // 2, base))

        esc_s = self._font_label.render("Esc to go back", True, TEXT_DIM)
        self.screen.blit(esc_s, (cx - esc_s.get_width() // 2, base + 42))

        # Name field
        name_rect = self._join_name_rect(cx, H)
        self._draw_field(name_rect, "Your Name", self._name_buf,
                         active=(self._active_field == "name"),
                         placeholder="Type your name…")

        # ── LAN server list ───────────────────────────────────────────────────
        lst_rect = self._join_list_rect(cx, H)

        # Header label
        hdr_s = self._font_label.render("LAN Servers:", True, TEXT_COLOR)
        self.screen.blit(hdr_s, (lst_rect.x, lst_rect.y - 22))

        # Refresh button (top-right of the list header)
        ref_rect  = self._join_refresh_rect(cx, H)
        scanning  = not self._scan_done
        ref_idle  = (45, 60,  90)
        ref_hover = (70, 100, 150)
        ref_bg    = ref_idle if scanning else (ref_hover if ref_rect.collidepoint(mouse) else ref_idle)
        pygame.draw.rect(self.screen, ref_bg, ref_rect, border_radius=4)
        ref_lbl = "Scanning" if scanning else "Refresh"
        ref_col = TEXT_DIM if scanning else TEXT_COLOR
        ref_s   = self._font_label.render(ref_lbl, True, ref_col)
        self.screen.blit(ref_s, (ref_rect.centerx - ref_s.get_width() // 2,
                                  ref_rect.centery - ref_s.get_height() // 2))

        # List box background + border
        pygame.draw.rect(self.screen, SERVER_ROW_BG, lst_rect, border_radius=6)
        pygame.draw.rect(self.screen, INPUT_BORDER_IDLE, lst_rect, width=1, border_radius=6)

        servers = self._lan_servers[:self.LIST_MAX_ROWS]
        if not servers:
            msg = "Scanning\u2026" if not self._scan_done else "No servers found on LAN"
            msg_s = self._font_label.render(msg, True, TEXT_DIM)
            self.screen.blit(msg_s, (lst_rect.centerx - msg_s.get_width() // 2,
                                      lst_rect.centery - msg_s.get_height() // 2))
        else:
            n = len(servers)
            for i, srv in enumerate(servers):
                row    = self._join_server_row_rect(cx, H, i)
                is_sel = srv["ip"] == self._ip_buf
                hovered = row.collidepoint(mouse)
                bg = SERVER_ROW_SEL if is_sel else (SERVER_ROW_HOVER if hovered else SERVER_ROW_BG)
                tl = tr = 6 if i == 0     else 0
                bl = br = 6 if i == n - 1 else 0
                pygame.draw.rect(self.screen, bg, row,
                                 border_top_left_radius=tl, border_top_right_radius=tr,
                                 border_bottom_left_radius=bl, border_bottom_right_radius=br)
                if i < n - 1:
                    pygame.draw.line(self.screen, INPUT_BORDER_IDLE,
                                     (row.x + 6, row.bottom - 1),
                                     (row.right - 6, row.bottom - 1))
                ip      = srv.get("ip", "?")
                players = srv.get("players", "?")
                max_p   = srv.get("max", "?")
                status  = "In Progress" if srv.get("started") else "Waiting"
                label   = f"{ip}   {players}/{max_p} players   [{status}]"
                row_s   = self._font_btn.render(label, True, TEXT_COLOR)
                self.screen.blit(row_s, (row.x + 10,
                                          row.centery - row_s.get_height() // 2))

        # IP field
        ip_rect = self._join_ip_rect(cx, H)
        self._draw_field(ip_rect, "Server IP", self._ip_buf,
                         active=(self._active_field == "ip"),
                         placeholder="localhost")

        # Hints
        hint_s = self._font_label.render(
            "Tab to switch fields  \u00b7  click a server to auto-fill  \u00b7  Enter to confirm",
            True, TEXT_DIM)
        self.screen.blit(hint_s, (cx - hint_s.get_width() // 2, ip_rect.bottom + 10))

        # Confirm button
        self._draw_btn(self._confirm_rect(W, H), "Connect", "join", mouse)

    # ── helpers ───────────────────────────────────────────────────────────────

    # ── join-mode layout helpers ───────────────────────────────────────────────

    def _join_base_y(self, H: int) -> int:
        """Top-of-content y so the join panel is vertically centred."""
        return max(20, (H - 110 - 400) // 2)

    def _join_name_rect(self, cx: int, H: int) -> pygame.Rect:
        base = self._join_base_y(H)
        return pygame.Rect(cx - self.INPUT_W // 2, base + 94, self.INPUT_W, self.INPUT_H)

    def _join_list_rect(self, cx: int, H: int) -> pygame.Rect:
        base = self._join_base_y(H)
        h    = self.LIST_MAX_ROWS * self.LIST_ROW_H
        return pygame.Rect(cx - self.INPUT_W // 2, base + 163, self.INPUT_W, h)

    def _join_server_row_rect(self, cx: int, H: int, i: int) -> pygame.Rect:
        lst = self._join_list_rect(cx, H)
        return pygame.Rect(lst.x, lst.y + i * self.LIST_ROW_H, lst.width, self.LIST_ROW_H)

    def _join_ip_rect(self, cx: int, H: int) -> pygame.Rect:
        lst = self._join_list_rect(cx, H)
        return pygame.Rect(cx - self.INPUT_W // 2, lst.bottom + 38, self.INPUT_W, self.INPUT_H)

    def _join_refresh_rect(self, cx: int, H: int) -> pygame.Rect:
        lst = self._join_list_rect(cx, H)
        return pygame.Rect(lst.right - 78, lst.y - 24, 78, 22)

    # ── original layout helpers ────────────────────────────────────────────────

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
                  mode: str, mouse: Tuple[int, int]) -> None:
        color, hover = _BTN_COLORS.get(mode, _BTN_COLORS["confirm"])
        hovered = rect.collidepoint(mouse)
        pygame.draw.rect(self.screen, hover if hovered else color,
                         rect, border_radius=8)
        pygame.draw.rect(self.screen, BTN_BORDER, rect, width=1, border_radius=8)
        surf = self._font_btn.render(label, True, TEXT_COLOR)
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                rect.centery - surf.get_height() // 2))

    def _make_result(self) -> Dict[str, Any]:
        return {
            "mode":      self._mode,
            "name":      (self._name_buf.strip() or "Player")[:20],
            "host_ip":   self._ip_buf.strip() or "localhost",
            "host_port": 1235,
        }
