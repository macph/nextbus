"""
Testing the graph module for service diagrams.
"""
import pytest

from nextbus.graph import (
    Path, Graph, _Layout, _rearrange_cycles, MaxColumnError, LayoutError,
    _set_lines, _draw_paths_between, draw_graph, _median,
    _count_crossings, _count_all_crossings
)


@pytest.fixture
def linear_path():
    return Path([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])


@pytest.fixture
def cyclic_path():
    return Path([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0])


def test_path_edges(linear_path):
    assert linear_path.edges == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
                                 (6, 7), (7, 8), (8, 9)]


def test_path_not_cyclic(linear_path):
    assert not linear_path.cyclic


def test_path_cyclic(cyclic_path):
    assert cyclic_path.cyclic


def test_path_make_not_cyclic(linear_path):
    assert linear_path.make_acyclic() == linear_path


def test_path_make_cyclic(linear_path, cyclic_path):
    assert cyclic_path.make_acyclic() == linear_path


def test_path_prepend(linear_path):
    linear_path.prepend(-1)
    assert linear_path._v == list(range(-1, 10))


def test_path_append(linear_path):
    linear_path.append(10)
    assert linear_path._v == list(range(11))


def test_path_prepend_with(linear_path):
    assert linear_path.prepend_with(-1)._v == list(range(-1, 10))


def test_path_append_with(linear_path):
    assert linear_path.append_with(10)._v == list(range(11))


def test_path_empty():
    path = Path()
    assert len(path) == 0
    assert not path.cyclic
    assert path.edges == []
    assert path.make_acyclic() == path


def test_path_split_left(linear_path):
    assert linear_path.split((0, 1)) == [Path(range(1, 10))]


def test_path_split_right(linear_path):
    assert linear_path.split((8, 9)) == [Path(range(9))]


def test_path_split_middle(linear_path):
    assert linear_path.split((4, 5)) == [Path(range(5)), Path(range(5, 10))]


def test_path_wrong_edge(linear_path):
    with pytest.raises(KeyError):
        linear_path.split((-1, 0))


GRAPHS = {
    # Empty
    "empty": (None, None),
    # Single vertex
    "single": (None, [0]),
    # Simple path
    "simple": ([(0, 1), (1, 2), (2, 3), (3, 4)], None),
    # Two distinct paths
    "two paths": ([(0, 1), (1, 2), (2, 3), (10, 11), (11, 12)], None),
    # Two paths, crossed
    "merged paths": ([(0, 1), (1, 2), (2, 4), (3, 4), (4, 5), (5, 6), (6, 7),
                      (6, 8), (8, 9)], None),
    # Path with a longer loop
    "path with loop": ([(0, 1), (1, 2), (2, 3), (2, 5), (3, 4), (4, 5), (5, 6),
                        (6, 7)], None),
    # Path with a loop and a crossover
    "crossed paths": ([(0, 1), (1, 2), (1, 4), (1, 5), (2, 3), (3, 4), (3, 5),
                       (4, 6), (5, 6), (6, 7)], None),
    # Complex with crossovers and dead end
    "complex graph": ([(0, 1), (1, 2), (1, 5), (1, 9), (2, 3), (3, 4), (3, 7),
                       (4, 5), (4, 8), (5, 6), (5, 7), (7, 8), (8, 9), (9, 10)],
                      None),
    # Path with a self-cycle
    "self cycle": ([(0, 1), (1, 2), (2, 2), (2, 3)], None),
    # Simple cycle
    "simple cycle": ([(0, 1), (1, 2), (2, 3), (3, 0)], None),
    # Path starting with a cycle (sources = 0, sinks > 0)
    "starting cycle": ([(0, 1), (1, 2), (2, 3), (3, 0), (3, 4), (4, 5)], None),
    # Path ending with a cycle (sources > 0, sinks = 0)
    "ending cycle": ([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 2)], None),
    # Pair of cycles, crossed
    "crossed cycles": ([(1, 2), (2, 0), (0, 3), (3, 4), (4, 5), (5, 1),
                        (11, 12), (12, 0), (0, 13), (13, 14), (14, 15),
                        (15, 11)], None),
    # Complex cyclic paths
    "complex cycles": ([(0, 2), (1, 2), (2, 1), (2, 3), (3, 4), (3, 5), (4, 6),
                        (5, 6), (6, 1), (5, 7), (7, 3), (7, 8), (7, 9), (9, 0),
                        (9, 5), (9, 8)], None),
}


def graph_from_key(key, sort=None):
    return Graph(*GRAPHS[key], sort)


@pytest.fixture
def empty_graph():
    return graph_from_key("empty")


@pytest.fixture
def single_graph():
    return graph_from_key("single")


@pytest.fixture
def simple_graph():
    return graph_from_key("simple")


@pytest.fixture
def two_graph():
    return graph_from_key("two paths")


@pytest.fixture
def merged_graph():
    return graph_from_key("merged paths")


@pytest.fixture
def complex_graph():
    return graph_from_key("complex graph")


@pytest.fixture
def self_cycle_graph():
    return graph_from_key("self cycle")


@pytest.fixture
def complex_cycle_graph():
    return graph_from_key("complex cycles")


def test_graph_false():
    assert not Graph()


def test_graph_true(single_graph, simple_graph):
    assert single_graph
    assert simple_graph


def test_graph_len(merged_graph):
    assert len(merged_graph) == 10


def test_graph_contains(single_graph, merged_graph):
    assert 0 in single_graph
    assert 0 in merged_graph


def test_graph_not_contains(empty_graph, merged_graph):
    assert 0 not in empty_graph
    assert 10 not in merged_graph


def test_graph_equals(simple_graph):
    assert simple_graph == Graph([(0, 1), (1, 2), (2, 3), (3, 4)])


def test_graph_not_equals(simple_graph):
    assert simple_graph != Graph([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])


def test_graph_equals_wrong_type(simple_graph):
    assert simple_graph != [(0, 1), (1, 2), (2, 3), (3, 4)]


GRAPH_ADJ_LISTS = {
    "empty": {},
    "single": {0: set()},
    "simple": {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: set()},
    "two paths": {0: {1}, 1: {2}, 2: {3}, 3: set(), 10: {11}, 11: {12},
                  12: set()},
    "merged paths": {0: {1}, 1: {2}, 2: {4}, 3: {4}, 4: {5}, 5: {6}, 6: {7, 8},
                     7: set(), 8: {9}, 9: set()},
    "path with loop": {0: {1}, 1: {2}, 2: {3, 5}, 3: {4}, 4: {5}, 5: {6},
                       6: {7}, 7: set()},
    "crossed paths": {0: {1}, 1: {2, 4, 5}, 2: {3}, 3: {4, 5}, 4: {6}, 5: {6},
                      6: {7}, 7: set()},
    "complex graph": {0: {1}, 1: {9, 2, 5}, 2: {3}, 5: {6, 7}, 9: {10},
                      3: {4, 7}, 4: {8, 5}, 7: {8}, 8: {9}, 6: set(),
                      10: set()},
    "self cycle": {0: {1}, 1: {2}, 2: {2, 3}, 3: set()},
    "simple cycle": {0: {1}, 1: {2}, 2: {3}, 3: {0}},
    "starting cycle": {0: {1}, 1: {2}, 2: {3}, 3: {0, 4}, 4: {5}, 5: set()},
    "ending cycle": {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: {5}, 5: {2}},
    "crossed cycles": {0: {3, 13}, 1: {2}, 2: {0}, 3: {4}, 4: {5}, 5: {1},
                       11: {12}, 12: {0}, 13: {14}, 14: {15}, 15: {11}},
    "complex cycles": {0: {2}, 1: {2}, 2: {1, 3}, 3: {4, 5}, 4: {6}, 5: {6, 7},
                       6: {1}, 7: {3, 8, 9}, 8: set(), 9: {0, 5, 8}},
}


@pytest.mark.parametrize("key, adj_list", GRAPH_ADJ_LISTS.items())
def test_graph_from_adj(key, adj_list):
    assert Graph.from_adj(adj_list) == graph_from_key(key)


@pytest.mark.parametrize("key, expected", GRAPH_ADJ_LISTS.items())
def test_graph_adj(key, expected):
    assert graph_from_key(key).adj == expected


@pytest.mark.parametrize("key, expected", {
    "empty": set(),
    "single": set(),
    "simple": {0, 1, 2, 3},
    "two paths": {0, 1, 2, 10, 11},
    "merged paths": {0, 1, 2, 3, 4, 5, 6, 8},
    "path with loop": {0, 1, 2, 3, 4, 5, 6},
    "crossed paths": {0, 1, 2, 3, 4, 5, 6},
    "complex graph": {0, 1, 2, 3, 4, 5, 7, 8, 9},
    "self cycle": {0, 1, 2},
    "simple cycle": {0, 1, 2, 3},
    "starting cycle": {0, 1, 2, 3, 4},
    "ending cycle": {0, 1, 2, 3, 4, 5},
    "crossed cycles": {0, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15},
    "complex cycles": {0, 1, 2, 3, 4, 5, 6, 7, 9},
}.items())
def test_graph_heads(key, expected):
    assert graph_from_key(key).heads == expected


@pytest.mark.parametrize("key, expected", {
    "empty": set(),
    "single": set(),
    "simple": {1, 2, 3, 4},
    "two paths": {1, 2, 3, 11, 12},
    "merged paths": {1, 2, 4, 5, 6, 7, 8, 9},
    "path with loop": {1, 2, 3, 4, 5, 6, 7},
    "crossed paths": {1, 2, 3, 4, 5, 6, 7},
    "complex graph": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
    "self cycle": {1, 2, 3},
    "simple cycle": {0, 1, 2, 3},
    "starting cycle": {0, 1, 2, 3, 4, 5},
    "ending cycle": {1, 2, 3, 4, 5},
    "crossed cycles": {0, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15},
    "complex cycles": {0, 1, 2, 3, 4, 5, 6, 7, 8, 9},
}.items())
def test_graph_tails(key, expected):
    assert graph_from_key(key).tails == expected


@pytest.mark.parametrize("key, expected", {
    "empty": set(),
    "single": set(),
    "simple": {0},
    "two paths": {0, 10},
    "merged paths": {0, 3},
    "path with loop": {0},
    "crossed paths": {0},
    "complex graph": {0},
    "self cycle": {0},
    "simple cycle": set(),
    "starting cycle": set(),
    "ending cycle": {0},
    "crossed cycles": set(),
    "complex cycles": set(),
}.items())
def test_graph_sources(key, expected):
    assert graph_from_key(key).sources == expected


@pytest.mark.parametrize("key, expected", {
    "empty": set(),
    "single": set(),
    "simple": {4},
    "two paths": {3, 12},
    "merged paths": {7, 9},
    "path with loop": {7},
    "crossed paths": {7},
    "complex graph": {6, 10},
    "self cycle": {3},
    "simple cycle": set(),
    "starting cycle": {5},
    "ending cycle": set(),
    "crossed cycles": set(),
    "complex cycles": {8},
}.items())
def test_graph_sinks(key, expected):
    assert graph_from_key(key).sinks == expected


@pytest.mark.parametrize("key, expected", {
    "empty": set(),
    "single": set(),
    "simple": {(0, 1), (1, 2), (2, 3), (3, 4)},
    "two paths": {(0, 1), (1, 2), (2, 3), (10, 11), (11, 12)},
    "merged paths": {(0, 1), (1, 2), (2, 4), (3, 4), (3, 4), (4, 5), (5, 6),
                     (6, 7), (6, 8), (8, 9)},
    "path with loop": {(0, 1), (1, 2), (2, 3), (2, 5), (3, 4), (4, 5), (5, 6),
                       (6, 7)},
    "crossed paths": {(0, 1), (1, 2), (1, 4), (1, 5), (2, 3), (3, 4), (3, 5),
                      (4, 6), (5, 6), (6, 7)},
    "complex graph": {(0, 1), (1, 2), (1, 5), (1, 9), (2, 3), (3, 4), (3, 7),
                      (4, 5), (4, 8), (5, 6), (5, 7), (7, 8), (8, 9), (9, 10)},
    "self cycle": {(0, 1), (1, 2), (2, 2), (2, 3)},
    "simple cycle": {(0, 1), (1, 2), (2, 3), (3, 0)},
    "starting cycle": {(0, 1), (1, 2), (2, 3), (3, 0), (3, 4), (4, 5)},
    "ending cycle": {(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 2)},
    "crossed cycles": {(1, 2), (2, 0), (0, 3), (3, 4), (4, 5), (5, 1), (11, 12),
                       (12, 0), (0, 13), (13, 14), (14, 15), (15, 11)},
    "complex cycles": {(0, 2), (1, 2), (2, 1), (2, 3), (3, 4), (3, 5), (4, 6),
                       (5, 6), (6, 1), (5, 7), (7, 3), (7, 8), (7, 9), (9, 0),
                       (9, 5), (9, 8)},
}.items())
def test_graph_edges(key, expected):
    assert graph_from_key(key).edges == expected


@pytest.mark.parametrize("key, expected", {
    "empty": set(),
    "single": {0},
    "simple": {0, 1, 2, 3, 4},
    "two paths": {0, 1, 2, 3, 10, 11, 12},
    "merged paths": {0, 1, 2, 3, 4, 5, 6, 7, 8, 9},
    "path with loop": {0, 1, 2, 3, 4, 5, 6, 7},
    "crossed paths": {0, 1, 2, 3, 4, 5, 6, 7},
    "complex graph": {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
    "self cycle": {0, 1, 2, 3},
    "simple cycle": {0, 1, 2, 3},
    "starting cycle": {0, 1, 2, 3, 4, 5},
    "ending cycle": {0, 1, 2, 3, 4, 5},
    "crossed cycles": {0, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15},
    "complex cycles": {0, 1, 2, 3, 4, 5, 6, 7, 8, 9},
}.items())
def test_graph_vertices(key, expected):
    assert graph_from_key(key).vertices == expected


@pytest.mark.parametrize("key, expected", [
    ("empty", set()),
    ("single", {0}),
    ("simple", set()),
])
def test_graph_isolated_vertices(key, expected):
    assert graph_from_key(key).isolated == expected


@pytest.mark.parametrize("vertex, expected", [
    (0, set()),
    (4, {2, 3}),
    (6, {5}),
    (9, {8}),
])
def test_graph_preceding(vertex, expected):
    assert graph_from_key("merged paths").preceding(vertex) == expected


@pytest.mark.parametrize("vertex, expected", [
    (0, {1}),
    (4, {5}),
    (6, {7, 8}),
    (9, set()),
])
def test_graph_following(vertex, expected):
    assert graph_from_key("merged paths").following(vertex) == expected


@pytest.mark.parametrize("vertex, expected", [
    (0, set()),
    (4, {(2, 4), (3, 4)}),
    (6, {(5, 6)}),
    (9, {(8, 9)}),
])
def test_graph_incoming(vertex, expected):
    assert graph_from_key("merged paths").incoming(vertex) == expected


@pytest.mark.parametrize("vertex, expected", [
    (0, {(0, 1)}),
    (4, {(4, 5)}),
    (6, {(6, 7), (6, 8)}),
    (9, set()),
])
def test_graph_outgoing(vertex, expected):
    assert graph_from_key("merged paths").outgoing(vertex) == expected


def test_graph_preceding_not_exists(simple_graph):
    with pytest.raises(KeyError):
        simple_graph.preceding(10)


def test_graph_following_wrong_vertex(simple_graph):
    with pytest.raises(KeyError):
        simple_graph.following(10)


def test_graph_incoming_wrong_vertex(simple_graph):
    with pytest.raises(KeyError):
        simple_graph.incoming(10)


def test_graph_outgoing_wrong_vertex(simple_graph):
    with pytest.raises(KeyError):
        simple_graph.outgoing(10)


def test_add_edge(simple_graph):
    simple_graph.add_edge(4, 5)
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: {5},
                                5: set()}


def test_add_vertex(empty_graph, single_graph):
    empty_graph.add_vertex(0)
    assert empty_graph == single_graph


def test_remove_vertex(simple_graph):
    simple_graph.remove_vertex(2)
    assert simple_graph.adj == {0: {1}, 1: set(), 3: {4}, 4: set()}


def test_remove_vertex_not_exists(simple_graph):
    with pytest.raises(KeyError):
        simple_graph.remove_vertex(10)


def test_remove_edge(simple_graph):
    simple_graph.remove_edge(2, 3)
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: set(), 3: {4}, 4: set()}


def test_remove_edge_vertex(simple_graph):
    simple_graph.remove_edge(3, 4, delete=True)
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: {3}, 3: set()}


def test_remove_edge_not_vertex(simple_graph):
    simple_graph.remove_edge(3, 4, delete=False)
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: {3}, 3: set(), 4: set()}


def test_remove_wrong_edge(simple_graph):
    with pytest.raises(KeyError):
        simple_graph.remove_edge(9, 10)


def test_add_path(simple_graph):
    simple_graph.add_path(Path([-3, -2, -1, 0]))
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: set(),
                                -3: {-2}, -2: {-1}, -1: {0}}


def test_add_path_sequence(simple_graph):
    simple_graph.add_path([(-3, -2), (-2, -1), (-1, 0)])
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: set(),
                                -3: {-2}, -2: {-1}, -1: {0}}


def test_add_path_partial(simple_graph):
    simple_graph.add_path(Path([10, 11, 2, 3, 14, 15, 16]))
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: {3}, 3: {4, 14}, 4: set(),
                                10: {11}, 11: {2}, 14: {15}, 15: {16},
                                16: set()}


def test_remove_path(simple_graph):
    simple_graph.remove_path(Path([2, 3, 4]))
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: set()}


def test_remove_path_no_delete(simple_graph):
    simple_graph.remove_path(Path([2, 3, 4]), delete=False)
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: set(), 3: set(), 4: set()}


def test_remove_path_sequence(simple_graph):
    simple_graph.remove_path([(2, 3), (3, 4)])
    assert simple_graph.adj == {0: {1}, 1: {2}, 2: set()}


def test_remove_path_wrong_edge(simple_graph):
    num_vertices = len(simple_graph)
    msg = (r"Edge \(4, 5\) on path \[\(2, 3\), \(3, 4\), \(4, 5\)\] does "
           r"not exist in graph")
    with pytest.raises(ValueError, match=msg):
        simple_graph.remove_path([(2, 3), (3, 4), (4, 5)])

    assert len(simple_graph) == num_vertices


def test_split_graph_empty(empty_graph):
    assert empty_graph.split() == [Graph()]


def test_split_graph_single(single_graph):
    assert single_graph.split() == [Graph(singles=[0])]


def test_split_graph_disconnected(two_graph):
    g0 = Graph([(0, 1), (1, 2), (2, 3)])
    g1 = Graph([(10, 11), (11, 12)])

    g_split = two_graph.split()
    assert len(g_split) == 2
    assert g0 in g_split
    assert g1 in g_split


def test_split_graph_connected(simple_graph):
    assert simple_graph.split() == [simple_graph]


def test_copy_simple(simple_graph):
    copy = simple_graph.copy()
    assert copy == simple_graph
    assert copy is not simple_graph


def test_copy_isolated(single_graph):
    copy = single_graph.copy()
    assert copy == single_graph
    assert copy is not single_graph


def test_clean_copy(self_cycle_graph):
    copy = self_cycle_graph.clean_copy()
    assert copy == Graph([(0, 1), (1, 2), (2, 3)])


def test_copy_clean_already(simple_graph):
    copy = simple_graph.clean_copy()
    assert copy == simple_graph


@pytest.mark.parametrize("key, expected", {
    "single": {0: Path()},
    "simple": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3]),
        4: Path([0, 1, 2, 3, 4])
    },
    "two paths": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3]),
        10: Path(),
        11: Path(),
        12: Path()
    },
    "merged paths": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path(),
        4: Path([0, 1, 2, 4]),
        5: Path([0, 1, 2, 4, 5]),
        6: Path([0, 1, 2, 4, 5, 6]),
        7: Path([0, 1, 2, 4, 5, 6, 7]),
        8: Path([0, 1, 2, 4, 5, 6, 8]),
        9: Path([0, 1, 2, 4, 5, 6, 8, 9])
    },
    "path with loop": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3]),
        4: Path([0, 1, 2, 3, 4]),
        5: Path([0, 1, 2, 5]),
        6: Path([0, 1, 2, 5, 6]),
        7: Path([0, 1, 2, 5, 6, 7])
    },
    "crossed paths": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3]),
        4: Path([0, 1, 4]),
        5: Path([0, 1, 5]),
        6: Path([0, 1, 4, 6]),
        7: Path([0, 1, 4, 6, 7])
    },
    "complex graph": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3]),
        4: Path([0, 1, 2, 3, 4]),
        5: Path([0, 1, 5]),
        6: Path([0, 1, 5, 6]),
        7: Path([0, 1, 5, 7]),
        8: Path([0, 1, 5, 7, 8]),
        9: Path([0, 1, 9]),
        10: Path([0, 1, 9, 10])
    },
    "self cycle": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3])
    },
    "simple cycle": {
        0: Path([0, 1, 2, 3, 0]),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3])
    },
    "starting cycle": {
        0: Path([0, 1, 2, 3, 0]),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3]),
        4: Path([0, 1, 2, 3, 4]),
        5: Path([0, 1, 2, 3, 4, 5])
    },
    "ending cycle": {
        0: Path(),
        1: Path([0, 1]),
        2: Path([0, 1, 2]),
        3: Path([0, 1, 2, 3]),
        4: Path([0, 1, 2, 3, 4]),
        5: Path([0, 1, 2, 3, 4, 5])
    },
    "crossed cycles": {
        0: Path([0, 3, 4, 5, 1, 2, 0]),
        1: Path([0, 3, 4, 5, 1]),
        2: Path([0, 3, 4, 5, 1, 2]),
        3: Path([0, 3]),
        4: Path([0, 3, 4]),
        5: Path([0, 3, 4, 5]),
        11: Path([0, 13, 14, 15, 11]),
        12: Path([0, 13, 14, 15, 11, 12]),
        13: Path([0, 13]),
        14: Path([0, 13, 14]),
        15: Path([0, 13, 14, 15])
    },
    "complex cycles": {
        0: Path([0, 2, 3, 5, 7, 9, 0]),
        1: Path([0, 2, 1]),
        2: Path([0, 2]),
        3: Path([0, 2, 3]),
        4: Path([0, 2, 3, 4]),
        5: Path([0, 2, 3, 5]),
        6: Path([0, 2, 3, 4, 6]),
        7: Path([0, 2, 3, 5, 7]),
        8: Path([0, 2, 3, 5, 7, 8]),
        9: Path([0, 2, 3, 5, 7, 9])
    },
}.items())
def test_search_paths_start_zero(key, expected):
    assert graph_from_key(key).search_paths(0) == expected


@pytest.mark.parametrize("key, expected", {
    "empty": Path(),
    "single": Path(),
    "simple": Path([0, 1, 2, 3, 4]),
    "two paths": Path([0, 1, 2, 3]),
    "merged paths": Path([0, 1, 2, 4, 5, 6, 8, 9]),
    "path with loop": Path([0, 1, 2, 5, 6, 7]),
    "crossed paths": Path([0, 1, 4, 6, 7]),
    "complex graph": Path([2, 3, 4, 8, 9, 10]),
    "self cycle": Path([0, 1, 2, 3]),
    "simple cycle": Path([0, 1, 2, 3, 0]),
    "starting cycle": Path([0, 1, 2, 3, 4, 5]),
    "ending cycle": Path([0, 1, 2, 3, 4, 5]),
    "crossed cycles": Path([3, 4, 5, 1, 2, 0, 13, 14, 15, 11, 12]),
    "complex cycles": Path([4, 6, 1, 2, 3, 5, 7, 9, 0]),
}.items())
def test_graph_diameter(key, expected):
    assert graph_from_key(key).diameter() == expected


@pytest.mark.parametrize("key, expected", {
    "empty": [],
    "single": [],
    "simple": [Path([0, 1, 2, 3, 4])],
    "two paths": [
        Path([0, 1, 2, 3]),
        Path([10, 11, 12])
    ],
    "merged paths": [
        Path([0, 1, 2, 4, 5, 6, 8, 9]),
        Path([3, 4]),
        Path([6, 7])
    ],
    "path with loop": [
        Path([0, 1, 2, 5, 6, 7]),
        Path([2, 3, 4, 5])
    ],
    "crossed paths": [
        Path([0, 1, 4, 6, 7]),
        Path([1, 2]),
        Path([1, 5]),
        Path([2, 3, 5, 6]),
        Path([3, 4])
    ],
    "complex graph": [
        Path([0, 1, 9]),
        Path([1, 2]),
        Path([1, 5, 7, 8]),
        Path([2, 3, 4, 8, 9, 10]),
        Path([3, 7]),
        Path([4, 5, 6])
    ],
    "self cycle": [Path([0, 1, 2, 3])],
    "simple cycle": [Path([0, 1, 2, 3, 0])],
    "starting cycle": [
        Path([0, 1, 2, 3, 4, 5]),
        Path([3, 0])
    ],
    "ending cycle": [
        Path([0, 1, 2, 3, 4, 5]),
        Path([5, 2])
    ],
    "crossed cycles": [
        Path([0, 3]),
        Path([3, 4, 5, 1, 2, 0, 13, 14, 15, 11, 12]),
        Path([12, 0])
    ],
    "complex cycles": [
        Path([0, 2]),
        Path([2, 1]),
        Path([3, 4]),
        Path([4, 6, 1, 2, 3, 5, 7, 9, 0]),
        Path([5, 6]),
        Path([7, 3]),
        Path([7, 8]),
        Path([9, 5]),
        Path([9, 8])
    ],
}.items())
def test_graph_paths(key, expected):
    assert sorted(graph_from_key(key).paths(), key=tuple) == expected


@pytest.mark.parametrize("key, expected", {
    "empty": [],
    "single": [0],
    "simple": [0, 1, 2, 3, 4],
    "two paths": [0, 1, 2, 3, 10, 11, 12],
    "merged paths": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "path with loop": [0, 1, 2, 3, 4, 5, 6, 7],
    "crossed paths": [0, 1, 2, 3, 4, 5, 6, 7],
    "complex graph": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "self cycle": [0, 1, 2, 3],
    "simple cycle": [0, 1, 2, 3],
    "starting cycle": [0, 1, 2, 3, 4, 5],
    "ending cycle": [0, 1, 2, 3, 4, 5],
    "crossed cycles": [3, 4, 5, 1, 2, 0, 13, 14, 15, 11, 12],
    "complex cycles": [4, 6, 1, 2, 3, 5, 7, 9, 8, 0],
}.items())
def test_graph_sequence(key, expected):
    assert graph_from_key(key).sequence() == expected


def test_graph_rearrange_cycles(complex_cycle_graph):
    # 8 is not in a cycle but is placed before 9 - need to rearrange
    sequence = [4, 6, 1, 2, 3, 5, 7, 8, 9, 0]
    _rearrange_cycles(complex_cycle_graph, sequence)

    assert sequence == [4, 6, 1, 2, 3, 5, 7, 9, 8, 0]


@pytest.mark.parametrize("key, expected", {
    "empty": [],
    "single": [0],
    "simple": [0, 1, 2, 3, 4],
    "two paths": [0, 1, 2, 3, 10, 11, 12],
    "merged paths": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "path with loop": [0, 1, 2, 3, 4, 5, 6, 7],
    "crossed paths": [0, 1, 2, 3, 5, 4, 6, 7],
    "complex graph": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "self cycle": [0, 1, 2, 3],
    "simple cycle": [3, 0, 1, 2],
    "starting cycle": [0, 1, 2, 3, 4, 5],
    "ending cycle": [0, 1, 2, 3, 4, 5],
    "crossed cycles": [13, 14, 15, 11, 12, 0, 3, 4, 5, 1, 2],
    "complex cycles": [4, 6, 1, 2, 3, 5, 7, 9, 8, 0],
}.items())
def test_graph_sequence_inverted(key, expected):
    def _sort_inverse(vertex):
        return -vertex

    assert graph_from_key(key, sort=_sort_inverse).sequence() == expected


@pytest.fixture
def simple_layout(simple_graph):
    gl = _Layout(simple_graph)
    _set_lines(gl)

    return gl


@pytest.fixture
def complex_layout(complex_cycle_graph):
    gl = _Layout(complex_cycle_graph)
    _set_lines(gl)

    return gl


def row_as_tuple(row):
    return (row.vertex, row.column, row.start, row.end, row.cycles_start,
            row.cycles_end)


def test_layout_row_copy(complex_layout):
    row = complex_layout.rows[4]
    copy = row.copy()

    assert row.layout == copy.layout
    assert row_as_tuple(row) == row_as_tuple(copy)
    assert row.start is not copy.start
    assert row.end is not copy.end
    assert row.cycles_start is not copy.cycles_start
    assert row.cycles_end is not copy.cycles_end
    assert row is not copy


def test_layout_row_copy_another_layout(complex_layout):
    layout = _Layout(complex_layout.g)
    row = complex_layout.rows[4]
    copy = row.copy(layout)

    assert copy.layout == layout
    assert row_as_tuple(row) == row_as_tuple(copy)


def test_layout_row_indices(simple_layout):
    assert all(simple_layout.rows[simple_layout.sequence[i]].index == i
               for i in range(len(simple_layout.sequence)))


def test_layout_row_next(simple_layout):
    assert simple_layout.rows[0].next == simple_layout.rows[1]


def test_layout_row_next_last(simple_layout):
    assert simple_layout.rows[4].next is None


def test_layout_row_previous(simple_layout):
    assert simple_layout.rows[1].previous == simple_layout.rows[0]


def test_layout_row_previous_first(simple_layout):
    assert simple_layout.rows[0].previous is None


def test_layout_copy(simple_layout):
    copy = simple_layout.copy()

    original_rows = {v: row_as_tuple(r) for v, r in simple_layout.rows.items()}
    copied_rows = {v: row_as_tuple(r) for v, r in copy.rows.items()}

    assert copied_rows == original_rows
    assert copy.rows != simple_layout.rows


@pytest.mark.parametrize("vertex, direct, cyclic, expected", [
    (2, False, False, set()),
    (2, False, True, {1}),
    (2, True, False, {3}),
    (2, True, True, {1, 3})
])
def test_layout_outgoing(complex_layout, vertex, direct, cyclic, expected):
    assert complex_layout.outgoing(vertex, direct, cyclic) == expected


@pytest.mark.parametrize("vertex, direct, cyclic, expected", [
    (2, False, False, set()),
    (2, False, True, {0}),
    (2, True, False, {1}),
    (2, True, True, {0, 1})
])
def test_layout_incoming(complex_layout, vertex, direct, cyclic, expected):
    assert complex_layout.incoming(vertex, direct, cyclic) == expected


@pytest.mark.parametrize("key, expected", {
    "empty": [],
    "single": [(0, 0, [set()], [], {}, {})],
    "simple": [
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [{2}], {}, {}),
        (2, 0, [{3}], [{3}], {}, {}),
        (3, 0, [{4}], [{4}], {}, {}),
        (4, 0, [set()], [], {}, {})
    ],
    "two paths": [
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [{2}], {}, {}),
        (2, 0, [{3}], [{3}], {}, {}),
        (3, 0, [set()], [{10}], {}, {}),
        (10, 0, [{11}], [{11}], {}, {}),
        (11, 0, [{12}], [{12}], {}, {}),
        (12, 0, [set()], [], {}, {})
    ],
    "merged paths": [
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [{2}], {}, {}),
        (2, 0, [{4}], [{4}, {3}], {}, {}),
        (3, 1, [{4}, {4}], [{4}], {}, {}),
        (4, 0, [{5}], [{5}], {}, {}),
        (5, 0, [{6}], [{6}], {}, {}),
        (6, 0, [{7, 8}], [{8}, {7}], {}, {}),
        (7, 1, [{8}, set()], [{8}], {}, {}),
        (8, 0, [{9}], [{9}], {}, {}),
        (9, 0, [set()], [], {}, {})
    ],
    "path with loop": [
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [{2}], {}, {}),
        (2, 0, [{3, 5}], [{5}, {3}], {}, {}),
        (3, 1, [{5}, {4}], [{5}, {4}], {}, {}),
        (4, 1, [{5}, {5}], [{5}], {}, {}),
        (5, 0, [{6}], [{6}], {}, {}),
        (6, 0, [{7}], [{7}], {}, {}),
        (7, 0, [set()], [], {}, {})
    ],
    "crossed paths": [
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2, 4, 5}], [{4, 5}, {2}], {}, {}),
        (2, 1, [{4, 5}, {3}], [{4, 5}, {3}], {}, {}),
        (3, 1, [{4, 5}, {4, 5}], [{5}, {4}], {}, {}),
        (4, 1, [{5}, {6}], [{5}, {6}], {}, {}),
        (5, 0, [{6}, {6}], [{6}], {}, {}),
        (6, 0, [{7}], [{7}], {}, {}),
        (7, 0, [set()], [], {}, {})
    ],
    "complex graph": [
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2, 5, 9}], [{5, 9}, {2}], {}, {}),
        (2, 1, [{5, 9}, {3}], [{5, 9}, {3}], {}, {}),
        (3, 1, [{5, 9}, {4, 7}], [{5, 9}, {7}, {4}], {}, {}),
        (4, 2, [{5, 9}, {7}, {5, 8}], [{9}, {7}, {8}, {5}], {}, {}),
        (5, 3, [{9}, {7}, {8}, {6, 7}], [{9}, {7}, {8}, {6}], {}, {}),
        (6, 3, [{9}, {7}, {8}, set()], [{9}, {7}, {8}], {}, {}),
        (7, 1, [{9}, {8}, {8}], [{9}, {8}], {}, {}),
        (8, 1, [{9}, {9}], [{9}], {}, {}),
        (9, 0, [{10}], [{10}], {}, {}),
        (10, 0, [set()], [], {}, {}),
    ],
    "self cycle": [
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [{2}], {}, {}),
        (2, 0, [{3}], [{3}], {}, {}),
        (3, 0, [set()], [], {}, {}),
    ],
    "simple cycle": [
        (None, None, [{0}], [{0}], {}, {0: (3, 0)}),
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [{2}], {}, {}),
        (2, 0, [{3}], [{3}], {}, {}),
        (3, 0, [{0}], [{0}], {0: (3, 0)}, {}),
    ],
    "starting cycle": [
        (None, None, [{0}], [{0}], {}, {0: (3, 0)}),
        (0, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [{2}], {}, {}),
        (2, 0, [{3}], [{3}], {}, {}),
        (3, 0, [{0, 4}], [{0}, {4}], {0: (3, 0)}, {}),
        (4, 1, [set(), {5}], [{5}], {}, {}),
        (5, 0, [set()], [], {}, {}),
    ],
    "ending cycle": [
        (0, 0, [{1}], [set(), {1}], {}, {}),
        (1, 1, [{2}, {2}], [{2}], {}, {0: (5, 2)}),
        (2, 0, [{3}], [{3}], {}, {}),
        (3, 0, [{4}], [{4}], {}, {}),
        (4, 0, [{5}], [{5}], {}, {}),
        (5, 0, [{2}], [{2}], {0: (5, 2)}, {}),
    ],
    "crossed cycles": [
        (None, None, [{3}], [{3}], {}, {0: (0, 3)}),
        (3, 0, [{4}], [{4}], {}, {}),
        (4, 0, [{5}], [{5}], {}, {}),
        (5, 0, [{1}], [{1}], {}, {}),
        (1, 0, [{2}], [set(), {2}], {}, {}),
        (2, 1, [{0}, {0}], [{0}], {}, {0: (12, 0)}),
        (0, 0, [{3, 13}], [{3}, {13}], {0: (0, 3)}, {}),
        (13, 1, [set(), {14}], [{14}], {}, {}),
        (14, 0, [{15}], [{15}], {}, {}),
        (15, 0, [{11}], [{11}], {}, {}),
        (11, 0, [{12}], [{12}], {}, {}),
        (12, 0, [{0}], [{0}], {0: (12, 0)}, {})
    ],
    "complex cycles": [
        (None, None, [{4}], [set(), {4}], {}, {0: (3, 4)}),
        (4, 1, [{6}, {6}], [set(), {6}], {}, {0: (5, 6)}),
        (6, 1, [{1}, {1}], [set(), {1}], {}, {0: (2, 1)}),
        (1, 1, [{2}, {2}], [{2}, set()], {}, {0: (0, 2)}),
        (2, 0, [{1, 3}, {3}], [set(), {1}, {3}], {1: (2, 1)}, {1: (7, 3)}),
        (3, 2, [{5}, set(), {4, 5}], [{5}, {4}], {1: (3, 4)}, {0: (9, 5)}),
        (5, 0, [{6, 7}, set()], [{6}, {7}], {0: (5, 6)}, {}),
        (7, 1, [set(), {3, 8, 9}], [{8}, {3}, {9}], {1: (7, 3)}, {}),
        (9, 2, [{8}, set(), {0, 5, 8}], [{8}, {0}, {5}], {2: (9, 5)}, {}),
        (8, 0, [set(), {0}, set()], [{0}], {}, {}),
        (0, 0, [{2}], [{2}], {0: (0, 2)}, {}),
    ],
}.items())
def test_set_rows(key, expected):
    gl = _Layout(graph_from_key(key))
    _set_lines(gl)

    assert [row_as_tuple(gl.rows[v]) for v in gl.sequence] == expected


@pytest.mark.parametrize("key, expected", {
    "empty": set(),
    "single": set(),
    "simple": set(),
    "two paths": set(),
    "merged paths": set(),
    "path with loop": set(),
    "crossed paths": set(),
    "complex graph": set(),
    "self cycle": set(),
    "simple cycle": {(3, 0)},
    "starting cycle": {(3, 0)},
    "ending cycle": {(5, 2)},
    "crossed cycles": {(0, 3), (12, 0)},
    "complex cycles": {(3, 4), (5, 6), (2, 1), (0, 2), (7, 3), (9, 5)},
}.items())
def test_cycles(key, expected):
    gl = _Layout(graph_from_key(key))
    _set_lines(gl)

    assert gl.cycles == expected


def test_no_rearrange(complex_layout):
    row = complex_layout.rows[3]

    row.rearrange(list(range(3)))

    assert row.previous.end == [set(), {1}, {3}]
    assert row.start == [{5}, set(), {4, 5}]
    assert row.previous.cycles_start == {1: (2, 1)}
    assert row.cycles_end == {0: (9, 5)}


def test_rearrange(complex_layout):
    row = complex_layout.rows[3]

    row.rearrange([2, 0, 1])

    assert row.previous.end == [{3}, set(), {1}]
    assert row.start == [{4, 5}, {5}, set()]
    assert row.previous.cycles_start == {2: (2, 1)}
    assert row.cycles_end == {1: (9, 5)}


def test_rearrange_wrong_len(complex_layout):
    row = complex_layout.rows[3]

    message = "New order .+ is not a permutation"
    with pytest.raises(ValueError, match=message):
        row.rearrange([0, 1])


def test_rearrange_not_permutation(complex_layout):
    row = complex_layout.rows[3]

    message = "New order .+ is not a permutation"
    with pytest.raises(ValueError, match=message):
        row.rearrange([0, 1, 1])


def test_rearrange_mismatch(complex_layout):
    row = complex_layout.rows[3]
    del row.start[-1]

    message = "do not have the same number of columns"
    with pytest.raises(LayoutError, match=message):
        row.rearrange([0, 1, 1])


@pytest.mark.parametrize("start, end, expected", [
    ([], [], set()),
    ([{1}, {2}], [{1}, {2}], {(0, 0), (1, 1)}),
    ([{1}, {1}, {2}], [{2}, {1}], {(0, 1), (1, 1), (2, 0)}),
    ([{2, 3}, {2, 3}], [{2}, {3}], {(0, 0), (0, 1), (1, 0), (1, 1)}),
], ids=repr)
def test_draw_paths_between(start, end, expected):
    assert _draw_paths_between(start, end) == expected


@pytest.mark.parametrize("start, end, expected", [
    ([], [], 0),
    ([{1}, {2}], [{1}, {2}], 0),
    ([{1}, {1}, {2}], [{2}, {1}], 2),
    ([{2, 3}, {2, 3}], [{2}, {3}], 1),
], ids=repr)
def test_count_crossings(start, end, expected):
    assert _count_crossings(start, end) == expected


@pytest.mark.parametrize("key, expected", {
    "empty": 0,
    "single": 0,
    "simple": 0,
    "crossed paths": 1,
    "complex graph": 3,
    "crossed cycles": 0,
    "complex cycles": 0,
}.items())
def test_cycles(key, expected):
    gl = _Layout(graph_from_key(key))
    _set_lines(gl)

    assert _count_all_crossings(gl) == expected


@pytest.mark.parametrize("collection, expected", [
    ([], -1),
    ([0, 1, 2, 3, 4], 2),
    ([0, 1, 2, 3, 4, 5], 2.5)
], ids=repr)
def test_median(collection, expected):
    assert _median(collection) == expected


@pytest.mark.parametrize("key, expected", {
    "empty": [],
    "single": [(0, 0, [])],
    "simple": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, 0, None)]),
        (4, 0, []),
    ],
    "two paths": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, []),
        (10, 0, [(0, 0, 0, None)]),
        (11, 0, [(0, 0, 0, None)]),
        (12, 0, []),
    ],
    "merged paths": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 1, [(0, 0, 0, None), (1, 0, 0, None)]),
        (4, 0, [(0, 0, 0, None)]),
        (5, 0, [(0, 0, 0, None)]),
        (6, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (7, 1, [(0, 0, 0, None)]),
        (8, 0, [(0, 0, 0, None)]),
        (9, 0, []),
    ],
    "path with loop": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (3, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (4, 1, [(0, 0, 0, None), (1, 0, 0, None)]),
        (5, 0, [(0, 0, 0, None)]),
        (6, 0, [(0, 0, 0, None)]),
        (7, 0, []),
    ],
    "crossed paths": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (2, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (3, 1, [(0, 0, 0, None), (0, 1, 0, None), (1, 0, 0, None),
                (1, 1, 0, None)]),
        (4, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (5, 0, [(0, 0, 0, None), (1, 0, 0, None)]),
        (6, 0, [(0, 0, 0, None)]),
        (7, 0, []),
    ],
    "complex graph": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (2, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (3, 1, [(0, 0, 0, None), (1, 1, 0, None), (1, 2, 0, None)]),
        (4, 2, [(0, 0, 0, None), (0, 3, 0, None), (1, 1, 0, None),
                (2, 2, 0, None), (2, 3, 0, None)]),
        (5, 3, [(0, 0, 0, None), (1, 1, 0, None), (2, 2, 0, None),
                (3, 1, 0, None), (3, 3, 0, None)]),
        (6, 3, [(0, 0, 0, None), (1, 1, 0, None), (2, 2, 0, None)]),
        (7, 1, [(0, 0, 0, None), (1, 1, 0, None), (2, 1, 0, None)]),
        (8, 1, [(0, 0, 0, None), (1, 0, 0, None)]),
        (9, 0, [(0, 0, 0, None)]),
        (10, 0, []),
    ],
    "self cycle": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, []),
    ],
    "simple cycle": [
        (None, None, [(0, 0, 1, 3)]),
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, -1, 0)]),
    ],
    "starting cycle": [
        (None, None, [(0, 0, 1, 3)]),
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, -1, 0), (0, 1, 0, None)]),
        (4, 1, [(1, 0, 0, None)]),
        (5, 0, []),
    ],
    "ending cycle": [
        (0, 0, [(0, 1, 0, None)]),
        (1, 1, [(0, 0, 1, 5), (1, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, 0, None)]),
        (4, 0, [(0, 0, 0, None)]),
        (5, 0, [(0, 0, -1, 2)]),
    ],
    "crossed cycles": [
        (None, None, [(0, 0, 1, 0)]),
        (3, 0, [(0, 0, 0, None)]),
        (4, 0, [(0, 0, 0, None)]),
        (5, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 1, 0, None)]),
        (2, 1, [(0, 0, 1, 12), (1, 0, 0, None)]),
        (0, 0, [(0, 0, -1, 3), (0, 1, 0, None)]),
        (13, 1, [(1, 0, 0, None)]),
        (14, 0, [(0, 0, 0, None)]),
        (15, 0, [(0, 0, 0, None)]),
        (11, 0, [(0, 0, 0, None)]),
        (12, 0, [(0, 0, -1, 0)]),
    ],
    "complex cycles": [
        (None, None, [(0, 1, 1, 3)]),
        (4, 1, [(0, 1, 1, 5), (1, 1, 0, None)]),
        (6, 1, [(0, 1, 1, 2), (1, 1, 0, None)]),
        (1, 1, [(0, 0, 1, 0), (1, 0, 0, None)]),
        (2, 0, [(0, 1, -1, 1), (0, 2, 0, None), (1, 2, 1, 7)]),
        (3, 2, [(0, 0, 1, 9), (2, 0, 0, None), (2, 1, -1, 4)]),
        (5, 0, [(0, 0, -1, 6), (0, 1, 0, None)]),
        (7, 1, [(1, 0, 0, None), (1, 1, -1, 3), (1, 2, 0, None)]),
        (9, 2, [(0, 0, 0, None), (2, 0, 0, None), (2, 1, 0, None),
                (2, 2, -1, 5)]),
        (8, 0, [(1, 0, 0, None)]),
        (0, 0, [(0, 0, -1, 2)]),
    ],
}.items())
def test_graph_draw_before_order(key, expected):
    assert draw_graph(graph_from_key(key), order=False) == expected


@pytest.mark.parametrize("key, expected", {
    "empty": [],
    "single": [(0, 0, [])],
    "simple": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, 0, None)]),
        (4, 0, []),
    ],
    "two paths": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, []),
        (10, 0, [(0, 0, 0, None)]),
        (11, 0, [(0, 0, 0, None)]),
        (12, 0, []),
    ],
    "merged paths": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 1, [(0, 0, 0, None), (1, 0, 0, None)]),
        (4, 0, [(0, 0, 0, None)]),
        (5, 0, [(0, 0, 0, None)]),
        (6, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (7, 1, [(0, 0, 0, None)]),
        (8, 0, [(0, 0, 0, None)]),
        (9, 0, []),
    ],
    "path with loop": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (3, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (4, 1, [(0, 0, 0, None), (1, 0, 0, None)]),
        (5, 0, [(0, 0, 0, None)]),
        (6, 0, [(0, 0, 0, None)]),
        (7, 0, []),
    ],
    "crossed paths": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (2, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (3, 1, [(0, 0, 0, None), (0, 1, 0, None), (1, 0, 0, None),
                (1, 1, 0, None)]),
        (4, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (5, 0, [(0, 0, 0, None), (1, 0, 0, None)]),
        (6, 0, [(0, 0, 0, None)]),
        (7, 0, []),
    ],
    "complex graph": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None), (0, 1, 0, None)]),
        (2, 1, [(0, 0, 0, None), (1, 1, 0, None)]),
        (3, 1, [(0, 0, 0, None), (1, 1, 0, None), (1, 2, 0, None)]),
        (4, 2, [(0, 0, 0, None), (0, 2, 0, None), (1, 1, 0, None),
                (2, 2, 0, None), (2, 3, 0, None)]),
        (5, 2, [(0, 0, 0, None), (1, 1, 0, None), (2, 1, 0, None),
                (2, 2, 0, None), (3, 3, 0, None)]),
        (6, 2, [(0, 0, 0, None), (1, 1, 0, None), (3, 2, 0, None)]),
        (7, 1, [(0, 0, 0, None), (1, 1, 0, None), (2, 1, 0, None)]),
        (8, 1, [(0, 0, 0, None), (1, 0, 0, None)]),
        (9, 0, [(0, 0, 0, None)]),
        (10, 0, []),
    ],
    "self cycle": [
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, []),
    ],
    "simple cycle": [
        (None, None, [(0, 0, 1, 3)]),
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, -1, 0)]),
    ],
    "starting cycle": [
        (None, None, [(0, 0, 1, 3)]),
        (0, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, -1, 0), (0, 1, 0, None)]),
        (4, 1, [(1, 0, 0, None)]),
        (5, 0, []),
    ],
    "ending cycle": [
        (0, 0, [(0, 1, 0, None)]),
        (1, 1, [(0, 0, 1, 5), (1, 0, 0, None)]),
        (2, 0, [(0, 0, 0, None)]),
        (3, 0, [(0, 0, 0, None)]),
        (4, 0, [(0, 0, 0, None)]),
        (5, 0, [(0, 0, -1, 2)]),
    ],
    "crossed cycles": [
        (None, None, [(0, 0, 1, 0)]),
        (3, 0, [(0, 0, 0, None)]),
        (4, 0, [(0, 0, 0, None)]),
        (5, 0, [(0, 0, 0, None)]),
        (1, 0, [(0, 1, 0, None)]),
        (2, 1, [(0, 0, 1, 12), (1, 0, 0, None)]),
        (0, 0, [(0, 0, -1, 3), (0, 1, 0, None)]),
        (13, 1, [(1, 0, 0, None)]),
        (14, 0, [(0, 0, 0, None)]),
        (15, 0, [(0, 0, 0, None)]),
        (11, 0, [(0, 0, 0, None)]),
        (12, 0, [(0, 0, -1, 0)]),
    ],
    "complex cycles": [
        (None, None, [(0, 1, 1, 3)]),
        (4, 1, [(0, 1, 1, 5), (1, 1, 0, None)]),
        (6, 1, [(0, 1, 1, 2), (1, 1, 0, None)]),
        (1, 1, [(0, 0, 1, 0), (1, 0, 0, None)]),
        (2, 0, [(0, 1, -1, 1), (0, 2, 0, None), (1, 2, 1, 7)]),
        (3, 2, [(0, 0, 1, 9), (2, 0, 0, None), (2, 1, -1, 4)]),
        (5, 0, [(0, 0, -1, 6), (0, 1, 0, None)]),
        (7, 1, [(1, 0, 0, None), (1, 1, -1, 3), (1, 2, 0, None)]),
        (9, 2, [(0, 0, 0, None), (2, 0, 0, None), (2, 1, 0, None),
                (2, 2, -1, 5)]),
        (8, 0, [(1, 0, 0, None)]),
        (0, 0, [(0, 0, -1, 2)]),
    ],
}.items())
def test_graph_draw_after_order(key, expected):
    assert draw_graph(graph_from_key(key), order=True) == expected


def test_limit_not_hit(complex_graph):
    complex_graph.draw()
    complex_graph.draw(max_columns=4)


def test_limit_hit(complex_graph):
    with pytest.raises(MaxColumnError):
        complex_graph.draw(max_columns=1)
