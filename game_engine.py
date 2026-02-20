"""
GameEngine: lógica pura do Coup, sem pygame.

O engine expõe um único PendingDecision por vez. O orquestrador (game.py)
consulta engine.pending_decision, roteia para o agente correto e chama
engine.submit_decision(choice) para avançar o jogo.
"""
from influences import Assassin, Duke, Countess, Captain, IncomeAction, ForeignAidAction, CoupAction
from player import Player
from game_state import (
    PendingDecision, PlayerStateView, GameStateView,
    PhaseAction, PhaseDefense, PhaseChallenge, PhaseDoubtBlock,
    PhaseBlockOpen, PhaseLoseInfluence, PhaseReveal, RevealContext,
)

ALL_ACTIONS = [
    IncomeAction(),
    ForeignAidAction(),
    Assassin(),
    Duke(),
    Captain(),
    CoupAction(),
]


class GameEngine:

    def __init__(self, players: list[Player]):
        self.players: list[Player] = players
        self.current_turn: int = 0
        self.pending_decision: PendingDecision | None = None

        # Fases internas (substituem os pending_* do game.py original).
        # Apenas uma fase pode estar ativa por vez; todas as outras são None.
        self._phase_action:      PhaseAction        | None = None
        self._phase_defense:     PhaseDefense       | None = None
        self._phase_challenge:   PhaseChallenge     | None = None
        self._phase_doubt_block: PhaseDoubtBlock    | None = None
        self._phase_block_open:  PhaseBlockOpen     | None = None
        self._phase_lose_inf:    PhaseLoseInfluence | None = None
        self._phase_reveal:      PhaseReveal        | None = None

        self._emit_decision()

    # ------------------------------------------------------------------ helpers

    def _next_turn(self, from_idx: int) -> int:
        """Próximo jogador vivo depois de from_idx."""
        n = len(self.players)
        for k in range(1, n + 1):
            idx = (from_idx + k) % n
            if self.players[idx].influences:
                return idx
        return from_idx  # só acontece se todos eliminados

    def _alive_indices(self) -> list[int]:
        return [i for i, p in enumerate(self.players) if p.influences]

    # ------------------------------------------------------------------ emit

    def _emit_decision(self):
        """Determina qual decisão é necessária agora e popula pending_decision."""
        if self.is_game_over():
            self.pending_decision = None
            return

        # Garante que current_turn aponte para um jogador vivo
        if not self.players[self.current_turn].influences:
            self.current_turn = self._next_turn(self.current_turn)

        # Prioridade idêntica à do _handle_click original
        if self._phase_reveal is not None:
            rv = self._phase_reveal
            self.pending_decision = PendingDecision(
                player_index=rv.challenged_player,
                decision_type='reveal',
                options=['reveal', 'refuse'],
                context={
                    'card_name':     rv.card_name,
                    'context':       rv.context,
                    'attacker_name': self.players[rv.attacker].name,
                },
            )

        elif self._phase_lose_inf is not None:
            li = self._phase_lose_inf
            target = self.players[li.target_idx]
            self.pending_decision = PendingDecision(
                player_index=li.target_idx,
                decision_type='lose_influence',
                options=list(range(len(target.influences))),
            )

        elif self._phase_challenge is not None:
            ch = self._phase_challenge
            self.pending_decision = PendingDecision(
                player_index=ch.queue[0],
                decision_type='challenge_action',
                options=['doubt', 'pass'],
                context={
                    'action_name': ch.action.get_name(),
                    'actor_name':  self.players[ch.actor].name,
                },
            )

        elif self._phase_doubt_block is not None:
            db = self._phase_doubt_block
            self.pending_decision = PendingDecision(
                player_index=db.queue[0],
                decision_type='challenge_block',
                options=['doubt', 'pass'],
                context={
                    'block_card':   db.action.get_block_name(),
                    'blocker_name': self.players[db.target].name,
                    'action_name':  db.action.get_name(),
                },
            )

        elif self._phase_block_open is not None:
            bo = self._phase_block_open
            self.pending_decision = PendingDecision(
                player_index=bo.queue[0],
                decision_type='block_or_pass',
                options=['block', 'pass'],
                context={
                    'action_name': bo.action.get_name(),
                    'block_card':  bo.action.get_block_name(),
                    'actor_name':  self.players[bo.actor].name,
                },
            )

        elif self._phase_defense is not None:
            df = self._phase_defense
            self.pending_decision = PendingDecision(
                player_index=df.target_idx,
                decision_type='defend',
                options=['block', 'doubt_action', 'accept'],
                context={
                    'action_name':   df.action.get_name(),
                    'block_card':    df.action.get_block_name(),
                    'attacker_name': self.players[self.current_turn].name,
                    'attacker_idx':  self.current_turn,
                },
            )

        elif self._phase_action is not None:
            targets = [i for i in self._alive_indices() if i != self.current_turn]
            self.pending_decision = PendingDecision(
                player_index=self.current_turn,
                decision_type='pick_target',
                options=targets,
                context={'action_name': self._phase_action.action.get_name()},
            )

        else:
            # Turno normal: jogador ativo escolhe ação
            player = self.players[self.current_turn]
            if player.coins >= 10:
                # Com 10+ moedas o Golpe é obrigatório
                available = [a for a in ALL_ACTIONS if a.get_name() == 'Golpe']
            else:
                available = [a for a in ALL_ACTIONS if a.can_use(player)]
            self.pending_decision = PendingDecision(
                player_index=self.current_turn,
                decision_type='pick_action',
                options=[a.get_name() for a in available],
            )

    # ------------------------------------------------------------------ submit

    def submit_decision(self, choice):
        assert self.pending_decision is not None
        dt = self.pending_decision.decision_type
        self.pending_decision = None

        handlers = {
            'pick_action':      self._on_pick_action,
            'pick_target':      self._on_pick_target,
            'defend':           self._on_defend,
            'challenge_action': self._on_challenge_action,
            'challenge_block':  self._on_challenge_block,
            'block_or_pass':    self._on_block_or_pass,
            'lose_influence':   self._on_lose_influence,
            'reveal':           self._on_reveal,
        }
        handlers[dt](choice)
        self._emit_decision()

    # ------------------------------------------------------------------ handlers

    def _on_pick_action(self, action_name: str):
        action = next(a for a in ALL_ACTIONS if a.get_name() == action_name)
        player = self.players[self.current_turn]

        if action.requires_target():
            # Seleção de alvo (Assassino, Capitão, Golpe)
            self._phase_action = PhaseAction(action=action)

        elif not action.is_challengeable():
            if action.is_open_blockable():
                # Ajuda Externa: qualquer jogador pode bloquear com Duque
                queue = [i for i in self._alive_indices() if i != self.current_turn]
                print(f"{player.name} anuncia: {action.get_name()}!")
                self._phase_block_open = PhaseBlockOpen(
                    actor=self.current_turn,
                    action=action,
                    queue=queue,
                )
            else:
                # Renda: executa imediatamente, sem fase de desafio
                action.apply(player)
                print(f"{player.name}: {action.get_name()} (+1 moeda).")
                self.current_turn = self._next_turn(self.current_turn)

        else:
            # Ação de carta (Duque, etc.): outros podem duvidar
            queue = [i for i in self._alive_indices() if i != self.current_turn]
            print(f"{player.name} anuncia: {action.get_name()}!")
            self._phase_challenge = PhaseChallenge(
                actor=self.current_turn,
                action=action,
                queue=queue,
            )

    def _on_pick_target(self, target_idx: int):
        assert self._phase_action is not None
        action = self._phase_action.action
        player = self.players[self.current_turn]
        target = self.players[target_idx]
        self._phase_action = None
        next_turn = self._next_turn(self.current_turn)

        if not action.is_challengeable():
            # Golpe: executa direto (sem defesa, sem desafio)
            action.apply_cost(player)
            print(f"{player.name} dá um Golpe em {target.name}!")
            self._lose_one_or_choose(target_idx, next_turn)
        elif action.has_defense():
            action.apply_cost(player)
            self._phase_defense = PhaseDefense(target_idx=target_idx, action=action)
        else:
            action.apply(player, target)
            print(f"{player.name} usou {action.get_name()} em {target.name}.")
            self.current_turn = next_turn

    def _on_defend(self, choice: str):
        assert self._phase_defense is not None
        df        = self._phase_defense
        target_idx = df.target_idx
        action     = df.action
        player    = self.players[self.current_turn]  # atacante
        target    = self.players[target_idx]
        next_turn = self._next_turn(self.current_turn)
        self._phase_defense = None

        if choice == 'block':
            self._phase_doubt_block = PhaseDoubtBlock(
                attacker=self.current_turn,
                target=target_idx,
                action=action,
                queue=[self.current_turn],  # só o atacante pode duvidar do bloqueio
            )

        elif choice == 'doubt_action':
            action_card = action.get_name()
            has_card    = any(inf.get_name() == action_card for inf in player.influences)
            print(f"{target.name} desafia {player.name} a provar que tem {action_card}!")
            if has_card:
                self._phase_reveal = PhaseReveal(
                    challenged_player=self.current_turn,
                    card_name=action_card,
                    context=RevealContext.DOUBT_ACTION,
                    attacker=self.current_turn,
                    target=target_idx,
                    action=action,
                    next_turn=next_turn,
                )
            else:
                print(f"{player.name} não tem {action_card}. Ação cancelada.")
                self._lose_one_or_choose(self.current_turn, next_turn)

        else:  # accept
            print(f"{target.name} aceitou. {player.name} executa {action.get_name()} em {target.name}!")
            if action.causes_influence_loss():
                self._lose_one_or_choose(target_idx, next_turn)
            else:
                action.apply_effect(player, target)
                self.current_turn = next_turn

    def _on_challenge_action(self, choice: str):
        assert self._phase_challenge is not None
        ch          = self._phase_challenge
        actor_idx   = ch.actor
        ac_action   = ch.action
        queue       = ch.queue
        actor       = self.players[actor_idx]
        doubter_idx = queue[0]
        doubter     = self.players[doubter_idx]
        next_turn   = self._next_turn(actor_idx)

        if choice == 'doubt':
            card_name = ac_action.get_name()
            has_card  = any(inf.get_name() == card_name for inf in actor.influences)
            print(f"{doubter.name} desafia {actor.name} a provar que tem {card_name}!")
            self._phase_challenge = None
            if has_card:
                self._phase_reveal = PhaseReveal(
                    challenged_player=actor_idx,
                    card_name=card_name,
                    context=RevealContext.DOUBT_OPEN,
                    attacker=actor_idx,
                    target=actor_idx,
                    action=ac_action,
                    next_turn=next_turn,
                    doubter=doubter_idx,
                )
            else:
                print(f"{actor.name} não tem {card_name}. Ação cancelada.")
                self._lose_one_or_choose(actor_idx, next_turn)

        elif choice == 'pass':
            queue.pop(0)
            if not queue:
                ac_action.apply(actor)
                print(f"{actor.name} usou {ac_action.get_name()} — {ac_action.get_description()}")
                self._phase_challenge = None
                self.current_turn = next_turn

    def _on_challenge_block(self, choice: str):
        assert self._phase_doubt_block is not None
        db          = self._phase_doubt_block
        queue       = db.queue
        attacker    = db.attacker
        target_idx  = db.target
        d_action    = db.action
        doubter_idx = queue[0]
        doubter     = self.players[doubter_idx]
        target      = self.players[target_idx]
        player      = self.players[attacker]
        next_turn   = self._next_turn(attacker)

        if choice == 'doubt':
            block_card = d_action.get_block_name()
            has_card   = any(inf.get_name() == block_card for inf in target.influences)
            print(f"{doubter.name} desafia {target.name} a provar que tem {block_card}!")
            self._phase_doubt_block = None
            if has_card:
                self._phase_reveal = PhaseReveal(
                    challenged_player=target_idx,
                    card_name=block_card,
                    context=RevealContext.DOUBT_BLOCK,
                    attacker=attacker,
                    target=target_idx,
                    action=d_action,
                    next_turn=next_turn,
                    doubter=doubter_idx,
                )
            else:
                print(f"{target.name} não tem {block_card}. Bloqueio falhou. Ação executada.")
                if not d_action.causes_influence_loss():
                    d_action.apply_effect(player, target)
                # Bloqueio falso: bloqueador perde uma carta (além do efeito da ação)
                self._lose_one_or_choose(target_idx, next_turn)

        elif choice == 'pass':
            queue.pop(0)
            if not queue:
                print(f"Ninguém duvidou. Bloqueio de {target.name} aceito.")
                self._phase_doubt_block = None
                self.current_turn = next_turn

    def _on_block_or_pass(self, choice: str):
        assert self._phase_block_open is not None
        bo          = self._phase_block_open
        actor_idx   = bo.actor
        action      = bo.action
        queue       = bo.queue
        blocker_idx = queue[0]
        blocker     = self.players[blocker_idx]
        next_turn   = self._next_turn(actor_idx)

        if choice == 'block':
            print(f"{blocker.name} bloqueia {action.get_name()} com {action.get_block_name()}!")
            self._phase_block_open = None
            # Só o ator pode duvidar do bloqueio
            self._phase_doubt_block = PhaseDoubtBlock(
                attacker=actor_idx,
                target=blocker_idx,
                action=action,
                queue=[actor_idx],
            )
        else:  # pass
            queue.pop(0)
            if not queue:
                actor = self.players[actor_idx]
                action.apply(actor)
                print(f"Ninguém bloqueou. {actor.name} usa {action.get_name()} (+2 moedas).")
                self._phase_block_open = None
                self.current_turn = next_turn

    def _on_lose_influence(self, card_idx: int):
        assert self._phase_lose_inf is not None
        li        = self._phase_lose_inf
        target    = self.players[li.target_idx]
        next_turn = li.next_turn
        lost      = target.influences.pop(card_idx)
        target.revealed_influences.append(lost)
        print(f"{target.name} perdeu: {lost.get_name()}")
        if not target.influences:
            print(f"{target.name} foi eliminado!")
        self._phase_lose_inf = None
        self.current_turn = next_turn

    def _on_reveal(self, choice: str):
        assert self._phase_reveal is not None
        rv           = self._phase_reveal
        ctx          = rv.context
        challenged   = self.players[rv.challenged_player]
        card_name    = rv.card_name
        attacker     = self.players[rv.attacker]
        target       = self.players[rv.target]
        action       = rv.action
        next_turn    = rv.next_turn
        attacker_idx = rv.attacker
        target_idx   = rv.target
        doubter_idx  = rv.doubter  # None only for DOUBT_ACTION (not used in that branch)
        self._phase_reveal = None

        has_card = (choice == 'reveal' and
                    any(inf.get_name() == card_name for inf in challenged.influences))

        if ctx == RevealContext.DOUBT_ACTION:
            # Alvo duvidou da ação do atacante
            if has_card:
                print(f"{challenged.name} revelou {card_name}! Desafio falhou. Ação executada.")
                if action.causes_influence_loss():
                    self._lose_one_or_choose(target_idx, next_turn)
                else:
                    action.apply_effect(attacker, target)
                    self.current_turn = next_turn
            else:
                msg = "não tinha" if choice == 'reveal' else "recusou revelar."
                print(f"{challenged.name} {msg} {card_name}. Ação cancelada.")
                self._lose_one_or_choose(attacker_idx, next_turn)

        elif ctx == RevealContext.DOUBT_BLOCK:
            # Atacante duvidou do bloqueio
            assert doubter_idx is not None
            doubter = self.players[doubter_idx]
            if has_card:
                print(f"{challenged.name} revelou {card_name}! Bloqueio mantido. {doubter.name} perde uma carta.")
                self._lose_one_or_choose(doubter_idx, next_turn)
            else:
                msg = "não tinha" if choice == 'reveal' else "recusou revelar."
                print(f"{challenged.name} {msg} {card_name}. Bloqueio falhou. Ação executada.")
                if not action.causes_influence_loss():
                    action.apply_effect(attacker, challenged)
                # Bloqueio falso: bloqueador perde uma carta (além do efeito da ação)
                self._lose_one_or_choose(target_idx, next_turn)

        elif ctx == RevealContext.DOUBT_OPEN:
            # Outro jogador duvidou de ação não-alvo (ex: Duque)
            assert doubter_idx is not None
            doubter = self.players[doubter_idx]
            if has_card:
                print(f"{challenged.name} revelou {card_name}! Desafio falhou. Ação executada.")
                action.apply(challenged)
                print(f"{challenged.name} usou {action.get_name()} — {action.get_description()}")
                self._lose_one_or_choose(doubter_idx, next_turn)
            else:
                msg = "não tinha" if choice == 'reveal' else "recusou revelar."
                print(f"{challenged.name} {msg} {card_name}. Ação cancelada.")
                self._lose_one_or_choose(attacker_idx, next_turn)

    # ------------------------------------------------------------------ util

    def _lose_one_or_choose(self, player_idx: int, next_turn: int):
        """Com 1 carta: elimina automaticamente. Com 2: pede escolha."""
        player = self.players[player_idx]
        if len(player.influences) <= 1:
            if player.influences:
                lost = player.influences.pop(0)
                player.revealed_influences.append(lost)
                print(f"{player.name} perdeu: {lost.get_name()}")
            if not player.influences:
                print(f"{player.name} foi eliminado!")
            self.current_turn = next_turn
        else:
            self._phase_lose_inf = PhaseLoseInfluence(
                target_idx=player_idx,
                next_turn=next_turn,
            )

    # ------------------------------------------------------------------ view

    def get_state_view(self, viewer_index: int) -> GameStateView:
        """Serializa o estado do jogo para um jogador específico."""
        player_views = []
        for i, p in enumerate(self.players):
            # Cartas só são visíveis para o próprio jogador
            influences = [inf.get_name() for inf in p.influences] if i == viewer_index else []
            player_views.append(PlayerStateView(
                index=i,
                name=p.name,
                coins=p.coins,
                influence_count=len(p.influences),
                influences=influences,
                revealed_influences=[inf.get_name() for inf in p.revealed_influences],
                is_eliminated=(len(p.influences) == 0),
            ))
        return GameStateView(
            players=player_views,
            current_turn=self.current_turn,
            pending_decision=self.pending_decision,
            viewer_index=viewer_index,
        )

    # ------------------------------------------------------------------ state

    def is_game_over(self) -> bool:
        return len(self._alive_indices()) <= 1

    def get_winner(self) -> str | None:
        alive = self._alive_indices()
        return self.players[alive[0]].name if len(alive) == 1 else None
