import math
import random

import numpy as np

from config import N, CLASSIC_MCTS_SIMULATIONS as SIMULATIONS, CLASSIC_C_PUCT as C_PUCT
from intefraces.i_game_state import IGameState
from utils.loaders import Game
from utils.progress import progress_bar


def get_neighbors():
    """ Get neighbors for each position """
    index_board = np.arange(Game.BOARD_SIZE, dtype=np.int)
    # Frame index board with -1 values
    fb_n = N + 2
    frame_board = np.full(fb_n ** 2, -1)
    frame_board.reshape(fb_n, fb_n)[1:-1, 1:-1] = index_board.reshape(N, N)
    # Get neighbors
    neighbors = {}
    for i in np.arange(fb_n ** 2).reshape(fb_n, fb_n)[1:-1, 1:-1].ravel():
        ni = [i - fb_n - 1, i - fb_n, i - fb_n + 1, i - 1, i + 1, i + fb_n - 1, i + fb_n, i + fb_n + 1]
        neighbors[frame_board[i]] = list(filter(lambda x: x != -1, frame_board[ni]))
    return neighbors


NEIGHBORS = get_neighbors()


class Node:

    def __init__(self, state: IGameState):
        self.state = state
        self.edges = []


class Edge:

    def __init__(self, in_node: Node, out_node: Node, action: int):
        self.in_node = in_node
        self.out_node = out_node
        self.action = action
        self.player = in_node.state.get_player()
        self.stats = {'N': 0, 'W': 0, 'Q': 0}


class MctsClassic:
    """ Classic Monte Carlo tree search """

    def __init__(self):
        self._tree = {}
        self._root = None

    def get_distribution(self, state: IGameState, verbose=True) -> np.ndarray:
        """ Perform MCTS simulations starting from current game state.
        :param state: root game state
        :param verbose: print progress info
        :return visit_counts: a vector of probability distribution over all actions
        """
        # Set root node
        if state.get_hashable() not in self._tree:
            self._create_tree(state)
        else:
            self._root = self._tree[state.get_hashable()]
            self._prune_tree(self._root)
        # Explore the tree
        for i in range(SIMULATIONS):
            self._simulate()
            if verbose:
                progress_bar(i + 1, SIMULATIONS, 'Exploring tree')
        # Return visit counts
        visit_counts = np.zeros(Game.ACTION_SIZE, dtype=np.integer)
        for edge in self._root.edges:
            visit_counts[edge.action] = edge.stats['N']
        return visit_counts / sum(visit_counts)

    def _simulate(self):
        """ Move to leaf node, evaluate it, and back propagate the value """
        leaf, breadcrumbs = self._move_to_leaf()
        if not leaf.state.is_game_finished():
            value = self._rollout(leaf.state)
            self._expand_node(leaf)
        else:
            value = leaf.state.get_value()
        self._back_propagate(leaf, value, breadcrumbs)

    def _move_to_leaf(self) -> (Node, list):
        """ Move down the tree until hit a leaf node """
        node = self._root
        breadcrumbs = []
        while node.edges:
            best_edge = self._get_best_edge(node)
            node = best_edge.out_node
            breadcrumbs.append(best_edge)
        return node, breadcrumbs

    @staticmethod
    def _rollout(state: IGameState) -> int:
        """ Return a result of a random rollout """
        player = state.get_player()
        # Random descent until game is finished
        while not state.is_game_finished():
            # Make random move
            action = random.choice(state.get_valid_actions())
            state = state.get_next_state(action)
        return state.get_value() if state.get_player() == player else -state.get_value()

    def _expand_node(self, leaf: Node):
        """ Expand node """
        for action in leaf.state.get_valid_actions():
            new_state = leaf.state.get_next_state(action)
            # Add node if necessary
            if new_state.get_hashable() not in self._tree:
                new_node = Node(new_state)
                self._add_node(self._tree, new_node)
            else:
                new_node = self._tree[new_state.get_hashable()]
            # Add edge
            new_edge = Edge(leaf, new_node, action)
            leaf.edges.append(new_edge)

    @staticmethod
    def _back_propagate(leaf: Node, value: int, breadcrumbs: list):
        """ Back propagate leaf value up the tree """
        leaf_player = leaf.state.get_player()
        for edge in breadcrumbs:
            sign = 1 if edge.player == leaf_player else -1
            edge.stats['N'] += 1
            edge.stats['W'] += value * sign
            edge.stats['Q'] = edge.stats['W'] / edge.stats['N']

    @staticmethod
    def _get_best_edge(node: Node):
        """ Pick edge with highest upper confidence bound """
        total_visits = sum(edge.stats['N'] for edge in node.edges)
        max_u = -float('inf')
        best_edge = None
        for edge in node.edges:
            if edge.stats['N'] == 0:
                return edge
            u = edge.stats['Q'] + C_PUCT * (math.log(total_visits) / edge.stats['N']) ** 0.5
            if u > max_u:
                max_u = u
                best_edge = edge
        return best_edge

    def _create_tree(self, state: IGameState):
        """ Create a new tree """
        self._tree = {}
        self._root = Node(state)
        self._add_node(self._tree, self._root)

    def _prune_tree(self, node: Node):
        """ Keep only subtree of the node and prune the rest """

        def copy_subtree(node_: Node):
            for edge in node_.edges:
                self._add_node(subtree, edge.out_node)
                copy_subtree(edge.out_node)

        subtree = {}
        self._add_node(subtree, node)
        copy_subtree(node)
        self._tree = subtree

    @staticmethod
    def _add_node(tree: dict, node: Node):
        """ Add node to the tree """
        tree[node.state.get_hashable()] = node
