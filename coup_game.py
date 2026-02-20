"""
coup_game.py  –  Coup pygame client
Connects automatically to coup_server.py at localhost:1235.
Start the server first, then run this file.

Usage:
  python coup_game.py [YourName]
  (If no name is given you will be prompted.)

Protocol: newline-delimited JSON over plain TCP.

Lobby phase:
  Client → Server: {"type": "lobby_join", "name": "<name>"}
  Server → Client: {"type": "lobby_state", "players": ["name1", ...]}

Game phase:
  Server → Client: {"type": "state",    "data": <GameStateView dict>}
  Client → Server: {"type": "decision", "choice": <serialized choice>}

Choice serialization rules (mirror of coup_server.py):
  PICK_ACTION      → action name string  (e.g. "Duque")
  PICK_TARGET      → int                 (player index)
  LOSE_INFLUENCE   → int                 (card index in hand)
  all others       → DecisionResponse.value string  (e.g. "pass", "block")
"""

import asyncio
import json
import queue
import sys
import threading

import pygame

from renderer import Renderer
from game_state import (
    GameStateView,
    PlayerStateView,
    PendingDecision,
    DecisionType,
    DecisionResponse,
)

HOST = "localhost"
PORT = 1235


# ── thin proxy so the Renderer can call .get_name() on deserialized actions ──

class _ActionProxy:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


# ── serialization helpers ─────────────────────────────────────────────────────

def _deserialize_state(data: dict) -> GameStateView:
    players = [PlayerStateView(**p) for p in data["players"]]

    pd = data.get("pending_decision")
    if pd:
        dt = DecisionType(pd["decision_type"])
        raw_opts = pd["options"]

        if dt == DecisionType.PICK_ACTION:
            options = [_ActionProxy(o) for o in raw_opts]
        else:
            options = raw_opts  # ints for PICK_TARGET / LOSE_INFLUENCE; strings otherwise

        pending = PendingDecision(
            player_index=pd["player_index"],
            decision_type=dt,
            options=options,
            context=pd.get("context", {}),
        )
    else:
        pending = None

    return GameStateView(
        players=players,
        current_turn=data["current_turn"],
        pending_decision=pending,
        viewer_index=data["viewer_index"],
    )


def _serialize_choice(choice) -> object:
    """Convert a click result into a JSON-safe value for the server."""
    if isinstance(choice, _ActionProxy):
        return choice.get_name()
    if isinstance(choice, DecisionResponse):
        return choice.value
    return choice  # int (PICK_TARGET / LOSE_INFLUENCE)


# ── main client class ─────────────────────────────────────────────────────────

class CoupGame:

    def __init__(self, player_name: str) -> None:
        self._player_name = player_name

        pygame.init()
        screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption(f"Coup – {player_name}")
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 22)
        self.renderer = Renderer(screen, self.font)

        # Shared state between pygame thread and network thread.
        self._state: GameStateView | None = None
        self._clickable: list = []
        self._game_over: bool = False
        self._status_msg: str = f"Connecting to {HOST}:{PORT}…"

        # Thread-safe channels.
        self._state_queue: queue.Queue = queue.Queue()    # network → pygame
        self._decision_queue: queue.Queue = queue.Queue()  # pygame → network

    # ── pygame loop ────────────────────────────────────────────────────────────

    def run(self) -> None:
        net_thread = threading.Thread(target=self._network_thread, daemon=True)
        net_thread.start()

        running = True
        while running:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            # Drain incoming state updates; keep only the latest.
            latest = None
            try:
                while True:
                    latest = self._state_queue.get_nowait()
            except queue.Empty:
                pass
            if latest is not None:
                self._state = latest
                if latest.pending_decision is None:
                    self._game_over = True

            # Render.
            self.renderer.clear()
            if self._state is not None:
                self._clickable = self.renderer.draw(self._state, mouse_pos)
            else:
                self._draw_status(self._status_msg)
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def _draw_status(self, msg: str) -> None:
        font = pygame.font.SysFont(None, 36)
        W, H = self.screen.get_size()
        lines = msg.split("\n")
        y = H // 2 - (len(lines) * 44) // 2
        for line in lines:
            surf = font.render(line, True, (200, 200, 200))
            self.screen.blit(surf, (W // 2 - surf.get_width() // 2, y))
            y += 44

    def _handle_click(self, pos: tuple) -> None:
        if self._state is None or self._game_over:
            return
        decision = self._state.pending_decision
        if decision is None or decision.player_index != self._state.viewer_index:
            return
        for rect, choice in self._clickable:
            if rect.collidepoint(pos):
                raw = _serialize_choice(choice)
                print(f"[{self._player_name}] {decision.decision_type.value} → {raw}")
                self._decision_queue.put(raw)
                break

    # ── network thread ─────────────────────────────────────────────────────────

    def _network_thread(self) -> None:
        asyncio.run(self._async_network())

    async def _async_network(self) -> None:
        while not self._game_over:
            try:
                reader, writer = await asyncio.open_connection(HOST, PORT)
            except (ConnectionRefusedError, OSError):
                self._status_msg = f"Waiting for server at {HOST}:{PORT}…"
                await asyncio.sleep(1)
                continue

            print(f"[Client] Connected to {HOST}:{PORT}")

            # ── Send lobby join immediately ─────────────────────────────────
            join_msg = json.dumps({"type": "lobby_join", "name": self._player_name}) + "\n"
            writer.write(join_msg.encode())
            await writer.drain()
            self._status_msg = "In lobby — waiting for more players…"

            send_task = asyncio.create_task(self._send_loop(writer))
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    try:
                        msg = json.loads(data.decode().strip())
                    except json.JSONDecodeError:
                        continue

                    mtype = msg.get("type")

                    if mtype == "lobby_state":
                        players = msg.get("players", [])
                        names = ", ".join(players) if players else "—"
                        self._status_msg = (
                            f"Lobby ({len(players)}/6): {names}\n"
                            "Type 's' on the server console to start."
                        )

                    elif mtype == "state":
                        state = _deserialize_state(msg["data"])
                        self._state_queue.put(state)
                        if state.pending_decision is None:
                            self._game_over = True

                    elif mtype == "error":
                        self._status_msg = f"Server error: {msg.get('msg', '?')}"
                        break

            except (ConnectionResetError, BrokenPipeError, OSError):
                pass
            except Exception as exc:
                print(f"[Client] Network error: {exc}")
            finally:
                send_task.cancel()
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

            if not self._game_over:
                print("[Client] Disconnected. Retrying in 1 s…")
                self._status_msg = "Reconnecting…"
                await asyncio.sleep(1)

    async def _send_loop(self, writer: asyncio.StreamWriter) -> None:
        """Forwards choices from the pygame thread to the server."""
        while True:
            try:
                choice = self._decision_queue.get_nowait()
                msg = json.dumps({"type": "decision", "choice": choice}) + "\n"
                writer.write(msg.encode())
                await writer.drain()
            except queue.Empty:
                await asyncio.sleep(0.01)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        player_name = sys.argv[1][:20]
    else:
        player_name = input("Enter your name: ").strip()[:20] or "Player"
    CoupGame(player_name).run()
