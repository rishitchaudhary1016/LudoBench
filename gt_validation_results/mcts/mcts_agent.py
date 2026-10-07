"""
Independent Monte Carlo Tree Search (MCTS) agent for LudoBench spot evaluation.

Location : <repo root>/validation/mcts/mcts_agent.py
Interface: MCTSAgent.select_move(env, player, dice, legal_moves) -> token index
           (identical to GameTheoryAgent / GameTheoryMultiplayerAgent / HeuristicAgent)

Design summary
--------------
* Rules come from the unmodified ludo_env.LudoEnv: LudoEnv.get_legal_moves and
  LudoEnv.apply_move are reused as-is on a lightweight simulation subclass
  (_SimEnv) that has no log files and does not touch the global `random` state.
* Standard UCT-MCTS: selection (UCB1) -> expansion (one new node) ->
  simulation (uniform-random rollout to game end) -> backpropagation.
* Dice are chance events. The tree is "chance-sampled": every decision node is
  keyed by (parent move, sampled dice value), so repeated visits through the
  same dice outcome share statistics. No evaluator, no hand-tuned weights, no
  search-depth limit: the only knowledge is the game rules + random playouts.
* Multiplayer (2-4 players): each node's mover maximises its OWN win rate
  (max^n style). A rollout returns a reward vector (winner = 1, others = 0).
* Pieces on the same square are interchangeable; they are merged into one
  candidate and the LOWEST token index is returned (same tie convention as GT).
"""

import math
import os
import random
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents import BaseAgent          # noqa: E402
from ludo_env import LudoEnv          # noqa: E402


# --------------------------------------------------------------------------- #
# Simulation environment (reuses LudoEnv rules, no side effects)
# --------------------------------------------------------------------------- #
class _NullFile:
    def write(self, *_a, **_k):
        pass

    def flush(self):
        pass


class _NullList:
    def append(self, _x):
        pass


class _SimEnv(LudoEnv):
    """LudoEnv rules without LudoEnv.__init__ side effects (log files, global seeding)."""

    def __init__(self, src_env):
        self.player_ids = list(src_env.player_ids)
        self.NUM_PLAYERS = len(self.player_ids)
        self.TOKENS_PER_PLAYER = getattr(src_env, "TOKENS_PER_PLAYER", 4)
        self.BOARD_SIZE = src_env.BOARD_SIZE
        self.HOME_START = src_env.HOME_START
        self.HOME_LEN = src_env.HOME_LEN
        self.START_POSITIONS = dict(src_env.START_POSITIONS)
        self.SAFE_SQUARES = set(src_env.SAFE_SQUARES)
        self.log_file = _NullFile()
        self.llm_log_file = _NullFile()
        self.player_logs = {pid: _NullFile() for pid in self.player_ids}
        self.move_counts = {pid: 0 for pid in self.player_ids}
        self.move_log = _NullList()
        self.tokens = {}
        self.current_player_idx = 0
        self.game_over = False
        self.winner = None

    def reset_to(self, tokens):
        self.tokens = {pid: list(tokens[pid]) for pid in self.player_ids}
        self.game_over = False
        self.winner = None


# --------------------------------------------------------------------------- #
# Tree node
# --------------------------------------------------------------------------- #
class _Node:
    """Decision node: `mover` must choose among `moves` given a fixed `dice`."""
    __slots__ = ("mover", "moves", "N", "W", "visits", "children")

    def __init__(self, mover, moves):
        self.mover = mover
        self.moves = moves                      # candidate token indices
        self.N = {m: 0 for m in moves}          # edge visit counts
        self.W = {m: 0.0 for m in moves}        # edge total reward for `mover`
        self.visits = 0
        self.children = {}                      # (move, next_dice) -> _Node


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class MCTSAgent(BaseAgent):
    """
    Args:
        num_rollouts:      MCTS iterations (= random rollouts) per decision.
        exploration_c:     UCB1 exploration constant (sqrt(2) is the textbook value).
        max_rollout_steps: safety cap on plies per rollout. If hit, the reward goes
                           to the player with most board progress (ties split).
        seed:              base seed. Each decision re-seeds from (seed, state), so
                           results do not depend on call order.
        merge_equivalent_moves: merge moves of tokens that sit on the same square.
    """

    def __init__(self, num_rollouts=1000, exploration_c=math.sqrt(2.0),
                 max_rollout_steps=400, seed=0, merge_equivalent_moves=True):
        self.num_rollouts = max(1, int(num_rollouts))
        self.exploration_c = float(exploration_c)
        self.max_rollout_steps = max(1, int(max_rollout_steps))
        self.seed = seed
        self.merge_equivalent_moves = merge_equivalent_moves
        self.last_search_info = None            # diagnostics of the latest decision

    # ---- public interface -------------------------------------------------- #
    def select_move(self, env, player, dice, legal_moves):
        legal_moves = list(legal_moves)
        if len(legal_moves) == 1:
            self.last_search_info = {"root_moves": legal_moves, "visits": {}, "win_rate": {}}
            return legal_moves[0]

        root_tokens = {pid: list(env.tokens[pid]) for pid in env.player_ids}
        rng = random.Random(f"{self.seed}|{player}|{dice}|{sorted(root_tokens.items())}")

        sim = _SimEnv(env)
        root = _Node(player, self._candidates(root_tokens[player], legal_moves))

        for _ in range(self.num_rollouts):
            sim.reset_to(root_tokens)
            self._iterate(sim, root, dice, rng)

        # Robust child: most visited; ties -> higher win rate -> lower token index.
        best = max(root.moves, key=lambda m: (root.N[m],
                                              root.W[m] / root.N[m] if root.N[m] else 0.0,
                                              -m))
        self.last_search_info = {
            "root_moves": list(root.moves),
            "visits": dict(root.N),
            "win_rate": {m: (root.W[m] / root.N[m] if root.N[m] else None) for m in root.moves},
        }
        return best

    # ---- helpers ----------------------------------------------------------- #
    def _candidates(self, own_tokens, legal):
        if not self.merge_equivalent_moves:
            return list(legal)
        seen, out = set(), []
        for m in sorted(legal):                  # lowest index represents each class
            if own_tokens[m] not in seen:
                seen.add(own_tokens[m])
                out.append(m)
        return out

    @staticmethod
    def _next_turn(sim, mover, dice, rng):
        """Advance the turn: handle extra turn on 6, roll dice, skip players with no legal move."""
        ids = sim.player_ids
        nxt = mover if dice == 6 else ids[(ids.index(mover) + 1) % len(ids)]
        for _ in range(10000):
            d = rng.randint(1, 6)
            legal = LudoEnv.get_legal_moves(sim, nxt, d)
            if legal:
                return nxt, d, legal
            if d != 6:
                nxt = ids[(ids.index(nxt) + 1) % len(ids)]
        return None

    @staticmethod
    def _terminal_reward(sim):
        return {pid: (1.0 if pid == sim.winner else 0.0) for pid in sim.player_ids}

    @staticmethod
    def _progress_reward(sim):
        """Used only when a rollout hits the step cap: leader by progress gets the reward."""
        scores = {}
        for pid in sim.player_ids:
            hs = sim.HOME_START + pid * sim.HOME_LEN
            st = sim.START_POSITIONS[pid]
            tot = 0
            for pos in sim.tokens[pid]:
                if pos == -1:
                    continue
                if 0 <= pos < sim.BOARD_SIZE:
                    tot += ((pos - st) % sim.BOARD_SIZE) + 1
                else:
                    tot += sim.BOARD_SIZE + (pos - hs + 1)
            scores[pid] = tot
        top = max(scores.values())
        leaders = [p for p, s in scores.items() if s == top]
        return {pid: (1.0 / len(leaders) if pid in leaders else 0.0) for pid in sim.player_ids}

    def _rollout(self, sim, mover, dice, legal, rng):
        """Uniform-random playout from the turn (mover, dice, legal) until a winner."""
        for _ in range(self.max_rollout_steps):
            m = rng.choice(legal)
            LudoEnv.apply_move(sim, mover, m, dice)
            if sim.winner is not None:
                return self._terminal_reward(sim)
            turn = self._next_turn(sim, mover, dice, rng)
            if turn is None:
                break
            mover, dice, legal = turn
        return self._progress_reward(sim)

    def _select_move_in_node(self, node, rng):
        untried = [m for m in node.moves if node.N[m] == 0]
        if untried:
            return rng.choice(untried)
        log_n = math.log(node.visits)
        c = self.exploration_c
        return max(node.moves,
                   key=lambda m: node.W[m] / node.N[m] + c * math.sqrt(log_n / node.N[m]))

    def _iterate(self, sim, root, root_dice, rng):
        """One MCTS iteration: select -> expand -> simulate -> backpropagate."""
        node, dice = root, root_dice
        path = []                                # [(node, move)]
        reward = None

        while True:
            move = self._select_move_in_node(node, rng)
            path.append((node, move))
            LudoEnv.apply_move(sim, node.mover, move, dice)

            if sim.winner is not None:           # terminal
                reward = self._terminal_reward(sim)
                break

            turn = self._next_turn(sim, node.mover, dice, rng)
            if turn is None:                     # pathological stall -> cutoff
                reward = self._progress_reward(sim)
                break
            nxt_mover, nxt_dice, nxt_legal = turn

            key = (move, nxt_dice)
            child = node.children.get(key)
            if child is None:                    # expansion: add ONE node, then simulate
                moves = self._candidates(sim.tokens[nxt_mover], nxt_legal)
                node.children[key] = _Node(nxt_mover, moves)
                reward = self._rollout(sim, nxt_mover, nxt_dice, nxt_legal, rng)
                break
            node, dice = child, nxt_dice

        for n, m in path:                        # backpropagation (mover's own reward)
            n.visits += 1
            n.N[m] += 1
            n.W[m] += reward[n.mover]
