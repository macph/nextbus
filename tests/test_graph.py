"""
Tests for service graphs.
"""
import unittest

from nextbus import graph
import utils


class VertexTests(unittest.TestCase):
    """ Testing Vertex. """
    def setUp(self):
        self.u = graph.Vertex(0, 1, 2)
        self.v = graph.Vertex(0, 1, 3)
        self.w = graph.Vertex(1, 2, 3)
        self.x = graph.Vertex(-1, 1, 2)

    def test_vertex(self):
        self.assertEqual((self.u.previous, self.u.current, self.u.next),
                         (0, 1, 2))

    def test_before_after(self):
        self.assertTrue(self.u.is_before(self.w))
        self.assertFalse(self.v.is_before(self.w))

        self.assertTrue(self.w.is_after(self.u))
        self.assertFalse(self.w.is_after(self.v))

    def test_share(self):
        self.assertTrue(self.u.share_preceding(self.v))
        self.assertFalse(self.u.share_preceding(self.x))

        self.assertTrue(self.u.share_following(self.x))
        self.assertFalse(self.v.share_following(self.w))


class GraphTests(unittest.TestCase):
    """ Testing Graph. """
    @staticmethod
    def _set(vertices):
        return {graph.Vertex(*v) for v in vertices}

    def setUp(self):
        # A DAG consisting of 3 disjoint graphs; one complex, one simple and
        # one with single vertex.
        self.vertices = [
            (14, 2, 1), (6, 7, None), (4, 5, 6), (2, 3, 4), (0, 1, 2),
            (10, 11, 4), (2, 1, 0), (None, 0, 1), (5, 6, 7), (1, 2, 3),
            (1, 0, None), (6, 8, None), (9, 10, 11), (0, 1, 9), (3, 4, 5),
            (1, 9, 10), (11, 4, 13), (13, 14, 2), (4, 13, 14), (5, 6, 8),
            (12, 5, 6), (10, 11, 12), (11, 12, 5), (None, 13, 14),
            (None, -1, None), (None, 15, 17), (None, 16, 17), (15, 17, 18),
            (16, 17, 18), (17, 18, None)
        ]
        self.graph = graph.Graph(self.vertices)
        self.cyclic = graph.Graph(self.vertices + [(13, 14, 9), (14, 9, 10)])

    def tearDown(self):
        del self.vertices

    def test_init_graph(self):
        g = graph.Graph()
        for v in self.vertices:
            g.add(v)

        self.assertEqual(self.graph, g)
        self.assertEqual(set(self.graph), self._set(self.vertices))

    def test_graph_null_vertex(self):
        g = graph.Graph()
        with self.assertRaisesRegex(ValueError, "cannot have a null current"):
            g.add((-1, None, 1))

    def test_graph_sources(self):
        sources = self._set([(None, 0, 1), (None, 13, 14), (None, -1, None),
                             (None, 15, 17), (None, 16, 17)])

        self.assertEqual(self.graph.sources(), sources)

    def test_graph_sinks(self):
        sinks = self._set([(6, 7, None), (1, 0, None), (6, 8, None),
                           (None, -1, None), (17, 18, None)])

        self.assertEqual(self.graph.sinks(), sinks)

    def test_graph_preceding(self):
        self.assertEqual(self.graph.preceding(graph.Vertex(1, 9, 10)),
                         self._set([(0, 1, 9)]))
        self.assertEqual(self.graph.preceding(graph.Vertex(None, 0, 1)), set())

    def test_graph_preceding_not_exists(self):
        with self.assertRaises(KeyError):
            self.graph.preceding(graph.Vertex(13, 14, 15))

    def test_graph_following(self):
        following = self._set([(10, 11, 4), (10, 11, 12)])

        self.assertEqual(self.graph.following(graph.Vertex(9, 10, 11)),
                         following)
        self.assertEqual(self.graph.following(graph.Vertex(6, 8, None)), set())

    def test_graph_following_not_exists(self):
        with self.assertRaises(KeyError):
            self.graph.following(graph.Vertex(13, 14, 15))

    def test_graph_split(self):
        graphs = self.graph.split()

        self.assertEqual({len(g) for g in graphs}, {24, 1, 5})

        union = graph.Graph()
        for g in graphs:
            union |= g
        self.assertEqual(self.graph, union)

        pairs = [(g, h) for g in graphs for h in graphs if h != g]
        self.assertTrue(all(g.isdisjoint(h) for g, h in pairs))

    def test_graph_split_cyclic(self):
        graphs = self.cyclic.split()

        self.assertEqual({len(g) for g in graphs}, {26, 1, 5})

    def test_graph_verify(self):
        self.graph.verify()

    def test_graph_verify_cyclic(self):
        with self.assertRaisesRegex(ValueError, "Path \[.+\] is cyclic."):
            self.cyclic.verify()

    def test_graph_invalid_preceding(self):
        self.graph.add((-2, -1, None))

        message = ("Preceding node of vertex <Vertex\(-2, -1, None\)> is not a "
                   "valid reference.")
        with self.assertRaisesRegex(ValueError, message):
            self.graph.verify()

    def test_graph_invalid_following(self):
        self.graph.add((None, -1, -2))

        message = ("Following node of vertex <Vertex\(None, -1, -2\)> is not a "
                   "valid reference.")
        with self.assertRaisesRegex(ValueError, message):
            self.graph.verify()

    def test_graph_sort(self):
        vertices = self.graph.sort()

        self.assertIn(graph.Vertex(None, 13, 14), self.graph)
        self.assertNotIn(graph.Vertex(None, 13, 14), vertices)

        self.assertLess(vertices.index(graph.Vertex(None, 0, 1)),
                        vertices.index(graph.Vertex(1, 0, None)))
        self.assertLess(vertices.index(graph.Vertex(9, 10, 11)),
                        vertices.index(graph.Vertex(5, 6, 8)))
        self.assertLess(vertices.index(graph.Vertex(9, 10, 11)),
                        vertices.index(graph.Vertex(13, 14, 2)))

    def test_graph_sort_cyclic(self):
        message = "Graph .+ has at least one cycle."
        with self.assertRaisesRegex(ValueError, message):
            self.cyclic.sort()
