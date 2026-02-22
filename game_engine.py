import random
from typing import Dict, List, Optional

from influences import Assassin, Duke, Captain, IncomeAction, ForeignAidAction, CoupAction
from game_agent import Player
from game_state import (
    PendingDecision, PlayerStateView, GameStateView,
    PhaseAction, PhaseDefense, PhaseChallenge, PhaseDoubtBlock,
    PhaseBlockOpen, PhaseLoseInfluence, PhaseReveal, RevealContext,
    DecisionType, DecisionResponse,
)

ALL_ACTIONS = [
    IncomeAction(),
    ForeignAidAction(),
    Assassin(),
    Duke(),
    Captain(),
    CoupAction(),
]

_MAX_LOG = 15   # maximum narrative entries kept in memory


class GameEngine:

    def __init__(self, players: List[Player], deck=None):
        self.players: List[Player] = players
        self._deck: Optional[list]= list(deck) if deck is not None else None
        self.current_turn: int = 0

        self.pending_decision: Optional[PendingDecision]= None

        self._phase_action: Optional[PhaseAction]= None
        self._phase_defense: Optional[PhaseDefense]= None
        self._phase_challenge: Optional[PhaseChallenge]= None
        self._phase_doubt_block: Optional[PhaseDoubtBlock]= None
        self._phase_block_open: Optional[PhaseBlockOpen]= None
        self._phase_lose_inf: Optional[PhaseLoseInfluence]= None
        self._phase_reveal: Optional[PhaseReveal]= None

        # Narrative event log (shown in UI event-log panel)
        self._event_log: List[str] = []
        # Last decision submitted — used by clients to spawn response bubbles
        self._last_action: Optional[dict] = None
        self._action_seq: int = 0

        self._emit_pending_decision()

    # ── logging helpers ───────────────────────────────────────────────────────

    def _log(self, text: str) -> None:
        """Print to server console AND append to the in-game event log."""
        print(text)
        self._event_log.append(text)
        if len(self._event_log) > _MAX_LOG:
            self._event_log.pop(0)

    def _set_last_action(self, player_idx: int, dt: str, choice: str,
                          bubble_text: str, **extra) -> None:
        """Record what was just decided so clients can play the right bubble."""
        self._action_seq += 1
        self._last_action = {
            'seq':           self._action_seq,
            'player_idx':    player_idx,
            'player_name':   self.players[player_idx].name,
            'decision_type': dt,
            'choice':        choice,
            'text':          bubble_text,
            **extra,
        }

    # ── turn helpers ──────────────────────────────────────────────────────────

    def _next_turn(self, from_id: int) -> int:
        """Next alive player from_id."""
        n = len(self.players)
        for k in range(1, n + 1):
            id = (from_id + k) % n
            if self.players[id].influences:
                return id
        return from_id

    def _alive_indices(self) -> List[int]:
        return [i for i, p in enumerate(self.players) if p.influences]

    def get_winner(self) -> Optional[str]:
        alive = self._alive_indices()
        return self.players[alive[0]].name if len(alive) == 1 else None

    def is_game_over(self) -> bool:
        return len(self._alive_indices()) <= 1

    def _emit_pending_decision(self):
        """Determina qual decisão é necessária agora e popula pending_decision."""
        if self.is_game_over():
            self.pending_decision = None
            return

        if not self.players[self.current_turn].influences:
            self.current_turn = self._next_turn(self.current_turn)

        if self._phase_reveal is not None:
            rv = self._phase_reveal
            self.pending_decision = PendingDecision(
                player_index=rv.challenged_player,
                decision_type=DecisionType.REVEAL,
                options=[DecisionResponse.REVEAL, DecisionResponse.REFUSE],
                context = {
                    'card_name':     rv.card_name,
                    'context':       rv.context,
                    'attacker_name': self.players[rv.attacker].name,
                    'attacker_idx':  rv.attacker,
                },
            )

        elif self._phase_lose_inf is not None:
            li = self._phase_lose_inf
            target = self.players[li.target_idx]
            self.pending_decision = PendingDecision(
                player_index=li.target_idx,
                decision_type=DecisionType.LOSE_INFLUENCE,
                options=list(range(len(target.influences))),
            )

        elif self._phase_challenge is not None:
            ch = self._phase_challenge
            self.pending_decision = PendingDecision(
                player_index=ch.queue[0],
                decision_type=DecisionType.CHALLENGE_ACTION,
                options=[DecisionResponse.DOUBT, DecisionResponse.PASS],
                context={
                    'action_name': ch.action.get_name(),
                    'actor_name':  self.players[ch.actor].name,
                    'actor_idx':   ch.actor,
                },
            )

        elif self._phase_doubt_block is not None:
            db = self._phase_doubt_block
            self.pending_decision = PendingDecision(
                player_index=db.queue[0],
                decision_type=DecisionType.CHALLENGE_BLOCK,
                options=[DecisionResponse.DOUBT, DecisionResponse.PASS],
                context={
                    'block_card':   db.action.get_block_name(),
                    'blocker_name': self.players[db.target].name,
                    'blocker_idx':  db.target,
                    'action_name':  db.action.get_name(),
                },
            )

        elif self._phase_block_open is not None:
            bo = self._phase_block_open
            self.pending_decision = PendingDecision(
                player_index=bo.queue[0],
                decision_type=DecisionType.BLOCK_OR_PASS,
                options=[DecisionResponse.BLOCK, DecisionResponse.PASS],
                context={
                    'action_name': bo.action.get_name(),
                    'block_card':  bo.action.get_block_name(),
                    'actor_name':  self.players[bo.actor].name,
                    'actor_idx':   bo.actor,
                },
            )

        elif self._phase_defense is not None:
            df = self._phase_defense
            self.pending_decision = PendingDecision(
                player_index=df.target_idx,
                decision_type=DecisionType.DEFEND,
                options=[DecisionResponse.BLOCK, DecisionResponse.DOUBT_ACTION, DecisionResponse.ACCEPT],
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
                decision_type=DecisionType.PICK_TARGET,
                options=targets,
                context={'action_name': self._phase_action.action.get_name()},
            )

        else:
            player = self.players[self.current_turn]
            if player.coins >= 10:
                available = [CoupAction()]
            else:
                available = [a for a in ALL_ACTIONS if a.can_use(player)]
            self.pending_decision = PendingDecision(
                player_index=self.current_turn,
                decision_type=DecisionType.PICK_ACTION,
                options=available,
            )

    def submit_decision(self, choice):
        assert self.pending_decision is not None
        dt  = self.pending_decision.decision_type
        pd  = self.pending_decision
        pidx = pd.player_index
        ctx  = pd.context

        # ── Derive the bubble text for this response ──────────────────────────
        choice_str = (choice.value       if hasattr(choice, 'value')    else
                      choice.get_name()  if hasattr(choice, 'get_name') else
                      str(choice))
        extra = {}

        if dt == DecisionType.PICK_ACTION:
            # Targeted / open actions announce via their follow-up states;
            # Income is detected by turn advancement. No post-decision bubble needed.
            bubble_text = ""

        elif dt == DecisionType.PICK_TARGET:
            # Already announced via PICK_TARGET pre-decision bubble; no duplicate.
            bubble_text = ""
            if isinstance(choice, int) and choice < len(self.players):
                extra['target_idx']  = choice
                extra['target_name'] = self.players[choice].name

        elif dt == DecisionType.DEFEND:
            if choice == DecisionResponse.BLOCK:
                # Next state (CHALLENGE_BLOCK) will show the block announcement.
                bubble_text = ""
            elif choice == DecisionResponse.DOUBT_ACTION:
                bubble_text = "Dúvida!"
            else:  # ACCEPT
                bubble_text = "Aceito"

        elif dt == DecisionType.CHALLENGE_ACTION:
            bubble_text = "Dúvida!" if choice == DecisionResponse.DOUBT else ""

        elif dt == DecisionType.CHALLENGE_BLOCK:
            bubble_text = "Dúvida!" if choice == DecisionResponse.DOUBT else ""

        elif dt == DecisionType.BLOCK_OR_PASS:
            # BLOCK is announced via the next CHALLENGE_BLOCK state; PASS is silent.
            bubble_text = ""

        elif dt == DecisionType.LOSE_INFLUENCE:
            player = self.players[pidx]
            card_name = (player.influences[choice].get_name()
                         if isinstance(choice, int) and choice < len(player.influences)
                         else '?')
            bubble_text = f"Perco {card_name}!"
            extra['card_name'] = card_name

        elif dt == DecisionType.REVEAL:
            card_name = ctx.get('card_name', '?')
            if choice == DecisionResponse.REVEAL:
                bubble_text = f"Tenho {card_name}!"
            else:
                bubble_text = "Recuso!"
            extra['card_name'] = card_name

        else:
            bubble_text = ""

        self._set_last_action(pidx, dt.value, choice_str, bubble_text, **extra)

        # ── Dispatch to the right handler ────────────────────────────────────
        self.pending_decision = None
        handlers = {
            DecisionType.PICK_ACTION:      self._on_pick_action,
            DecisionType.PICK_TARGET:      self._on_pick_target,
            DecisionType.DEFEND:           self._on_defend,
            DecisionType.CHALLENGE_ACTION: self._on_challenge_action,
            DecisionType.CHALLENGE_BLOCK:  self._on_challenge_block,
            DecisionType.BLOCK_OR_PASS:    self._on_block_or_pass,
            DecisionType.LOSE_INFLUENCE:   self._on_lose_influence,
            DecisionType.REVEAL:           self._on_reveal,
        }
        handlers[dt](choice)
        self._emit_pending_decision()

    def _on_pick_action(self, action):
        player = self.players[self.current_turn]

        if action.requires_target():
            # Seleção de alvo (Assassino, Capitão, Golpe)
            self._phase_action = PhaseAction(action=action)

        elif not action.is_challengeable():
            if action.is_open_blockable():
                # Ajuda Externa: qualquer jogador pode bloquear com Duque
                queue = [i for i in self._alive_indices() if i != self.current_turn]
                self._log(f"{player.name} anuncia: {action.get_name()}!")
                self._phase_block_open = PhaseBlockOpen(
                    actor=self.current_turn,
                    action=action,
                    queue=queue,
                )
            else:
                # Renda: executa imediatamente, sem fase de desafio
                action.apply(player)
                self._log(f"{player.name}: {action.get_name()} (+1 moeda).")
                self.current_turn = self._next_turn(self.current_turn)

        else:
            # Ação de carta (Duque, etc.): outros podem duvidar
            queue = [i for i in self._alive_indices() if i != self.current_turn]
            self._log(f"{player.name} anuncia: {action.get_name()}!")
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
            self._log(f"{player.name} dá um Golpe em {target.name}!")
            self._lose_one_or_choose(target_idx, next_turn)
        elif action.has_defense():
            action.apply_cost(player)
            self._log(f"{player.name} usa {action.get_name()} em {target.name} — aguardando defesa.")
            self._phase_defense = PhaseDefense(target_idx=target_idx, action=action)
        else:
            action.apply(player, target)
            self._log(f"{player.name} usou {action.get_name()} em {target.name}.")
            self.current_turn = next_turn

    def _on_defend(self, choice: DecisionResponse):
        assert self._phase_defense is not None
        df        = self._phase_defense
        target_idx = df.target_idx
        action     = df.action
        player    = self.players[self.current_turn]  # atacante
        target    = self.players[target_idx]
        next_turn = self._next_turn(self.current_turn)
        self._phase_defense = None

        if choice == DecisionResponse.BLOCK:
            self._log(f"{target.name} tenta bloquear {action.get_name()} de {player.name}!")
            self._phase_doubt_block = PhaseDoubtBlock(
                attacker=self.current_turn,
                target=target_idx,
                action=action,
                queue=[self.current_turn],  # só o atacante pode duvidar do bloqueio
            )

        elif choice == DecisionResponse.DOUBT_ACTION:
            action_card = action.get_name()
            has_card    = any(inf.get_name() == action_card for inf in player.influences)
            self._log(f"{target.name} desafia {player.name} a provar que tem {action_card}!")
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
                self._log(f"{player.name} não tem {action_card}. Ação cancelada.")
                self._lose_one_or_choose(self.current_turn, next_turn)

        else:  # ACCEPT
            self._log(f"{target.name} aceitou. {player.name} executa {action.get_name()} em {target.name}!")
            if action.causes_influence_loss():
                self._lose_one_or_choose(target_idx, next_turn)
            else:
                action.apply_effect(player, target)
                self.current_turn = next_turn

    def _on_challenge_action(self, choice: DecisionResponse):
        assert self._phase_challenge is not None
        ch          = self._phase_challenge
        actor_idx   = ch.actor
        ac_action   = ch.action
        queue       = ch.queue
        actor       = self.players[actor_idx]
        doubter_idx = queue[0]
        doubter     = self.players[doubter_idx]
        next_turn   = self._next_turn(actor_idx)

        if choice == DecisionResponse.DOUBT:
            card_name = ac_action.get_name()
            has_card  = any(inf.get_name() == card_name for inf in actor.influences)
            self._log(f"{doubter.name} desafia {actor.name} a provar que tem {card_name}!")
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
                self._log(f"{actor.name} não tem {card_name}. Ação cancelada.")
                self._lose_one_or_choose(actor_idx, next_turn)

        elif choice == DecisionResponse.PASS:
            queue.pop(0)
            if not queue:
                ac_action.apply(actor)
                self._log(f"{actor.name} usou {ac_action.get_name()} — {ac_action.get_description()}")
                self._phase_challenge = None
                self.current_turn = next_turn

    def _on_challenge_block(self, choice: DecisionResponse):
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

        if choice == DecisionResponse.DOUBT:
            block_card = d_action.get_block_name()
            has_card   = any(inf.get_name() == block_card for inf in target.influences)
            self._log(f"{doubter.name} desafia {target.name} a provar que tem {block_card}!")
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
                self._log(f"{target.name} não tem {block_card}. Bloqueio falhou. Ação executada.")
                if not d_action.causes_influence_loss():
                    d_action.apply_effect(player, target)
                # Bloqueio falso: bloqueador perde uma carta (além do efeito da ação)
                self._lose_one_or_choose(target_idx, next_turn)

        elif choice == DecisionResponse.PASS:
            queue.pop(0)
            if not queue:
                self._log(f"Ninguém duvidou. Bloqueio de {target.name} aceito.")
                self._phase_doubt_block = None
                self.current_turn = next_turn

    def _on_block_or_pass(self, choice: DecisionResponse):
        assert self._phase_block_open is not None
        bo          = self._phase_block_open
        actor_idx   = bo.actor
        action      = bo.action
        queue       = bo.queue
        blocker_idx = queue[0]
        blocker     = self.players[blocker_idx]
        next_turn   = self._next_turn(actor_idx)

        if choice == DecisionResponse.BLOCK:
            self._log(f"{blocker.name} bloqueia {action.get_name()} com {action.get_block_name()}!")
            self._phase_block_open = None
            # Só o ator pode duvidar do bloqueio
            self._phase_doubt_block = PhaseDoubtBlock(
                attacker=actor_idx,
                target=blocker_idx,
                action=action,
                queue=[actor_idx],
            )
        elif choice == DecisionResponse.PASS:
            queue.pop(0)
            if not queue:
                actor = self.players[actor_idx]
                action.apply(actor)
                self._log(f"Ninguém bloqueou. {actor.name} usa {action.get_name()} (+2 moedas).")
                self._phase_block_open = None
                self.current_turn = next_turn

    def _on_lose_influence(self, card_idx: int):
        assert self._phase_lose_inf is not None
        li        = self._phase_lose_inf
        target    = self.players[li.target_idx]
        next_turn = li.next_turn
        lost      = target.influences.pop(card_idx)
        target.revealed_influences.append(lost)
        self._log(f"{target.name} perdeu: {lost.get_name()}")
        if not target.influences:
            self._log(f"{target.name} foi eliminado!")
        self._phase_lose_inf = None
        self.current_turn = next_turn

    def _on_reveal(self, choice: DecisionResponse):
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

        has_card = (choice == DecisionResponse.REVEAL and
                    any(inf.get_name() == card_name for inf in challenged.influences))

        # Sucesso: devolve a carta ao baralho e compra outra (regra padrão do Coup)
        if has_card and self._deck is not None:
            card = next(inf for inf in challenged.influences if inf.get_name() == card_name)
            challenged.influences.remove(card)
            self._deck.append(card)
            random.shuffle(self._deck)
            challenged.influences.append(self._deck.pop())

        if ctx == RevealContext.DOUBT_ACTION:
            # Alvo duvidou da ação do atacante
            if has_card:
                self._log(f"{challenged.name} revelou {card_name}! Desafio falhou — ação executada. {target.name} perde influência.")
                # apply_effect é no-op para ações destrutivas (Assassino); roubo acontece aqui
                action.apply_effect(attacker, target)
                # Desafiante (alvo) falhou no desafio → perde uma carta
                self._lose_one_or_choose(target_idx, next_turn)
            else:
                msg = "não tinha" if choice == DecisionResponse.REVEAL else "recusou revelar"
                self._log(f"{challenged.name} {msg} {card_name}. Ação cancelada. {challenged.name} perde influência.")
                self._lose_one_or_choose(attacker_idx, next_turn)

        elif ctx == RevealContext.DOUBT_BLOCK:
            # Atacante duvidou do bloqueio
            assert doubter_idx is not None
            doubter = self.players[doubter_idx]
            if has_card:
                self._log(f"{challenged.name} revelou {card_name}! Bloqueio mantido. {doubter.name} perde influência.")
                self._lose_one_or_choose(doubter_idx, next_turn)
            else:
                msg = "não tinha" if choice == DecisionResponse.REVEAL else "recusou revelar"
                self._log(f"{challenged.name} {msg} {card_name}. Bloqueio falhou — ação executada. {challenged.name} perde influência.")
                if not action.causes_influence_loss():
                    action.apply_effect(attacker, challenged)
                # Bloqueio falso: bloqueador perde uma carta (além do efeito da ação)
                self._lose_one_or_choose(target_idx, next_turn)

        elif ctx == RevealContext.DOUBT_OPEN:
            # Outro jogador duvidou de ação não-alvo (ex: Duque)
            assert doubter_idx is not None
            doubter = self.players[doubter_idx]
            if has_card:
                self._log(f"{challenged.name} revelou {card_name}! Desafio falhou — ação executada. {doubter.name} perde influência.")
                action.apply(challenged)
                self._log(f"{challenged.name} usou {action.get_name()} — {action.get_description()}")
                self._lose_one_or_choose(doubter_idx, next_turn)
            else:
                msg = "não tinha" if choice == DecisionResponse.REVEAL else "recusou revelar"
                self._log(f"{challenged.name} {msg} {card_name}. Ação cancelada. {challenged.name} perde influência.")
                self._lose_one_or_choose(attacker_idx, next_turn)

    def _lose_one_or_choose(self, player_idx: int, next_turn: int):
        """Com 1 carta: elimina automaticamente. Com 2: pede escolha."""
        player = self.players[player_idx]
        if len(player.influences) <= 1:
            if player.influences:
                lost = player.influences.pop(0)
                player.revealed_influences.append(lost)
                self._log(f"{player.name} perdeu: {lost.get_name()}")
            if not player.influences:
                self._log(f"{player.name} foi eliminado!")
            self.current_turn = next_turn
        else:
            self._phase_lose_inf = PhaseLoseInfluence(
                target_idx=player_idx,
                next_turn=next_turn,
            )

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

        # Count every copy of each card type across deck + all player hands + all revealed.
        cards_per_type: Dict[str, int] = {}
        all_cards = list(self._deck or [])
        for p in self.players:
            all_cards.extend(p.influences)
            all_cards.extend(p.revealed_influences)
        for card in all_cards:
            name = card.get_name()
            cards_per_type[name] = cards_per_type.get(name, 0) + 1

        return GameStateView(
            players=player_views,
            current_turn=self.current_turn,
            pending_decision=self.pending_decision,
            viewer_index=viewer_index,
            cards_per_type=cards_per_type,
            event_log=list(self._event_log),
            last_action=self._last_action,
        )
