"""
Testing the graph module for service diagrams.
"""
import unittest

from nextbus.graph import Path, Graph


class PathTests(unittest.TestCase):
    """ Testing the Path class. """
    def setUp(self):
        self.path = Path(range(10))
        self.cycle = Path(list(range(10)) + [0])

    def tearDown(self):
        del self.path

    def test_graph_init(self):
        p0 = Path([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        p1 = Path()
        p1._v = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        self.assertEqual(self.path, p0)
        self.assertEqual(self.path, p1)

    def test_graph_edges(self):
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8),
                 (8, 9)]
        self.assertEqual(self.path.edges, edges)

    def test_graph_not_cyclic(self):
        self.assertFalse(self.path.cyclic)

    def test_graph_cyclic(self):
        self.assertTrue(self.cycle.cyclic)

    def test_graph_make_not_cyclic(self):
        self.assertEqual(self.path.make_acyclic(), self.path)

    def test_graph_make_cyclic(self):
        self.assertEqual(self.cycle.make_acyclic(), self.path)

    def test_graph_prepend(self):
        self.path.prepend(-1)
        self.assertTrue(self.path._v, list(range(-1, 10)))

    def test_graph_append(self):
        self.path.append(10)
        self.assertTrue(self.path._v, list(range(1, 11)))

    def test_graph_prepend_with(self):
        p1 = self.path.prepend_with(-1)
        self.assertTrue(p1._v, list(range(-1, 10)))

    def test_graph_append_with(self):
        p1 = self.path.append_with(10)
        self.assertTrue(p1._v, list(range(1, 11)))

    def test_graph_empty(self):
        path = Path()
        self.assertEqual(len(path), 0)
        self.assertEqual(path.cyclic, False)
        self.assertEqual(path.edges, [])
        self.assertEqual(path.make_acyclic(), path)

    def test_graph_split_left(self):
        self.assertEqual(self.path.split((0, 1)), [Path(range(1, 10))])

    def test_graph_split_right(self):
        self.assertEqual(self.path.split((8, 9)), [Path(range(9))])

    def test_graph_split_middle(self):
        self.assertEqual(self.path.split((4, 5)),
                         [Path(range(5)), Path(range(5, 10))])

    def test_graph_wrong_edge(self):
        with self.assertRaises(KeyError):
            self.path.split((-1, 0))


class GraphTests(unittest.TestCase):
    """ Testing the Graph class. """
    def assertResultsEqual(self, d1, d2):
        """ Compare results for multiple graphs in the form of dictionaries
            which are assumed to have the same keys.
        """
        if d1.keys() != d2.keys():
            raise ValueError("Keys %r for the first dictionary are not equal "
                             "to the second dictionary keys %r" %
                             (d1.keys(), d2.keys()))
        for k in d1:
            with self.subTest(test=k):
                self.assertEqual(d1[k], d2[k])

    def setUp(self):
        # Empty
        self.empty = Graph()
        # Single vertex
        self.single = Graph(singles=[0])
        # Simple path
        self.simple = Graph([(0, 1), (1, 2), (2, 3), (3, 4)])
        # Two distinct paths
        self.two_paths = Graph([(0, 1), (1, 2), (2, 3), (10, 11), (11, 12)])
        # Two paths, crossed
        self.merge = Graph([(0, 1), (1, 2), (2, 4), (3, 4), (4, 5), (5, 6),
                            (6, 7), (6, 8), (8, 9)])
        # Path with a longer loop
        self.loop = Graph([(0, 1), (1, 2), (2, 3), (2, 5), (3, 4), (4, 5),
                           (5, 6), (6, 7)])
        # Path with a loop and a crossover
        self.cross = Graph([(0, 1), (1, 2), (1, 4), (1, 5), (2, 3), (3, 4),
                            (3, 5), (4, 6), (5, 6), (6, 7)])
        # Path with a self-cycle
        self.self_cycle = Graph([(0, 1), (1, 2), (2, 2), (2, 3)])
        # Simple cycle
        self.cycle = Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
        # Path starting with a cycle (sources = 0, sinks > 0)
        self.cycle_start = Graph([(0, 1), (1, 2), (2, 3), (3, 0), (3, 4),
                                  (4, 5)])
        # Path ending with a cycle (sources > 0, sinks = 0)
        self.cycle_end = Graph([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 2)])
        # Pair of cycles, crossed (like infinity symbol)
        self.two_cycles = Graph([(1, 2), (2, 0), (0, 3), (3, 4), (4, 5), (5, 1),
                                 (11, 12), (12, 0), (0, 13), (13, 14), (14, 15),
                                 (15, 11)])
        # All graphs in a dict
        self.graphs = {
            "empty": self.empty,
            "single": self.single,
            "simple": self.simple,
            "two paths": self.two_paths,
            "merged paths": self.merge,
            "path with loop": self.loop,
            "crossed paths": self.cross,
            "self cycle": self.self_cycle,
            "simple cycle": self.cycle,
            "starting cycle": self.cycle_start,
            "ending cycle": self.cycle_end,
            "crossed cycles": self.two_cycles
        }

    def tearDown(self):
        del self.graphs
        del (self.empty, self.single, self.simple, self.two_paths, self.merge,
             self.loop, self.cross, self.self_cycle, self.cycle,
             self.cycle_start, self.cycle_end, self.two_cycles)

    def test_graph_len(self):
        self.assertEqual(len(self.merge), 10)

    def test_graph_contains(self):
        self.assertTrue(0 in self.merge)

    def test_graph_not_contains(self):
        self.assertTrue(10 not in self.merge)

    def test_graph_equals(self):
        g = Graph([(0, 1), (1, 2), (2, 3), (3, 4)])
        self.assertTrue(self.simple == g)

    def test_graph_not_equals(self):
        g = Graph([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])
        self.assertTrue(self.simple != g)

    def test_graph_equals_wrong_type(self):
        g = [(0, 1), (1, 2), (2, 3), (3, 4)]
        self.assertTrue(self.simple != g)

    def test_graph_adj(self):
        adjacency_lists = {
            "empty": {},
            "single": {0: set()},
            "simple": {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: set()},
            "two paths": {0: {1}, 1: {2}, 2: {3}, 3: set(), 10: {11}, 11: {12},
                          12: set()},
            "merged paths": {0: {1}, 1: {2}, 2: {4}, 3: {4}, 4: {5}, 5: {6},
                              6: {7, 8}, 7: set(), 8: {9}, 9: set()},
            "path with loop": {0: {1}, 1: {2}, 2: {3, 5}, 3: {4}, 4: {5},
                               5: {6}, 6: {7}, 7: set()},
            "crossed paths": {0: {1}, 1: {2, 4, 5}, 2: {3}, 3: {4, 5}, 4: {6},
                              5: {6}, 6: {7}, 7: set()},
            "self cycle": {0: {1}, 1: {2}, 2: {2, 3}, 3: set()},
            "simple cycle": {0: {1}, 1: {2}, 2: {3}, 3: {0}},
            "starting cycle": {0: {1}, 1: {2}, 2: {3}, 3: {0, 4}, 4: {5},
                               5: set()},
            "ending cycle": {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: {5}, 5: {2}},
            "crossed cycles": {0: {3, 13}, 1: {2}, 2: {0}, 3: {4}, 4: {5},
                               5: {1}, 11: {12}, 12: {0}, 13: {14}, 14: {15},
                               15: {11}}
        }
        self.assertResultsEqual({n: g.adj for n, g in self.graphs.items()},
                                adjacency_lists)

    def test_graph_heads(self):
        graph_heads = {
            "empty": set(),
            "single": set(),
            "simple": {0, 1, 2, 3},
            "two paths": {0, 1, 2, 10, 11},
            "merged paths": {0, 1, 2, 3, 4, 5, 6, 8},
            "path with loop": {0, 1, 2, 3, 4, 5, 6},
            "crossed paths": {0, 1, 2, 3, 4, 5, 6},
            "self cycle": {0, 1, 2},
            "simple cycle": {0, 1, 2, 3},
            "starting cycle": {0, 1, 2, 3, 4},
            "ending cycle": {0, 1, 2, 3, 4, 5},
            "crossed cycles": {0, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15}
        }
        self.assertResultsEqual({n: g.heads for n, g in self.graphs.items()},
                                graph_heads)

    def test_graph_tails(self):
        graph_tails = {
            "empty": set(),
            "single": set(),
            "simple": {1, 2, 3, 4},
            "two paths": {1, 2, 3, 11, 12},
            "merged paths": {1, 2, 4, 5, 6, 7, 8, 9},
            "path with loop": {1, 2, 3, 4, 5, 6, 7},
            "crossed paths": {1, 2, 3, 4, 5, 6, 7},
            "self cycle": {1, 2, 3},
            "simple cycle": {0, 1, 2, 3},
            "starting cycle": {0, 1, 2, 3, 4, 5},
            "ending cycle": {1, 2, 3, 4, 5},
            "crossed cycles": {0, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15}
        }
        self.assertResultsEqual({n: g.tails for n, g in self.graphs.items()},
                                graph_tails)

    def test_graph_sources(self):
        graph_sources = {
            "empty": set(),
            "single": set(),
            "simple": {0},
            "two paths": {0, 10},
            "merged paths": {0, 3},
            "path with loop": {0},
            "crossed paths": {0},
            "self cycle": {0},
            "simple cycle": set(),
            "starting cycle": set(),
            "ending cycle": {0},
            "crossed cycles": set()
        }
        self.assertResultsEqual({n: g.sources for n, g in self.graphs.items()},
                                graph_sources)

    def test_graph_sinks(self):
        graph_sinks = {
            "empty": set(),
            "single": set(),
            "simple": {4},
            "two paths": {3, 12},
            "merged paths": {7, 9},
            "path with loop": {7},
            "crossed paths": {7},
            "self cycle": {3},
            "simple cycle": set(),
            "starting cycle": {5},
            "ending cycle": set(),
            "crossed cycles": set()
        }
        self.assertResultsEqual({n: g.sinks for n, g in self.graphs.items()},
                                graph_sinks)

    def test_graph_edges(self):
        graph_edges = {
            "empty": set(),
            "single": set(),
            "simple": {(0, 1), (1, 2), (2, 3), (3, 4)},
            "two paths": {(0, 1), (1, 2), (2, 3), (10, 11), (11, 12)},
            "merged paths": {(0, 1), (1, 2), (2, 4), (3, 4), (3, 4), (4, 5),
                              (5, 6), (6, 7), (6, 8), (8, 9)},
            "path with loop": {(0, 1), (1, 2), (2, 3), (2, 5), (3, 4), (4, 5),
                               (5, 6), (6, 7)},
            "crossed paths": {(0, 1), (1, 2), (1, 4), (1, 5), (2, 3), (3, 4),
                              (3, 5), (4, 6), (5, 6), (6, 7)},
            "self cycle": {(0, 1), (1, 2), (2, 2), (2, 3)},
            "simple cycle": {(0, 1), (1, 2), (2, 3), (3, 0)},
            "starting cycle": {(0, 1), (1, 2), (2, 3), (3, 0), (3, 4), (4, 5)},
            "ending cycle": {(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 2)},
            "crossed cycles": {(1, 2), (2, 0), (0, 3), (3, 4), (4, 5), (5, 1),
                               (11, 12), (12, 0), (0, 13), (13, 14), (14, 15),
                               (15, 11)}
        }
        self.assertResultsEqual({n: g.edges for n, g in self.graphs.items()},
                                graph_edges)

    def test_graph_vertices(self):
        graph_vertices = {
            "empty": set(),
            "single": {0},
            "simple": {0, 1, 2, 3, 4},
            "two paths": {0, 1, 2, 3, 10, 11, 12},
            "merged paths": {0, 1, 2, 3, 4, 5, 6, 7, 8, 9},
            "path with loop": {0, 1, 2, 3, 4, 5, 6, 7},
            "crossed paths": {0, 1, 2, 3, 4, 5, 6, 7},
            "self cycle": {0, 1, 2, 3},
            "simple cycle": {0, 1, 2, 3},
            "starting cycle": {0, 1, 2, 3, 4, 5},
            "ending cycle": {0, 1, 2, 3, 4, 5},
            "crossed cycles": {0, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15}
        }
        self.assertResultsEqual({n: g.vertices for n, g in self.graphs.items()},
                                graph_vertices)

    def test_graph_isolated_vertices(self):
        graph_isolated_vertices = {
            "empty": set(),
            "single": {0},
            "simple": set()
        }
        result = {
            "empty": self.empty.isolated,
            "single": self.single.isolated,
            "simple": self.simple.isolated
        }
        self.assertResultsEqual(result, graph_isolated_vertices)

    def test_graph_preceding(self):
        result = {
            "start": self.merge.preceding(0),
            "converges": self.merge.preceding(4),
            "diverges": self.merge.preceding(6),
            "end": self.merge.preceding(9),
        }
        expected = {
            "start": set(),
            "converges": {2, 3},
            "diverges": {5},
            "end": {8}
        }
        self.assertResultsEqual(result, expected)

    def test_graph_following(self):
        result = {
            "start": self.merge.following(0),
            "converges": self.merge.following(4),
            "diverges": self.merge.following(6),
            "end": self.merge.following(9),
        }
        expected = {
            "start": {1},
            "converges": {5},
            "diverges": {7, 8},
            "end": set()
        }
        self.assertResultsEqual(result, expected)

    def test_graph_incoming(self):
        result = {
            "start": self.merge.incoming(0),
            "converges": self.merge.incoming(4),
            "diverges": self.merge.incoming(6),
            "end": self.merge.incoming(9),
        }
        expected = {
            "start": set(),
            "converges": {(2, 4), (3, 4)},
            "diverges": {(5, 6)},
            "end": {(8, 9)}
        }
        self.assertResultsEqual(result, expected)

    def test_graph_outgoing(self):
        result = {
            "start": self.merge.outgoing(0),
            "converges": self.merge.outgoing(4),
            "diverges": self.merge.outgoing(6),
            "end": self.merge.outgoing(9),
        }
        expected = {
            "start": {(0, 1)},
            "converges": {(4, 5)},
            "diverges": {(6, 7), (6, 8)},
            "end": set()
        }
        self.assertResultsEqual(result, expected)

    def test_graph_preceding_not_exists(self):
        with self.assertRaises(KeyError):
            self.simple.preceding(10)

    def test_graph_following_wrong_vertex(self):
        with self.assertRaises(KeyError):
            self.simple.following(10)

    def test_graph_incoming_wrong_vertex(self):
        with self.assertRaises(KeyError):
            self.simple.incoming(10)

    def test_graph_outgoing_wrong_vertex(self):
        with self.assertRaises(KeyError):
            self.simple.outgoing(10)

    def test_add_edge(self):
        self.simple.add_edge(4, 5)
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: {5}, 5: set()})

    def test_add_vertex(self):
        self.empty.add_vertex(0)
        self.assertEqual(self.empty, self.single)

    def test_remove_vertex(self):
        self.simple.remove_vertex(2)
        self.assertEqual(self.simple.adj, {0: {1}, 1: set(), 3: {4}, 4: set()})

    def test_remove_vertex_not_exists(self):
        with self.assertRaises(KeyError):
            self.simple.remove_vertex(10)

    def test_remove_edge(self):
        self.simple.remove_edge(2, 3)
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: set(), 3: {4}, 4: set()})

    def test_remove_edge_vertex(self):
        self.simple.remove_edge(3, 4, delete=True)
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: {3}, 3: set()})

    def test_remove_edge_not_vertex(self):
        self.simple.remove_edge(3, 4, delete=False)
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: {3}, 3: set(), 4: set()})

    def test_remove_wrong_edge(self):
        with self.assertRaises(KeyError):
            self.simple.remove_edge(9, 10)

    def test_add_path(self):
        self.simple.add_path(Path([-3, -2, -1, 0]))
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: set(), -3: {-2},
                          -2: {-1}, -1: {0}})

    def test_add_path_sequence(self):
        self.simple.add_path([(-3, -2), (-2, -1), (-1, 0)])
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: {3}, 3: {4}, 4: set(), -3: {-2},
                          -2: {-1}, -1: {0}})

    def test_add_path_partial(self):
        self.simple.add_path(Path([10, 11, 2, 3, 14, 15, 16]))
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: {3}, 3: {4, 14}, 4: set(),
                          10: {11}, 11: {2}, 14: {15}, 15: {16}, 16: set()})

    def test_remove_path(self):
        self.simple.remove_path(Path([2, 3, 4]))
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: set()})

    def test_remove_path_no_delete(self):
        self.simple.remove_path(Path([2, 3, 4]), delete=False)
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: set(), 3: set(), 4: set()})

    def test_remove_path_sequence(self):
        self.simple.remove_path([(2, 3), (3, 4)])
        self.assertEqual(self.simple.adj,
                         {0: {1}, 1: {2}, 2: set()})

    def test_remove_path_wrong_edge(self):
        num_vertices = len(self.simple)
        msg = "Edge \(4, 5\) does not exist in graph"
        with self.assertRaisesRegex(ValueError, msg):
            self.simple.remove_path([(2, 3), (3, 4), (4, 5)])
        self.assertEqual(len(self.simple), num_vertices)

    def test_split_graph_empty(self):
        self.assertEqual(self.empty.split(), [Graph()])

    def test_split_graph_single(self):
        self.assertEqual(self.single.split(), [Graph(singles=[0])])

    def test_split_graph_disconnected(self):
        g0 = Graph([(0, 1), (1, 2), (2, 3)])
        g1 = Graph([(10, 11), (11, 12)])
        g_split = self.two_paths.split()
        self.assertTrue(len(g_split) == 2 and g0 in g_split and g1 in g_split)

    def test_split_graph_connected(self):
        g_split = self.simple.split()
        self.assertTrue(g_split, [self.simple])

    def test_copy_simple(self):
        g = self.simple.copy()
        self.assertTrue(g == self.simple and g is not self.simple)

    def test_copy_isolated(self):
        g = self.single.copy()
        self.assertTrue(g == self.single and g is not self.single)

    def test_clean_copy(self):
        g = self.self_cycle.clean_copy()
        self.assertEqual(Graph([(0, 1), (1, 2), (2, 3)]), g)

    def test_copy_clean_already(self):
        g = self.simple.clean_copy()
        self.assertEqual(g, self.simple)

    def test_search_paths_start_zero(self):
        expected_paths = {
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
        }

        del self.graphs["empty"]  # Don't need empty graph for this
        self.assertResultsEqual(
            {n: g.search_paths(0) for n, g in self.graphs.items()},
            expected_paths
        )

    def test_graph_diameter(self):
        graph_diameters = {
            "empty": Path(),
            "single": Path(),
            "simple": Path([0, 1, 2, 3, 4]),
            "two paths": Path([0, 1, 2, 3]),
            "merged paths": Path([0, 1, 2, 4, 5, 6, 8, 9]),
            "path with loop": Path([0, 1, 2, 5, 6, 7]),
            "crossed paths": Path([0, 1, 4, 6, 7]),
            "self cycle": Path([0, 1, 2, 3]),
            "simple cycle": Path([0, 1, 2, 3, 0]),
            "starting cycle": Path([0, 1, 2, 3, 4, 5]),
            "ending cycle": Path([0, 1, 2, 3, 4, 5]),
            "crossed cycles": Path([3, 4, 5, 1, 2, 0, 13, 14, 15, 11, 12]),
        }
        self.assertResultsEqual(
            {n: g.diameter() for n, g in self.graphs.items()},
            graph_diameters
        )

    def test_graph_paths(self):
        graph_paths = {
            "empty": [],
            "single": [],
            "simple": [Path([0, 1, 2, 3, 4])],
            "two paths": [Path([0, 1, 2, 3]), Path([10, 11, 12])],
            "merged paths": [Path([0, 1, 2, 4, 5, 6, 8, 9]), Path([3, 4]),
                              Path([6, 7])],
            "path with loop": [Path([0, 1, 2, 5, 6, 7]), Path([2, 3, 4, 5])],
            "crossed paths": [Path([0, 1, 4, 6, 7]), Path([1, 2, 3, 4]),
                              Path([1, 5, 6]), Path([3, 5])],
            "self cycle": [Path([0, 1, 2, 3])],
            "simple cycle": [Path([0, 1, 2, 3, 0])],
            "starting cycle": [Path([0, 1, 2, 3, 4, 5]), Path([3, 0])],
            "ending cycle": [Path([0, 1, 2, 3, 4, 5]), Path([5, 2])],
            "crossed cycles": [Path([0, 3]),
                               Path([3, 4, 5, 1, 2, 0, 13, 14, 15, 11, 12]),
                               Path([12, 0])],
        }
        self.assertResultsEqual(
            {n: sorted(g.paths(), key=tuple) for n, g in
             self.graphs.items()},
            graph_paths
        )

    def test_graph_sequence(self):
        graph_seq = {
            "empty": [],
            "single": [0],
            "simple": [0, 1, 2, 3, 4],
            "two paths": [0, 1, 2, 3, 10, 11, 12],
            "merged paths": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            "path with loop": [0, 1, 2, 3, 4, 5, 6, 7],
            "crossed paths": [0, 1, 2, 3, 5, 4, 6, 7],
            "self cycle": [0, 1, 2, 3],
            "simple cycle": [0, 1, 2, 3],
            "starting cycle": [0, 1, 2, 3, 4, 5],
            "ending cycle": [0, 1, 2, 3, 4, 5],
            "crossed cycles": [3, 4, 5, 1, 2, 0, 13, 14, 15, 11, 12],
        }
        self.assertResultsEqual(
            {n: g.sequence() for n, g in self.graphs.items()},
            graph_seq
        )
