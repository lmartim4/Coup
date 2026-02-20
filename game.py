"""
Orquestrador do jogo local: 1 humano ("Eu") + 1 bot aleatório.

Responsabilidades:
  - Inicializar pygame e o engine
  - A cada frame, checar se a decisão pendente é do bot → decidir imediatamente
  - Renderizar o estado do ponto de vista do jogador humano
  - Rotear cliques do mouse para engine.submit_decision()
"""
import pygame
import random
from influences import Assassin, Duke, Countess, Captain
from player import Player
from game_engine import GameEngine
from bot_agent import BotAgent
from renderer import Renderer


class Game:

    HUMAN_IDX = 0   # índice do jogador humano (sempre o primeiro)

    def __init__(self):
        pygame.init()
        screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption("Coup")
        self.screen   = screen
        self.clock    = pygame.time.Clock()
        self.font     = pygame.font.SysFont(None, 22)
        self.renderer = Renderer(screen, self.font)

        deck    = self._build_deck()
        players = self._deal_players(["Eu", "Diego", "Contente", "Lucas"], deck)

        self.engine      = GameEngine(players)
        self.bot_agents  = {1: BotAgent("Diego"),2: BotAgent("Contente"),3: BotAgent("Lucas")}  # índice → agente

        # Rects clicáveis do último frame: [(pygame.Rect, choice)]
        self._clickable: list = []

    # ------------------------------------------------------------------ setup

    @staticmethod
    def _build_deck():
        deck = (
            [Assassin()] * 3 +
            [Duke()]     * 3 +
            [Countess()] * 3 +
            [Captain()]  * 3
        )
        random.shuffle(deck)
        return deck

    @staticmethod
    def _deal_players(names: list[str], deck: list) -> list[Player]:
        players = []
        for name in names:
            influences = [deck.pop(), deck.pop()]
            players.append(Player(name, influences))
        return players

    # ------------------------------------------------------------------ loop

    def run(self):
        running = True
        while running:
            mouse_pos = pygame.mouse.get_pos()

            # Eventos
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            # Decisões automáticas dos bots
            self._tick_bots()

            # Renderiza do ponto de vista do humano
            self.renderer.clear()
            state_view      = self.engine.get_state_view(self.HUMAN_IDX)
            self._clickable = self.renderer.draw(state_view, mouse_pos)
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    # ------------------------------------------------------------------ bot tick

    def _tick_bots(self):
        """Se a decisão pendente é de um bot, resolve imediatamente."""
        decision = self.engine.pending_decision
        if decision is None:
            return
        agent = self.bot_agents.get(decision.player_index)
        if agent is None:
            return  # decisão é do humano
        state_view = self.engine.get_state_view(decision.player_index)
        choice = agent.decide(state_view, decision)
        player_name = self.engine.players[decision.player_index].name
        print(f"[{player_name}] {decision.decision_type} → {choice}")
        self.engine.submit_decision(choice)

    # ------------------------------------------------------------------ click

    def _handle_click(self, pos: tuple):
        decision = self.engine.pending_decision
        if decision is None or decision.player_index != self.HUMAN_IDX:
            return
        for rect, choice in self._clickable:
            if rect.collidepoint(pos):
                print(f"[Eu] {decision.decision_type} → {choice}")
                self.engine.submit_decision(choice)
                break
