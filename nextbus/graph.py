"""
Draws a route graph for a service.
"""
import collections
import collections.abc as abc
import enum

from nextbus import db, models


class Line(enum.Enum):
    THROUGH, TERMINATE, CONTINUE = range(3)


class Path(abc.Sequence, abc.Hashable):
    """ Immutable path as sequence of vertices. """
    def __init__(self, vertices):
        self._v = tuple(vertices)

    def __repr__(self):
        return "<Path(%r, cyclic=%s)>" % (self._v, self.cyclic)

    def __getitem__(self, index):
        return self._v[index]

    def __contains__(self, vertex):
        return vertex in self._v

    def __len__(self):
        return len(self._v)

    def __hash__(self):
        return hash(self._v)

    @property
    def cyclic(self):
        return len(self._v) > 1 and self._v[0] == self._v[-1]

    @property
    def edges(self):
        return [(self[i], self[i+1]) for i in range(len(self) - 1)]

    def make_acyclic(self):
        """ Create an acyclic path by removing the last vertex. """
        return Path(self[:-1]) if self.cyclic else Path(self)

    def prepend_with(self, vertex):
        """ Returns this path but with an vertex appended. """
        return Path([vertex] + list(self))

    def append_with(self, vertex):
        """ Returns this path but with an vertex prepended. """
        return Path(list(self) + [vertex])

    def split(self, edge):
        """ Returns new paths split by cutting an edge.

            If said edge is the first or last in the path the first or last
            vertex respectively is removed, returning one path.
        """
        edges = self.edges

        try:
            index = edges.index(edge)
        except ValueError:
            raise KeyError(edge)

        if index == 0:
            # Remove first vertex
            return [Path(self[1:])]
        elif index == len(edges) - 1:
            # Remove last vertex
            return [Path(self[:-1])]
        else:
            # Split into two paths
            return [Path(self[:index+1]), Path(self[index+1:])]


def _extract_path(graph, u, queue, paths, sequence, forward=True):
    """ Finds longest possible path starting or ending at specified vertex,
        adding it to the list of paths and the sequence. The path is removed
        from the graph afterwards.
    """
    cache = {}  # New cache as the graph will have been modified
    new_paths = []
    index = sequence.index(u)
    i = index + 1 if forward else index
    if u not in graph:
        return False

    for v in graph:
        vertices = (u, v) if forward else (v, u)
        path = graph.shortest_path(*vertices, cache)
        if path is not None:
            new_paths.append(path)

    if not new_paths:
        return False

    longest = max(new_paths, key=len)
    graph.remove_path(longest)
    paths.append(longest)

    longest_ac = longest.make_acyclic()
    list_long = [v for v in longest_ac if v not in sequence]
    # Modify existing sequence
    sequence[i:] = list_long + sequence[i:]
    queue.extendleft(longest_ac.edges)

    return True


def _analyse_graph(graph):
    """ Analyses a connected graph to find a set of distinct paths and a
        topologically ordered sequence.
    """
    # Make a copy to modify
    graph = graph.copy()
    # Find any self-cycles and remove them
    for e in graph.edges:
        if e[0] == e[1]:
            del graph[e]
    # Start with the diameter of the graph
    diameter = graph.diameter()
    diameter_ac = diameter.make_acyclic()
    if not diameter:
        return [], []

    # Remove diameter from graph and search the rest
    graph.remove_path(diameter)
    paths, sequence = [diameter], list(diameter_ac)
    queue = collections.deque(diameter.edges)

    while queue:
        u, v = edge = queue.pop()
        # Search paths both forwards and backwards
        forward = _extract_path(graph, u, queue, paths, sequence, True)
        backward = _extract_path(graph, v, queue, paths, sequence, False)
        if forward or backward:
            # Maybe another distinct path here - search again
            queue.append(edge)

    assert not len(graph)

    return paths, sequence


class Graph(abc.MutableMapping):
    """ Directed graph.

        Can be created from a list of edges as tuples of two vertex labels.
    """
    def __init__(self, pairs=None):
        self._v = collections.defaultdict(set)
        if pairs is not None:
            for v1, v2 in pairs:
                self._v[v1].add(v2)

    def __repr__(self):
        return "<Graph(%s)>" % set(self)

    def __getitem__(self, v):
        if v in self.heads:
            return self._v[v]
        elif v in self.tails:
            return set()
        else:
            raise KeyError(v)

    def __iter__(self):
        return iter(self.vertices)

    def __len__(self):
        return len(self.vertices)

    def __setitem__(self, v1, v2):
        self._v[v1].add(v2)

    def __delitem__(self, v):
        try:
            v1, v2 = v
            self._v[v1].remove(v2)
            if not self._v[v1]:
                del self._v[v1]

        except TypeError:
            if v in self._v:
                del self._v[v]
            for u in self._v:
                self._v[u].discard(v)

    @property
    def edges(self):
        """ All edges in this graph as tuples of two vertices. """
        return {(u, w) for u, v in self._v.items() for w in v}

    @property
    def heads(self):
        return set(self._v)

    @property
    def tails(self):
        """ All vertices at end of edges in this graph. """
        return set.union(*self._v.values()) if self._v else set()

    @property
    def sources(self):
        """ All vertices at start of edges in this graph. """
        return self.heads - self.tails

    @property
    def sinks(self):
        """ All vertices without incoming edges. """
        return self.tails - self.heads

    @property
    def vertices(self):
        """ All vertices without outgoing edges. """
        return self.heads | self.tails

    def following(self, v):
        """ All vertices at end of edges that start at specified vertex. """
        if v in self._v:
            return self._v[v]
        elif v in self:
            return set()
        else:
            raise KeyError(v)

    def preceding(self, v):
        """ All vertices at start of edges that end at specified vertex. """
        if v not in self:
            raise KeyError(v)

        return {u for u in self._v if v in self._v[u]}

    def incoming(self, v):
        """ All incoming edges for specified vertex. """
        if v not in self:
            raise KeyError(v)

        return {(u, v) for u in self.preceding(v)}

    def outgoing(self, v):
        """ All outgoing edges for specified vertex. """
        if v in self._v:
            return {(v, w) for w in self._v[v]}
        elif v in self:
            return set()
        else:
            raise KeyError(v)

    def copy(self):
        """ Makes a copy of the graph. """
        return Graph(self.edges)

    def add_edge(self, v1, v2):
        """ Adds an edge to the graph. """
        self._v[v1].add(v2)

    def remove_edge(self, v1, v2):
        """ Removes an edge. Equivalent to ``del graph[(v1, v2)]``. """
        del self[(v1, v2)]

    def add_path(self, path):
        """ Adds a Path object or a sequence of edges to this graph. """
        try:
            edges = path.edges
        except AttributeError:
            edges = path

        for v1, v2 in edges:
            self._v[v1].add(v2)

    def remove_path(self, path):
        """ Removes all edges in Path or sequence of edges from this graph. """
        try:
            edges = path.edges
        except AttributeError:
            edges = path

        for e in edges:
            del self[e]

    def split(self):
        """ Splits graph into a number of connected graphs. """
        groups = {}

        def update_group(index, new_index):
            nonlocal groups
            for f in groups:
                if groups[f] == index:
                    groups[f] = new_index

        for i, edge in enumerate(self.edges):
            for e in groups:
                if e[0] in edge or e[1] in edge:
                    update_group(groups[e], i)
            groups[edge] = i

        assert len(groups) == len(self.edges)

        sets = collections.defaultdict(set)
        for w, i in groups.items():
            sets[i].add(w)

        return [Graph(s) for s in sets.values()] if sets else [self.copy()]

    def shortest_path(self, v1, v2, cache=None, _walk=None):
        """ Finds the shortest path between a pair of vertices in the graph
            recursively.

            Invalid paths (eg disconnected vertices or internal cycles) return
            None.
        """
        if v1 not in self:
            raise KeyError(v1)
        if v2 not in self:
            raise KeyError(v2)

        if cache is not None and (v1, v2) in cache:
            return cache[(v1, v2)]

        if v1 in self.sinks or v2 in self.sources:
            if cache is not None:
                cache[(v1, v2)] = None
            return None

        def _path_sort(p):
            return (len(p), *iter(p))

        # We only want to discard cycles within walks, so first vertex is not
        # included
        walk = _walk if _walk is not None else []

        path = None
        paths = []
        for v in self.following(v1):
            if v in walk:
                # Cycled back to same vertex within walk - can't end so discard
                break
            if v == v1 == v2:
                path = Path([v1])
                break
            if v == v2:
                path = Path([v1, v2])
                break

            new_path = self.shortest_path(v, v2, cache, walk + [v])
            if new_path is not None and not new_path.cyclic:
                # Attach first vertex to start of path found
                paths.append(new_path.prepend_with(v1))

        if path is None and paths:
            path = min(paths, key=_path_sort)

        if cache is not None:
            cache[(v1, v2)] = path

        return path

    def diameter(self):
        """ Finds the longest path in this graph that is the shortest path
            between a pair of vertices.

            Longest paths are sorted by their vertices as to give a consistent
            result.
        """
        paths = []
        cache = {}

        for u in self.heads:
            for v in self.tails:
                # Find all possible paths
                new_path = self.shortest_path(u, v, cache)
                if new_path is not None:
                    paths.append(new_path)

        if paths:
            # Get all longest paths and pick first path after sorting
            return min((p for p in paths if len(p) == max(map(len, paths))),
                       key=lambda p: tuple(p))

    def analyse(self):
        """ Finds all distinct paths for this graph and the topological order
            of vertices, starting with the diameter.
        """
        graphs = self.split()
        paths, sequence = [], []
        # Start with the largest connected graph and analyse each
        for g in sorted(graphs, key=len, reverse=True):
            new_paths, new_sequence = _analyse_graph(g)
            paths.extend(new_paths)
            sequence.extend(new_sequence)

        return paths, sequence

    def paths(self):
        """ List of distinct paths in this graph, starting with the diameter.
        """
        return self.analyse()[0]

    def sequence(self):
        """ Topological order of vertices in this graph, organised around the
            diameter.
        """
        return self.analyse()[1]

    def draw(self, sequence=None):
        """ Draws a diagram of the service. """
        lines_before, lines_after = 0, 0  # Number of lines
        columns = {}  # Record of lines and vertex status

        seq = self.sequence() if sequence is None else sequence

        if len(seq) > len(set(seq)):
            raise ValueError("Vertices in sequence %r are not unique")

        for i, v in enumerate(seq):
            incoming, outgoing = self.preceding(v), self.following(v)
            before, after = set(seq[:i]), set(seq[i+1:])

            if not incoming:
                # Vertex starts here
                status_before = Line.TERMINATE
            elif incoming - before:
                # Possible cyclic path
                status_before = Line.CONTINUE
                incoming &= before
            else:
                status_before = Line.THROUGH

            if not outgoing:
                # Vertex terminates here
                status_after = Line.TERMINATE
            elif outgoing - after:
                # Possible cyclic path
                status_after = Line.CONTINUE
                outgoing &= after
            else:
                status_after = Line.THROUGH

            if v in columns:
                col = columns[v][0]
            else:
                col = lines_before

            lines_after += len(outgoing) - len(incoming)

            diverges = [u for u in seq if u in outgoing]
            for j, u in enumerate(reversed(diverges)):
                if u in columns and columns[u][1] is not None:
                    continue

                new_col = col + j
                if u in columns:
                    new_col = min(new_col, columns[u][0])

                columns[u] = (new_col, None, None, None, None)

            columns[v] = (col, status_before, status_after,
                          lines_before, lines_after)

            lines_before = lines_after

        return columns


def _service_stops(code, direction=None):
    """ Get dictionary of distinct stops for a service.

        :param code: Service code.
        :param direction: Groups journey patterns by direction.
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

    stops = (
        models.StopPoint.query
        .options(db.joinedload(models.StopPoint.locality))
    )

    pairs = pairs.subquery()
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
            models.JourneyPattern.id.label("pattern_id"),
            models.JourneyLink.sequence.label("sequence"),
            models.JourneyLink.stop_point_ref.label("stop_ref")
        )
        .select_from(models.JourneyPattern)
        .join(models.JourneyPattern.links)
        .filter(models.JourneyPattern.service_ref == code,
                models.JourneyLink.stop_point_ref.isnot(None))
    )

    if direction is not None:
        stops = stops.filter(models.JourneyPattern.direction == direction)

    stops = stops.subquery()
    pairs = db.session.query(
        stops.c.stop_ref.label("current"),
        db.func.lead(stops.c.stop_ref)
        .over(partition_by=stops.c.pattern_id, order_by=stops.c.sequence)
        .label("next")
    )

    pairs = pairs.subquery()
    query = db.session.query(pairs).filter(pairs.c.next.isnot(None))

    return Graph(query.all())


def service_stop_list(code, direction=None):
    """ Queries all patterns for a service and creates list of stops sorted
        topologically.

        :param code: Service code.
        :param direction: Groups journey patterns by direction.
    """
    dict_stops = _service_stops(code, direction)
    if not dict_stops:
        raise ValueError("No stops exist for service code %s" % code)

    graph = _service_graph(code, direction)
    stops = [dict_stops[v] for v in graph.sequence()]

    return stops


def service_json(service, direction):
    """ Creates geometry JSON data for map. """
    dict_stops = _service_stops(service.code, direction)
    if not dict_stops:
        raise ValueError("No stops exist for service %r" % service.code)

    def coordinates(vertex):
        stop = dict_stops[vertex]
        return stop.longitude, stop.latitude

    paths, sequence = _service_graph(service.code, direction).analyse()

    # Serialise data
    lines = [[coordinates(v) for v in p] for p in paths if len(p) > 1]
    route_data = [dict_stops[s].to_geojson() for s in sequence]
    # Check if service has a mirror
    mirrored = {p.direction for p in service.patterns} == {True, False}

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

    data = {
        "service": service.code,
        "line": service.line,
        "description": service.description,
        "direction": direction,
        "operator": service.local_operator.name,
        "mirrored": mirrored,
        "sequence": route_data,
        "paths": geojson
    }

    return data
