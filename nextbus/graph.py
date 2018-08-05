"""
Draws a route graph for a service.
"""
import collections
import collections.abc as abc
import reprlib

from nextbus import db, models


class Vertex(collections.namedtuple("Vertex", "previous current next")):
    """ Vertex in a DAG, with preceding, current and following node labels. """
    def __repr__(self):
        nodes = [self.previous, self.current, self.next]
        return "<Vertex(%s)>" % ", ".join(map(reprlib.repr, nodes))

    def is_before(self, other):
        return (self.current == other.previous and
                self.next == other.current)

    def is_after(self, other):
        return (self.previous == other.current and
                self.current == other.next)

    def share_preceding(self, other):
        return (self.previous == other.previous and
                self.current == other.current)

    def share_following(self, other):
        return (self.current == other.current and
                self.next == other.next)


class Graph(abc.MutableSet):
    """ DAG using Vertex objects. """
    def __init__(self, vertices=()):
        self._v = set(map(self._convert, vertices))

    @reprlib.recursive_repr()
    def __repr__(self):
        return "<Graph(%s)>" % reprlib.repr(self._v)

    def __contains__(self, item):
        return item in self._v

    def __iter__(self):
        return iter(self._v)

    def __len__(self):
        return len(self._v)

    @staticmethod
    def _convert(vertex):
        """ Converts tuples to Vertex objects.
        """
        if isinstance(vertex, Vertex):
            new = vertex
        else:
            try:
                new = Vertex(*vertex)
            except TypeError as err:
                raise TypeError(
                    "Graphs only accept Vertex objects or tuples of length 3 "
                    "for preceding, current and following nodes."
                ) from err

        if new.current is None:
            raise ValueError("Vertex %r in a graph cannot have a null current "
                             "value." % (new,))

        return new

    def add(self, vertex):
        self._v.add(self._convert(vertex))

    def update(self, vertices):
        self._v.update(map(self._convert, vertices))

    def discard(self, vertex):
        self._v.discard(vertex)

    def preceding(self, vertex):
        """ Find all vertices directly preceding this vertex. """
        if vertex not in self:
            raise KeyError(vertex)

        return {v for v in self if v.is_before(vertex)}

    def following(self, vertex):
        """ Find all vertices directly following this vertex. """
        if vertex not in self:
            raise KeyError(vertex)

        return {v for v in self if v.is_after(vertex)}

    def sources(self):
        """ All vertices without preceding vertices. """
        return {v for v in self if v.previous is None}

    def sinks(self):
        """ All vertices without following vertices. """
        return {v for v in self if v.next is None}

    def split(self):
        """ Splits DAG into multiple disjoint graphs. """
        visited = {}

        for i, u in enumerate(self):
            if u in visited:
                continue
            visited[u] = i
            visited_local = set()
            to_search = collections.deque(self.following(u))

            while to_search:
                v = to_search.pop()
                if v in visited_local:
                    # Already found earlier in local tree; this is cyclic
                    continue
                visited_local.add(v)
                if v in visited:
                    # Set all vertices found in this path to new index
                    for w, k in visited.items():
                        if k == i:
                            visited[w] = visited[v]
                    i = visited[v]
                else:
                    visited[v] = i
                visited_local.add(v)
                to_search.extendleft(self.following(v))

        assert len(visited) == len(self)

        graphs = collections.defaultdict(Graph)
        for v, i in visited.items():
            graphs[i].add(v)

        return list(graphs.values())

    def _extend_path(self, vertex, lines, visited, _path=None):
        """ Helper function to create paths by iterating through graph. """
        visited.add(vertex)

        if _path is not None and vertex in _path:
            # Vertex already in path => Cyclic path
            lines.append(_path)
            return
        elif _path is not None:
            path = _path + [vertex]
        elif _path is None and vertex.previous is not None:
            # Start a new path and set first vertex's preceding node to None
            new = Vertex(None, vertex.current, vertex.next)
            if new in self:
                # This vertex already exists, use that instead
                return
            path = [new]
        else:
            path = [vertex]

        if vertex.next is None:
            lines.append(path)
            return

        if vertex in {v for v in visited
                      if v.share_following(vertex) and v != vertex}:
            # Merging with another path. Discard current vertex and
            # terminate previous vertex
            path = path[:-1]
            if not path:
                return
            last = path.pop(-1)
            new = Vertex(last.previous, last.current, None)
            path.append(new)
            lines.append(path)
            return

        following = self.following(vertex)
        if following - visited:
            self._extend_path(following.pop(), lines, visited, path)
        elif following:
            lines.append(path)
            return
        else:
            raise ValueError("Vertex %r has a non-null following node but "
                             "no matching vertices were found." % (vertex,))
        for v in following:
            self._extend_path(v, lines, visited)

    def lines(self):
        """ Splits graph into several distinct paths.

            :returns: List of current node values.
        """
        lines = []
        # Split into different graphs first
        graphs = self.split()
        if len(graphs) > 1:
            for g in graphs:
                new_lines = g.lines()
                if new_lines:
                    lines.extend(new_lines)
        else:
            visited = set()
            to_search = {u for u in self.sources() for v in self
                         if not u.share_following(v)}
            if not to_search:
                # Graph is connected and cyclic; enough to pick a single vertex
                to_search = list(self)[:1]
            for u in to_search:
                self._extend_path(u, lines, visited)

            assert visited == set(self)
            lines = [[v.current for v in l] for l in lines]

        return lines

    def verify(self):
        """ Checks all vertices have the correct references and is not cyclic.
        """
        visited = set()

        def search(vertex, _path=None):
            """ Searches through tree for any invalid vertices. """
            nonlocal visited

            path = [vertex] if _path is None else _path + [vertex]
            if path.count(vertex) > 1:
                raise ValueError("Path %r is cyclic." % path)

            if vertex in visited:
                return
            if vertex.previous is not None and not self.preceding(vertex):
                raise ValueError("Preceding node of vertex %r is not a valid "
                                 "reference." % (vertex,))
            if vertex.next is not None and not self.following(vertex):
                raise ValueError("Following node of vertex %r is not a valid "
                                 "reference." % (vertex,))

            visited.add(vertex)
            for v in self.following(vertex):
                search(v, path)

        for u in self:
            search(u)

    def sort(self):
        """ Returns a sorted list of vertices in topological order using Kahn's
            algorithm.
        """
        vertices = []
        not_visited = set(self)
        sources = collections.deque(self.sources())

        while sources:
            source = sources.pop()
            vertices.append(source)
            not_visited.remove(source)
            for v in self.following(source):
                if not self.preceding(v) - set(vertices):
                    sources.append(v)

        if not_visited:
            raise ValueError("Graph %r has at least one cycle." % self)

        # Any vertices with null preceding or following nodes are excluded if
        # they share other nodes with existing vertices
        for u in vertices:
            if (u.previous is None and
                    len({v for v in self if v.share_following(u)}) > 1):
                vertices.remove(u)
                continue
            if (u.next is None and
                    len({v for v in self if v.share_preceding(u)}) > 1):
                vertices.remove(u)

        return vertices


def _service_stops(code, direction=None, columns=None):
    """ Get dictionary of distinct stops for a service.

        :param code: Service code.
        :param direction: Groups journey patterns by direction.
        :param columns: If not None, load specified columns (ATCO code always
        selected regardless).
        :returns: Dictionary with ATCO codes as keys for stop point objects.
    """
    pairs = (
        db.session.query(models.JourneyLink.stop_point_ref,
                         models.JourneyPattern.direction)
        .join(models.JourneyPattern.links)
        .filter(models.JourneyPattern.service_ref == code)
    )

    if direction is not None:
        pairs = pairs.filter(models.JourneyPattern.direction == direction)

    pairs = pairs.subquery()
    stops = models.StopPoint.query
    if columns is not None:
        col = set(columns) | {"atco_code"}
        stops = stops.options(db.load_only(*tuple(col)))

    stops = (
        stops.distinct()
        .join(pairs, pairs.c.stop_point_ref == models.StopPoint.atco_code)
    )

    return {s.atco_code: s for s in stops.all()}


def _service_graph(code, direction=None):
    """ Get list of stops and their preceding and following stops for a service.

        :param code: Service code.
        :param direction: Groups journey patterns by direction.
    """
    stops = (
        db.session.query(
            db.func.lag(models.JourneyLink.stop_point_ref)
            .over(partition_by=models.JourneyPattern.id,
                  order_by=models.JourneyLink.sequence)
            .label("s0"),
            models.JourneyLink.stop_point_ref.label("s1"),
            db.func.lead(models.JourneyLink.stop_point_ref)
            .over(partition_by=models.JourneyPattern.id,
                  order_by=models.JourneyLink.sequence)
            .label("s2")
        )
        .select_from(models.JourneyPattern)
        .join(models.JourneyPattern.links)
        .filter(models.JourneyPattern.service_ref == code)
    )

    if direction is not None:
        stops = stops.filter(models.JourneyPattern.direction == direction)

    return Graph(stops.all())


def service_stops(code, direction=None):
    """ Queries all patterns for a service and creates list of stops sorted
        topologically.

        :param code: Service code.
        :param direction: Groups journey patterns by direction.
    """
    dict_stops = _service_stops(code, direction)
    if not dict_stops:
        raise ValueError("No stops exist for service code %s" % code)

    graph = _service_graph(code, direction)
    stops = [dict_stops[v.current] for v in graph.sort()]

    return stops


def service_json(service, direction):
    """ Creates geometry JSON data for map. """
    dict_stops = _service_stops(service.code, direction,
                                ["latitude", "longitude"])
    if not dict_stops:
        raise ValueError("No stops exist for service %r" % service.code)

    def convert(vertex):
        stop = dict_stops[vertex]
        return stop.longitude, stop.latitude

    paths = _service_graph(service.code, direction).lines()
    lines = [[convert(v) for v in p] for p in paths if len(p) > 1]

    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": lines
        },
        "properties": {
            "service": service.code,
            "line": service.line,
            "description": service.description,
            "direction": direction
        }
    }

    return geojson
