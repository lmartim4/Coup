"""
coup_server.py  –  Coup game server with lobby

Run this first, then launch coup_game.py on each client machine.
Type 's' + Enter on the server console to start the game.

Protocol: newline-delimited JSON over plain TCP.

Lobby phase:
  Client → Server: {"type": "lobby_join", "name": "<player name>"}
  Server → Client: {"type": "lobby_state", "players": ["name1", "name2", ...]}
  Server → Client: {"type": "error", "msg": "<reason>"}   (on reject)

Game phase:
  Server → Client: {"type": "state", "data": <GameStateView dict>}
  Client → Server: {"type": "decision", "choice": <serialized choice>}

Choice serialization:
  PICK_ACTION      → action name string  (e.g. "Duque")
  PICK_TARGET      → int                 (player index)
  LOSE_INFLUENCE   → int                 (card index in hand)
  all others       → DecisionResponse.value string  (e.g. "pass", "block")
"""

import asyncio
import json
import random
import sys
import threading
from typing import Any

from game_engine import GameEngine
from game_agent import Player, BotAgent
from game_state import DecisionType, DecisionResponse, PendingDecision
from influences import Assassin, Duke, Countess, Captain, Influence

HOST = "localhost"
PORT = 1235
MIN_PLAYERS = 4   # minimum total players; bots fill the gap
MAX_PLAYERS = 6

BOT_NAMES = ["Bot-Alpha", "Bot-Beta", "Bot-Gamma", "Bot-Delta", "Bot-Epsilon"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_deck() -> list[Influence]:
    deck: list[Influence] = [Assassin()] * 3 + [Duke()] * 3 + [Countess()] * 3 + [Captain()] * 3
    random.shuffle(deck)
    return deck


def _deal_players(names: list[str], deck: list[Influence]) -> list[Player]:
    players = []
    for name in names:
        influences = [deck.pop(), deck.pop()]
        players.append(Player(name, influences))
    return players


def _deserialize_choice(choice_raw: Any, decision: PendingDecision) -> Influence | int | DecisionResponse:
    """Convert the raw JSON value from the client back to a Python game object."""
    dt = decision.decision_type
    if dt == DecisionType.PICK_ACTION:
        return next(a for a in decision.options if a.get_name() == choice_raw)
    elif dt in (DecisionType.PICK_TARGET, DecisionType.LOSE_INFLUENCE):
        return int(choice_raw)
    else:
        return DecisionResponse(choice_raw)


# ── game server ───────────────────────────────────────────────────────────────

class GameServer:

    def __init__(self, auto_start: bool = False):
        # Lobby state
        self._lobby_lock = asyncio.Lock()
        # list of (name, writer) for each connected human in lobby order
        self._lobby_clients: list[tuple[str, asyncio.StreamWriter]] = []
        self._start_event = asyncio.Event()
        self._game_started = False

        # For programmatic start (solo / host modes)
        self._auto_start = auto_start
        self._server_loop: asyncio.AbstractEventLoop | None = None

        # Game state (populated in start_game)
        self._engine: GameEngine | None = None
        self._bot_agents: dict[int, BotAgent] = {}
        # player_index → asyncio.Queue (receives raw choice values from clients)
        self._human_queues: dict[int, asyncio.Queue] = {}
        # player_index → StreamWriter (to send game states)
        self._human_writers: dict[int, asyncio.StreamWriter] = {}
        # StreamWriter → player_index (reverse map, for handle_client)
        self._writer_to_index: dict[asyncio.StreamWriter, int] = {}

    # ── lobby helpers ──────────────────────────────────────────────────────────

    async def _broadcast_lobby(self):
        """Push the current lobby player list to all connected clients."""
        names = [n for n, _ in self._lobby_clients]
        msg = json.dumps({"type": "lobby_state", "players": names}) + "\n"
        for _, writer in self._lobby_clients:
            try:
                writer.write(msg.encode())
                await writer.drain()
            except Exception:
                pass

    # ── game helpers ───────────────────────────────────────────────────────────

    async def _send_state_to_all(self):
        """Send the current game state to every connected human, from their POV."""
        for pidx, writer in self._human_writers.items():
            state = self._engine.get_state_view(pidx)
            msg = json.dumps({"type": "state", "data": state.to_dict()}) + "\n"
            try:
                writer.write(msg.encode())
                await writer.drain()
            except Exception:
                pass

    async def _tick_bots(self):
        """Advance the engine through consecutive bot decisions.

        Broadcasts the current state *before* each bot acts so that clients
        see every announcement phase (e.g. CHALLENGE_ACTION, PICK_TARGET)
        and can display speech-bubble animations for them.
        """
        while True:
            decision = self._engine.pending_decision
            if decision is None or decision.player_index in self._human_queues:
                break
            # Broadcast the announcement state before the bot responds to it.
            await self._send_state_to_all()
            agent = self._bot_agents[decision.player_index]
            state_view = self._engine.get_state_view(decision.player_index)
            choice = agent.decide(state_view, decision)
            pname = self._engine.players[decision.player_index].name
            print(f"  [{pname}] {decision.decision_type.value} → "
                  f"{choice.get_name() if hasattr(choice, 'get_name') else choice}")
            self._engine.submit_decision(choice)

    async def _game_loop(self):
        """Main game loop: drives decisions and broadcasts state after each move."""
        await self._tick_bots()
        await self._send_state_to_all()

        while True:
            decision = self._engine.pending_decision
            if decision is None:
                print("[Server] Game over!")
                await self._send_state_to_all()
                break

            pidx = decision.player_index
            if pidx not in self._human_queues:
                # Shouldn't happen after _tick_bots, but guard anyway
                await self._tick_bots()
                await self._send_state_to_all()
                continue

            # Wait for the human player's decision
            choice_raw = await self._human_queues[pidx].get()

            try:
                choice = _deserialize_choice(choice_raw, decision)
            except (StopIteration, ValueError, KeyError) as exc:
                print(f"[Server] Bad choice {choice_raw!r}: {exc}")
                continue

            pname = self._engine.players[pidx].name
            print(f"  [{pname}] {decision.decision_type.value} → "
                  f"{choice.get_name() if hasattr(choice, 'get_name') else choice}")
            self._engine.submit_decision(choice)
            await self._tick_bots()
            await self._send_state_to_all()

    # ── client connection handler ──────────────────────────────────────────────

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        addr = writer.get_extra_info("peername")
        print(f"[Server] New connection from {addr}")

        # ── Step 1: read lobby_join ─────────────────────────────────────────
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=30.0)
        except asyncio.TimeoutError:
            writer.close()
            return

        if not data:
            writer.close()
            return

        try:
            msg = json.loads(data.decode().strip())
        except json.JSONDecodeError:
            writer.close()
            return

        if msg.get("type") != "lobby_join":
            writer.close()
            return

        name = str(msg.get("name", "Player"))[:20].strip() or "Player"

        # ── Step 2: add to lobby (or reject) ───────────────────────────────
        async with self._lobby_lock:
            if self._game_started:
                reply = json.dumps({"type": "error", "msg": "Game already started"}) + "\n"
                writer.write(reply.encode())
                await writer.drain()
                writer.close()
                return
            if len(self._lobby_clients) >= MAX_PLAYERS:
                reply = json.dumps({"type": "error", "msg": "Lobby is full"}) + "\n"
                writer.write(reply.encode())
                await writer.drain()
                writer.close()
                return
            self._lobby_clients.append((name, writer))
            n = len(self._lobby_clients)
            print(f"[Lobby] '{name}' joined. ({n}/{MAX_PLAYERS} players)")
            await self._broadcast_lobby()

        # Auto-start for solo mode (first human joining triggers the game)
        if self._auto_start and not self._game_started:
            asyncio.create_task(self.start_game())

        # ── Step 3: wait for game start ────────────────────────────────────
        await self._start_event.wait()

        # ── Step 4: game phase — read decisions from this client ───────────
        pidx = self._writer_to_index.get(writer)
        if pidx is None:
            writer.close()
            return

        try:
            while True:
                data = await reader.readline()
                if not data:
                    print(f"[Server] '{name}' disconnected.")
                    break
                try:
                    msg = json.loads(data.decode().strip())
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "decision":
                    await self._human_queues[pidx].put(msg["choice"])
        except (ConnectionResetError, BrokenPipeError, OSError):
            print(f"[Server] '{name}' connection lost.")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    # ── game setup ─────────────────────────────────────────────────────────────

    # ── programmatic start helpers ─────────────────────────────────────────────

    def request_start_threadsafe(self):
        """Call from any thread to request game start (host button, etc.)."""
        if self._server_loop is not None and not self._game_started:
            asyncio.run_coroutine_threadsafe(self._do_start(), self._server_loop)

    async def _do_start(self):
        if not self._game_started and self._lobby_clients:
            await self.start_game()

    # ── game setup ─────────────────────────────────────────────────────────────

    async def start_game(self):
        """Build the game, assign indices, and start the game loop."""
        async with self._lobby_lock:
            if self._game_started:
                return  # guard against double-start
            self._game_started = True

        human_names = [n for n, _ in self._lobby_clients]
        n_humans = len(human_names)

        # Fill remaining slots with bots up to MIN_PLAYERS
        all_names = list(human_names)
        bot_pool = iter(BOT_NAMES)
        while len(all_names) < MIN_PLAYERS:
            all_names.append(next(bot_pool))

        deck = _build_deck()
        players = _deal_players(all_names, deck)
        self._engine = GameEngine(players, deck)

        # Map each human writer to its player index
        for idx, (_, writer) in enumerate(self._lobby_clients):
            self._writer_to_index[writer] = idx
            self._human_queues[idx] = asyncio.Queue()
            self._human_writers[idx] = writer

        # Create bot agents for the padded slots
        for idx in range(n_humans, len(all_names)):
            self._bot_agents[idx] = BotAgent(all_names[idx])

        bots = all_names[n_humans:] if n_humans < len(all_names) else []
        print(f"[Server] Starting game!")
        print(f"  Humans : {human_names}")
        print(f"  Bots   : {bots}")

        # Wake up all waiting handle_client coroutines
        self._start_event.set()

        # Run the game
        await self._game_loop()


# ── server console input ──────────────────────────────────────────────────────

async def _console_loop(game_server: GameServer) -> None:
    """Reads stdin in a thread so the event loop stays unblocked."""
    loop = asyncio.get_event_loop()
    print(f"[Server] Waiting for players (1–{MAX_PLAYERS} humans, "
          f"min {MIN_PLAYERS} total with bots).")
    print("[Server] Type 's' + Enter to start the game.")
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        cmd = line.strip().lower()
        if cmd == 's':
            if game_server._game_started:
                print("[Server] Game already started.")
                break
            if not game_server._lobby_clients:
                print("[Server] No players in lobby yet — connect at least one client first.")
                continue
            await game_server.start_game()
            break


# ── in-process server helpers (for title-screen solo/host modes) ──────────────

async def _run_server_async(game_server: "GameServer") -> None:
    """Coroutine used by run_server_in_thread – no console loop."""
    game_server._server_loop = asyncio.get_running_loop()

    async def _handler(reader, writer):
        await game_server.handle_client(reader, writer)

    server = await asyncio.start_server(_handler, HOST, PORT)
    print(f"[Server] Coup server listening on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()


def run_server_in_thread(auto_start: bool = False) -> "GameServer":
    """Start the game server in a background daemon thread. Returns the GameServer."""
    gs = GameServer(auto_start=auto_start)

    def _thread():
        asyncio.run(_run_server_async(gs))

    t = threading.Thread(target=_thread, daemon=True)
    t.start()
    return gs


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    game_server = GameServer()

    async def _handler(reader, writer):
        await game_server.handle_client(reader, writer)

    server = await asyncio.start_server(_handler, HOST, PORT)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"[Server] Coup server listening on {addrs}")

    # Run console input concurrently with the server
    console_task = asyncio.create_task(_console_loop(game_server))

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
