"""
Draws a route graph for a service.
"""
import collections
import collections.abc as abc
import itertools

from nextbus import db, models


class Path(abc.MutableSequence):
    """ Immutable path as sequence of vertices. """
    def __init__(self, vertices=None):
        self._v = list(vertices) if vertices is not None else []

    def __repr__(self):
        return "<Path(%r, cyclic=%s)>" % (self._v, self.cyclic)

    def __getitem__(self, index):
        return self._v[index]

    def __contains__(self, vertex):
        return vertex in self._v

    def __len__(self):
        return len(self._v)

    def __eq__(self, other):
        return list(self) == list(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __setitem__(self, index, value):
        self._v[index] = value

    def __delitem__(self, index):
        del self._v[index]

    def insert(self, index, value):
        self._v.insert(index, value)

    @property
    def cyclic(self):
        return len(self) > 1 and self[0] == self[-1]

    @property
    def edges(self):
        return [(self[i], self[i+1]) for i in range(len(self) - 1)]

    def make_acyclic(self):
        """ Create an acyclic path by removing the last vertex. """
        return Path(self[:-1]) if self.cyclic else Path(self)

    def prepend(self, vertex):
        """ Adds vertex to start of path. """
        self.insert(0, vertex)

    def prepend_with(self, vertex):
        """ Returns copy of this path but with an vertex appended. """
        return Path([vertex] + list(self))

    def append_with(self, vertex):
        """ Returns copy of this path but with an vertex prepended. """
        return Path(list(self) + [vertex])

    def split(self, edge):
        """ Returns list of new paths split by cutting an edge.

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


def _merge_forward(graph, sequence, path, index):
    """ Merges path into sequence, ensuring all new vertices follows the
        existing ones in the adjacency list.
    """
    i = index
    for v in path:
        if v in sequence:
            continue
        # Check if any later vertices have this path and move index
        after = [j for j, w in enumerate(sequence[i:], i)
                 if v in graph.following(w)]
        if after:
            i = after[-1] + 1
        sequence.insert(i, v)
        i += 1


def _merge_backward(graph, sequence, path, index):
    """ Merges path into sequence, ensuring all new vertices precedes the
        existing ones in the adjacency list.
    """
    i = index
    for v in path[::-1]:
        if v in sequence:
            continue
        # Check if any previous vertices have this path and move index
        after = [i - j for j, w in enumerate(sequence[i::-1])
                 if v in graph.preceding(w)]
        if after:
            i = after[-1]
        sequence.insert(i, v)


def _analyse_graph(graph):
    """ Analyses a connected graph to find a set of distinct paths and a
        topologically ordered sequence.
    """
    # Make a copy without self-cycles to modify
    g = graph.clean_copy()
    g0 = g.copy()
    # Start with the diameter of the graph
    diameter = g.diameter()
    if not diameter:
        # The graph has no edges so return sorted list of isolated vertices
        return [], sorted(g.isolated)
    diameter_ac = diameter.make_acyclic()

    # Remove diameter from graph and search the rest
    g.remove_path(diameter)
    paths, sequence = [diameter], list(diameter_ac)

    stack = collections.deque()
    # Search paths both forwards and backwards
    # All diverging branches are searched backwards and vice versa
    stack.extend((e, False) for e in reversed(diameter.edges))
    stack.extend((e, True) for e in diameter.edges)

    while stack:
        edge, forward = stack.pop()
        vertex = edge[0] if forward else edge[1]

        try:
            new_paths = g.search_paths(vertex, forward).values()
        except KeyError:
            continue
        if not any(new_paths):
            continue

        # Add paths to list
        longest = max(sorted(new_paths, key=tuple), key=len)
        g.remove_path(longest)
        paths.append(longest)

        # Merge paths into sequence
        longest_ac = longest.make_acyclic()
        index = sequence.index(vertex)
        if forward:
            _merge_forward(g0, sequence, longest_ac, index)
        else:
            _merge_backward(g0, sequence, longest_ac, index)

        # Add new paths to stack for searching
        stack.extendleft((e, False) for e in reversed(longest_ac.edges))
        stack.extendleft((e, True) for e in longest_ac.edges)
        # Maybe another distinct path here - return vertex to queue
        stack.append((edge, forward))

    return paths, sequence


def _draw_paths_row(start, end):
    paths = set()
    for x0, v0 in enumerate(start):
        if v0 in end:
            paths.add((x0, end.index(v0)))
            continue
        for x1, v1 in enumerate(end):
            if v0 & v1:
                paths.add((x0, x1))

    return paths


def _count_crossovers(start, end):
    crossovers = 0
    if not end:
        return crossovers

    paths = _draw_paths_row(start, end)
    for (x0, x1), (x2, x3) in itertools.combinations(paths, 2):
        try:
            # Intersection of two lines - we assume both start at y = 0 and
            # end at y = 1
            intersection = (x2 - x0) / (x2 - x3 - x0 + x1)
        except ZeroDivisionError:
            continue
        # Need to have intersection between y = 0 and y = 1
        if 0 < intersection < 1:
            crossovers += 1

    return crossovers


def _find_least_crossovers(s0, e0, s1, e1):
    if e0 is None:
        len_ = len(s1)
    elif s1 is None:
        len_ = len(e0)
    else:
        len_ = min(len(e0), len(s1))

    if len_ < 2:
        return

    original = tuple(range(len_))
    crossovers = {}
    for p in itertools.permutations(original):
        count = 0
        if e0 is not None:
            ei = [e0[i] for i in p]
            count += _count_crossovers(s0, ei)
        if s1 is not None:
            si = [s1[i] for i in p]
            count += _count_crossovers(si, e1)

        crossovers[p] = count

    min_co = min(crossovers.values())
    least_co = {c for c, i in crossovers.items() if i == min_co}

    if original in least_co:
        # Original arrangement already has the least number of crossovers
        return

    def diff(t):
        return sum(abs(i - j) for i, j in zip(original, t))

    return min(least_co, key=diff)


class _GraphLayout:
    """ Helper class for drawing a graph. """

    def __init__(self, graph, sequence=None):
        self.g = graph
        self.seq = sequence if sequence else self.g.sequence()

        if len(self.seq) > len(set(self.seq)):
            raise ValueError("Sequence %r has non-unique vertices" % self.seq)

        self._width = None
        self._col = None
        self._next = None
        self._start = None
        self._end = None
        self._paths = None

    def _init(self):
        self._width = 0
        self._col = {}
        self._next = {}
        self._start = {}
        self._end = {}
        self._paths = {}

    def _incoming(self, vertex):
        index = self.seq.index(vertex)
        return self.g.preceding(vertex) & set(self.seq[:index])

    def _outgoing(self, vertex):
        index = self.seq.index(vertex)
        return self.g.following(vertex) & set(self.seq[index+1:])

    def _set_next_columns(self, vertex, column):
        columns = {}

        diverges = [v for v in self.seq if v in self._outgoing(vertex)]
        add_col = False
        col_added = False
        for u in diverges[::-1]:
            # Add new column for extra vertices
            if add_col and not col_added:
                self._width += 1
                col_added = True

            new_col = column + 1 if add_col else column
            # Put the vertex in the lower of columns set by earlier vertices
            if u in self._col:
                new_col = min(new_col, self._col[u])

            columns[u] = new_col
            # Create new column if diverging vertex takes up same column
            if not add_col and new_col == column:
                add_col = True

        return columns

    def _set_column(self, index):
        vertex = self.seq[index]
        if vertex in self._next:
            del self._next[vertex]

        column = self._col.get(vertex, self._width)
        # Search for diverging vertices and set their columns
        new_columns = self._set_next_columns(vertex, column)
        self._col.update(new_columns)
        self._next.update(new_columns)

        # If this vertex terminates move vertices in higher columns
        if not self._outgoing(vertex):
            for v, c in self._next.items():
                if c > column:
                    self._col[v] = self._next[v] = c - 1

        if not self._incoming(vertex):
            self._width += 1
        # If no other following vertices or all in lower columns reduce width
        if not self._next or max(self._next.values()) < self._width - 1:
            self._width -= 1

        self._col[vertex] = column

    def _first_in_column(self, column, start=0):
        for v in self.seq[start:]:
            if self._col[v] == column:
                return v

    def _rearrange_lines(self, lines, index):
        if index >= len(self.seq) - 1:
            return

        next_v = self.seq[index + 1]
        next_c = self._col[next_v]
        # Move all references for next vertex to this column
        if any(next_v in c for c in lines):
            for vertices in lines:
                vertices.discard(next_v)
            # Add new column for lines if necessary
            if next_c >= len(lines):
                lines.append({next_v})
            else:
                lines[next_c].add(next_v)

        if next_c < len(lines):
            temp = set()
            # Move all other references from this column
            for v in lines[next_c] - {next_v}:
                other_col = self._col[v]
                if v != self._first_in_column(other_col, index):
                    temp.add(v)
                lines[next_c].remove(v)
            if temp:
                # Add new line to avoid the next vertex
                lines.insert(next_c + 1, temp)

    @staticmethod
    def _remove_lines(lines):
        single_lines = set()
        seen = []
        to_remove = []
        # Find lines with only one vertex and mark duplicates for removal
        for i, c in enumerate(lines):
            if len(c) == 1:
                single_lines |= c
            if c not in seen:
                seen.append(c)
            else:
                to_remove.append(i)

        # Remove all duplicate lines that lead to a single vertex
        for i in reversed(to_remove):
            del lines[i]

        # Remove vertices from lines that already exist in other lines
        for c in lines:
            if len(c) > 1:
                c -= single_lines

        # Clean up any empty columns
        for i in reversed(range(len(lines))):
            if not lines[i]:
                del lines[i]

    def _set_lines(self, index):
        vertex = self.seq[index]
        col = self._col[vertex]

        # Set starting lines to lines at end of previous row
        if index > 0:
            previous_v = self.seq[index - 1]
            lines_start = [set(c) for c in self._end[previous_v]]
        else:
            lines_start = []

        # Remove current vertex
        for c in lines_start:
            c.discard(vertex)

        # Add new columns if necessary
        while col >= len(lines_start):
            lines_start.append(set())

        diverges = [v for v in self.seq if v in self._outgoing(vertex)]
        for v in diverges:
            lines_start[col].add(v)

        # Clean up empty columns except for current vertex
        lines_start = [c for i, c in enumerate(lines_start) if c or i == col]
        lines_end = [set(c) for c in lines_start]

        self._rearrange_lines(lines_end, index)
        self._remove_lines(lines_end)

        self._start[vertex] = lines_start
        self._end[vertex] = lines_end

    def _swap_lines_row(self, index):
        len_seq = len(self.seq)
        if len_seq == 1:
            return

        cur_v = self.seq[index]
        prev_v = self.seq[index - 1]

        start0 = self._start[prev_v] if index != 0 else None
        end0 = self._end[prev_v] if index != 0 else None
        start1 = self._start[cur_v] if index != len_seq - 1 else None
        end1 = self._start[cur_v] if index != len_seq - 1 else None

        best_match = _find_least_crossovers(start0, end0, start1, end1)
        if best_match is None:
            return

        len_ = len(best_match)
        self._end[prev_v] = [end0[i] for i in best_match] + end0[len_:]
        self._start[cur_v] = [start1[i] for i in best_match] + start1[len_:]
        if self._col[cur_v] < len_:
            self._col[cur_v] = best_match[self._col[cur_v]]

    def _draw_paths(self, index):
        vertex = self.seq[index]
        paths = _draw_paths_row(self._start[vertex], self._end[vertex])

        self._paths[vertex] = paths

    def draw(self):
        self._init()
        len_seq = len(self.seq)

        for i in range(len_seq):
            self._set_column(i)

        for i in range(len_seq):
            self._set_lines(i)

        for i in range(len_seq):
            self._swap_lines_row(i)

        for i in range(len_seq):
            self._draw_paths(i)

        for v in self.seq:
            print(v, self._col[v], self._start[v], self._end[v])
        print()

        return [(v, self._col[v], self._paths[v]) for v in self.seq]


class Graph:
    """ Directed graph.

        Can be created from a list of edges as tuples of two vertex labels.
    """
    def __init__(self, pairs=None, singles=None):
        self._v = collections.defaultdict(set)
        if pairs is not None:
            for v1, v2 in pairs:
                self[v1] = v2
        if singles is not None:
            for v in singles:
                self.add_vertex(v)

    def __repr__(self):
        return "<Graph(%s)>" % (repr(set(self)) if self else "")

    def __iter__(self):
        return iter(self.vertices)

    def __len__(self):
        return len(self.vertices)

    def __contains__(self, v):
        return v in self.vertices

    def __eq__(self, other):
        try:
            return self.adj == other.adj
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, v):
        if v in self.heads:
            return self._v[v]
        elif v in self.tails:
            return set()
        else:
            raise KeyError(v)

    def __setitem__(self, v1, v2):
        if v2 is not None:
            self._v[v1].add(v2)
            if v2 not in self._v:
                self._v[v2] = set()
        else:
            self._v[v1] = set()

    def __delitem__(self, v):
        if v in self._v:
            del self._v[v]
        else:
            raise KeyError(v)
        for u in self._v:
            self._v[u].discard(v)

    @property
    def adj(self):
        """ Adjacency list for this graph as a dictionary of sets. """
        return dict(self._v)

    @property
    def vertices(self):
        """ All vertices in graph. """
        return set(self._v.keys())

    @property
    def isolated(self):
        """ All vertices without associated edges. """
        return self.vertices - self.heads - self.tails

    @property
    def edges(self):
        """ All edges in this graph as tuples of two vertices. """
        return {(u, v) for u, w in self._v.items() for v in w}

    @property
    def heads(self):
        """ All vertices at head of edges in this graph. """
        return {v for v, w in self._v.items() if w}

    @property
    def tails(self):
        """ All vertices at end of edges in this graph. """
        return set().union(*self._v.values())

    @property
    def sources(self):
        """ All vertices at start of edges in this graph. """
        return self.heads - self.tails

    @property
    def sinks(self):
        """ All vertices without incoming edges. """
        return self.tails - self.heads

    def copy(self):
        """ Makes a copy of the graph. """
        return Graph(self.edges, singles=self.isolated)

    def clean_copy(self):
        """ Makes a copy of the graph with no self-edges. """
        graph = self.copy()
        for u, v in graph.edges:
            if u == v:
                graph.remove_edge(u, v)

        return graph

    def following(self, v):
        """ All vertices at end of edges that start at specified vertex. """
        if v not in self._v:
            raise KeyError(v)

        return set(self._v[v])

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
        if v not in self._v:
            raise KeyError(v)

        return {(v, u) for u in self.following(v)}

    def contains_vertex(self, vertex):
        return vertex in self

    def contains_edge(self, edge):
        try:
            u, v = edge
        except TypeError as err:
            raise TypeError("%r is not a tuple of two values" % edge) from err

        return u in self._v and v in self._v[u]

    def contains_path(self, path):
        return all(self.contains_edge(e) for e in path.edges)

    def add_vertex(self, v, following=None):
        self[v] = following

    def remove_vertex(self, v):
        del self[v]

    def add_edge(self, v1, v2):
        self[v1] = v2

    def remove_edge(self, v1, v2, delete=True):
        """ Removes edge from graph. If delete is True, any orphaned vertices
            are removed as well.
        """
        if v1 not in self._v:
            raise KeyError(v1)
        if v2 not in self._v[v1]:
            raise KeyError(v2)

        self._v[v1].discard(v2)

        if delete and not self._v[v1] and v1 not in self.tails:
            del self[v1]
        if delete and not self._v[v2]:
            del self[v2]

    def add_path(self, path):
        """ Adds a Path object or a sequence of edges to this graph. """
        try:
            edges = path.edges
        except AttributeError:
            edges = path

        for e in edges:
            try:
                v1, v2 = e
            except TypeError as err:
                raise TypeError("%r is not a tuple of two values" % e)
            self[v1] = v2

    def remove_path(self, path, delete=True):
        """ Removes all edges in Path or sequence of edges from this graph. If
            delete is True, any orphaned vertices are removed as well.
        """
        try:
            edges = path.edges
        except AttributeError:
            edges = path

        for e in edges:
            if not self.contains_edge(e):
                raise ValueError("Edge %r does not exist in graph %r" %
                                 (e, self))

        for v1, v2 in edges:
            self.remove_edge(v1, v2, delete)

    def update(self, adj):
        """ Updates graph with an adjacency list in the form of a dictionary of
            vertex heads with neighbouring nodes as iterables.
        """
        for u in dict(adj):
            for v in adj[u]:
                self[u] = v

    def clear(self):
        """ Clears all vertices and edges from graph. """
        self._v.clear()

    def split(self):
        """ Splits graph into a number of connected graphs. """
        edges = {}

        for new, edge in enumerate(self.edges):
            for e in edges:
                if e[0] in edge or e[1] in edge:
                    edges.update({f: new for f, index in edges.items()
                                  if index == edges[e]})
            edges[edge] = new

        groups = collections.defaultdict(list)
        for e, i in edges.items():
            groups[i].append(e)

        connected = [Graph(s) for s in groups.values()]
        isolated = [Graph(singles=[v]) for v in self.isolated]

        if connected or isolated:
            return connected + isolated
        else:
            return [Graph()]

    def _search_paths(self, v, target=None):
        """ Does a BFS to find shortest paths in graph starting at vertex `v`.

            If target vertex `t` is None, all paths are searched and returned as
            a dictionary of vertices with shortest paths. Otherwise, only the
            shortest path starting at `v` and ending at `t` is returned.

            Edges following vertices are sorted to give a consistent result.
        """
        if v not in self:
            raise KeyError(v)
        if target is not None and target not in self:
            raise KeyError(v)

        paths = {}
        queue = collections.deque()

        # Add all immediately adjacent paths to queue
        queue.extendleft(
            Path([v, w]) for w in sorted(self.following(v))
        )

        while queue:
            p = queue.pop()
            u = p[-1]
            if u in paths:
                # A shorter path was already found
                continue
            paths[u] = p
            if target is not None and u == target:
                break
            if u != v:
                # Add all following paths to queue
                queue.extendleft(
                    p.append_with(w) for w in sorted(self.following(u))
                )

        # Find all vertices not covered by BFS
        for u in self.vertices - paths.keys():
            paths[u] = Path()

        return paths if target is None else {target: paths[target]}

    def search_paths(self, v, forward=True):
        """ Does BFS on graph to find shortest paths from vertex v to all other
            vertices (including itself), or vice versa if forward is False.

            Edges following vertices are sorted to give a consistent result.
        """
        if forward:
            paths = self._search_paths(v)
        else:
            paths = {u: self._search_paths(u, v)[v] for u in self}

        return paths

    def shortest_path(self, v1, v2):
        """ Finds the shortest path between a pair of vertices in the graph
            recursively.

            Invalid paths (eg disconnected vertices or internal cycles) return
            None.
        """
        if v1 not in self:
            raise KeyError(v1)
        if v2 not in self:
            raise KeyError(v2)

        paths_from = self._search_paths(v1, v2)

        return paths_from[v2] if paths_from[v2] else None

    def diameter(self):
        """ Finds the longest path in this graph that is the shortest path
            between a pair of vertices.

            Longest paths are sorted by their vertices as to give a consistent
            result.
        """
        longest_paths = []

        for v in sorted(self):
            new_paths = self._search_paths(v)
            longest_paths.extend(new_paths.values())

        if longest_paths:
            longest_paths.sort(key=tuple)
            return max(longest_paths, key=len)
        else:
            return Path()

    def analyse(self):
        """ Finds all distinct paths for this graph and the topological order
            of vertices, starting with the diameter.
        """
        paths, sequence = [], []
        # Start with the largest connected graph and analyse each
        for g in sorted(self.split(), key=len, reverse=True):
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
        """ Lays out graph using sequence.

            :param sequence: Use sequence to draw graph, If it is None the
            sequence is generated instead..
            :returns: List of dictionaries, ordered using sequence, with
            vertex name, column and lines before/after.
        """
        return _GraphLayout(self, sequence).draw()


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


def service_graph(code, direction):
    """ Get list of stops and their preceding and following stops for a service.

        :param code: Service code.
        :param direction: Groups journey patterns by direction - False for
        outbound and True for inbound.
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
                models.JourneyPattern.direction == direction,
                models.JourneyLink.stop_point_ref.isnot(None))
    )

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


def service_stop_list(code, direction):
    """ Queries all patterns for a service and creates list of stops sorted
        topologically.

        :param code: Service code.
        :param direction: Groups journey patterns by direction - False for
        outbound and True for inbound.
    """
    dict_stops = _service_stops(code, direction)
    if not dict_stops:
        raise ValueError("No stops exist for service code %s" % code)

    graph = service_graph(code, direction)
    stops = [dict_stops[v] for v in graph.sequence()]

    return stops


def service_json(service, direction):
    """ Creates geometry JSON data for map.

        :param service: Service instance.
        :param direction: Groups journey patterns by direction - False for
        outbound and True for inbound.
    """
    dict_stops = _service_stops(service.code, direction)
    if not dict_stops:
        raise ValueError("No stops exist for service %r" % service.code)

    def coordinates(vertex):
        stop = dict_stops[vertex]
        return stop.longitude, stop.latitude

    paths, sequence = service_graph(service.code, direction).analyse()

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
