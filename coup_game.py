import asyncio
import json
import queue
import threading
from typing import Any
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

class _ActionProxy:
    def __init__(self, name: str):
        self._name = name

    def get_name(self) -> str:
        return self._name

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
        cards_per_type=data.get("cards_per_type", {}),
    )


def _serialize_choice(choice: Any) -> str | int:
    """Convert a click result into a JSON-safe value for the server."""
    if isinstance(choice, _ActionProxy):
        return choice.get_name()
    if isinstance(choice, DecisionResponse):
        return choice.value
    return choice  # int (PICK_TARGET / LOSE_INFLUENCE)


# ── main client class ─────────────────────────────────────────────────────────

class CoupGame:

    # Button colours for the lobby "Start Game" button
    _START_BTN_COLOR = (50, 110,  70)
    _START_BTN_HOVER = (80, 150, 100)
    _START_BTN_W     = 200
    _START_BTN_H     = 44

    def __init__(
        self,
        player_name: str,
        host: str = HOST,
        port: int = PORT,
        is_host: bool = False,
        server_ref=None,
        screen: pygame.Surface | None = None,
        clock: pygame.time.Clock | None = None,
    ):
        self._player_name = player_name
        self._host        = host
        self._port        = port
        self._is_host     = is_host
        self._server_ref  = server_ref

        if screen is None:
            pygame.init()
            screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        pygame.display.set_caption(f"Coup – {player_name}")
        self.screen = screen
        self.clock  = clock if clock is not None else pygame.time.Clock()
        self.font   = pygame.font.SysFont(None, 22)
        self.renderer = Renderer(screen, self.font)

        # Shared state between pygame thread and network thread.
        self._state: GameStateView | None = None
        self._clickable: list[tuple[pygame.Rect, Any]] = []
        self._game_over: bool = False
        self._status_msg: str = f"Connecting to {host}:{port}…"

        # Rect for the lobby "Start Game" button (host mode only).
        self._start_btn_rect: pygame.Rect | None = None

        # Thread-safe channels.
        self._state_queue: queue.Queue[GameStateView] = queue.Queue()    # network → pygame
        self._decision_queue: queue.Queue[str | int] = queue.Queue()  # pygame → network

        # Speech-bubble deduplication key (prevents re-triggering the same announcement).
        self._last_bubble_key: tuple[Any, ...] | None = None
        # Tracks the last current_turn seen, used to detect Renda (no-announcement action).
        self._prev_turn: int | None = None

    # ── pygame loop ────────────────────────────────────────────────────────────

    def run(self):
        net_thread = threading.Thread(target=self._network_thread, daemon=True)
        net_thread.start()

        running = True
        while running:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.WINDOWRESIZED:
                    self.screen = pygame.display.get_surface()
                    self.renderer.screen = self.screen
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            # Drain incoming state updates.
            # Spawn bubbles for EVERY queued state (so no announcement is missed
            # when the server sends several states in rapid succession for bot turns),
            # but only render the latest one to keep the display smooth.
            latest = None
            try:
                while True:
                    s = self._state_queue.get_nowait()
                    self._check_and_spawn_bubble(s)
                    latest = s
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
                self._draw_status(self._status_msg, mouse_pos)
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def _draw_status(self, msg: str, mouse_pos: tuple[int, int] = (0, 0)) -> None:
        font = pygame.font.SysFont(None, 36)
        W, H = self.screen.get_size()
        lines = msg.split("\n")
        y = H // 2 - (len(lines) * 44) // 2
        for line in lines:
            surf = font.render(line, True, (200, 200, 200))
            self.screen.blit(surf, (W // 2 - surf.get_width() // 2, y))
            y += 44

        # "Start Game" button for host mode (shown only while in lobby)
        if self._is_host:
            bx = W // 2 - self._START_BTN_W // 2
            by = y + 20
            rect = pygame.Rect(bx, by, self._START_BTN_W, self._START_BTN_H)
            hovered = rect.collidepoint(mouse_pos)
            pygame.draw.rect(
                self.screen,
                self._START_BTN_HOVER if hovered else self._START_BTN_COLOR,
                rect, border_radius=8,
            )
            pygame.draw.rect(self.screen, (200, 200, 220), rect, width=1, border_radius=8)
            btn_font = pygame.font.SysFont(None, 28)
            label = btn_font.render("Start Game", True, (255, 255, 255))
            self.screen.blit(label, (
                rect.centerx - label.get_width() // 2,
                rect.centery - label.get_height() // 2,
            ))
            self._start_btn_rect = rect

    def _handle_click(self, pos: tuple[int, int]) -> None:
        # Lobby "Start Game" button (host mode, before game state arrives)
        if (self._state is None
                and self._is_host
                and self._start_btn_rect is not None
                and self._start_btn_rect.collidepoint(pos)
                and self._server_ref is not None):
            self._server_ref.request_start_threadsafe()
            return

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

    def _check_and_spawn_bubble(self, state: GameStateView) -> None:
        pd = state.pending_decision
        if pd is None:
            return

        ctx  = pd.context
        dt   = pd.decision_type
        turn = state.current_turn  # disambiguates the same player acting on different turns

        if (self._prev_turn is not None
                and turn != self._prev_turn
                and (self._last_bubble_key is None
                     or self._last_bubble_key[3] != self._prev_turn)):
            renda_key = ('announce', self._prev_turn, 'Renda', self._prev_turn)
            self._last_bubble_key = renda_key
            self.renderer.add_bubble("Renda!", self._prev_turn, state)

        self._prev_turn = turn

        text        = None
        speaker_idx = None
        key         = None

        if dt == DecisionType.PICK_TARGET:
            # Player picked an action that needs a target (Golpe, Assassino, Capitao…).
            # This is the first announcement state for targeted actions.
            action      = ctx.get('action_name', '?')
            speaker_idx = state.current_turn
            key         = ('announce', speaker_idx, action, turn)
            text        = f"{action}!"

        elif dt == DecisionType.CHALLENGE_ACTION:
            # Player announced a card-based action (Duque, etc.) — non-targeted.
            actor_idx   = ctx.get('actor_idx')
            action      = ctx.get('action_name', '?')
            speaker_idx = actor_idx
            key         = ('announce', actor_idx, action, turn)
            text        = f"Sou o {action}!"

        elif dt == DecisionType.CHALLENGE_BLOCK:
            blocker_idx = ctx.get('blocker_idx')
            card        = ctx.get('block_card', '?')
            speaker_idx = blocker_idx
            key         = ('announce', blocker_idx, card, turn)
            text        = f"Bloqueio com {card}!"

        elif dt == DecisionType.BLOCK_OR_PASS:
            actor_idx   = ctx.get('actor_idx')
            action      = ctx.get('action_name', '?')
            speaker_idx = actor_idx
            key         = ('announce', actor_idx, action, turn)
            text        = f"{action}!"

        elif dt == DecisionType.DEFEND:
            # Attacker already announced via PICK_TARGET — shares the same key,
            # so this only fires if PICK_TARGET state was never seen by this client.
            attacker_idx = ctx.get('attacker_idx')
            action       = ctx.get('action_name', '?')
            speaker_idx  = attacker_idx
            key          = ('announce', attacker_idx, action, turn)
            text         = f"{action}!"

        if key and key != self._last_bubble_key and speaker_idx is not None and text is not None:
            self._last_bubble_key = key
            self.renderer.add_bubble(text, speaker_idx, state)

    def _network_thread(self) -> None:
        asyncio.run(self._async_network())

    async def _async_network(self):
        while not self._game_over:
            try:
                reader, writer = await asyncio.open_connection(self._host, self._port)
            except (ConnectionRefusedError, OSError):
                self._status_msg = f"Waiting for server at {self._host}:{self._port}…"
                await asyncio.sleep(1)
                continue

            print(f"[Client] Connected to {self._host}:{self._port}")

            # ── Send lobby join immediately ─────────────────────────────────
            join_msg = json.dumps({"type": "lobby_join", "name": self._player_name}) + "\n"
            writer.write(join_msg.encode())
            await writer.drain()
            self._status_msg = "In lobby — waiting…"

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
                        if self._is_host:
                            self._status_msg = (
                                f"Lobby ({len(players)}/6): {names}\n"
                                "Click 'Start Game' when ready."
                            )
                        else:
                            self._status_msg = (
                                f"Lobby ({len(players)}/6): {names}\n"
                                "Waiting for host to start…"
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

    async def _send_loop(self, writer: asyncio.StreamWriter):
        """Forwards choices from the pygame thread to the server."""
        while True:
            try:
                choice = self._decision_queue.get_nowait()
                msg = json.dumps({"type": "decision", "choice": choice}) + "\n"
                writer.write(msg.encode())
                await writer.drain()
            except queue.Empty:
                await asyncio.sleep(0.01)
                

if __name__ == "__main__":
    from title_screen import TitleScreen
    from coup_server import run_server_in_thread

    pygame.init()
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption("Coup")
    clock = pygame.time.Clock()
    
    config = TitleScreen(screen, clock).run()

    mode        = config["mode"]
    player_name = config["name"]
    host        = HOST
    port        = PORT
    is_host     = False
    server_ref  = None

    if mode in ("solo", "host"):
        server_ref = run_server_in_thread(auto_start=(mode == "solo"))
        host       = "localhost"
        is_host    = (mode == "host")
    else:
        host = config["host_ip"]
        port = config["host_port"]

    CoupGame(
        player_name,
        host=host,
        port=port,
        is_host=is_host,
        server_ref=server_ref,
        screen=screen,
        clock=clock,
    ).run()
