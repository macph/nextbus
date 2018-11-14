"""
Draws a route graph for a service.
"""
import collections
import collections.abc as abc
import itertools

from nextbus import db, models


ORDER_ITERATIONS = 6


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


# TODO: Add support for cyclic paths - use negative numbers or separate dicts


class _Layout:
    """ Helper class to hold all data while setting vertices and lines. """
    def __init__(self, graph, sequence=None):
        self.g = graph
        self.seq = graph.sequence() if sequence is None else sequence

        if len(self.seq) > len(set(self.seq)):
            raise ValueError("Sequence %r has non-unique vertices" % self.seq)

        self.col = {v: 0 for v in self.seq}
        self.start = {}
        self.end = {}
        self.cycles = {}
        self.next_cycles = {}
        self.paths = {}

    def _select(self, vertex=None, index=None):
        if vertex is not None:
            v, i = vertex, self.seq.index(vertex)
        elif index is not None:
            v, i = self.seq[index], index
        else:
            raise ValueError("Either a vertex or an index must be specified.")

        return v, i

    def incoming(self, vertex, direct=True, cyclic=False):
        preceding = self.g.preceding(vertex)
        index = self.seq.index(vertex)
        before = set(self.seq[:index])

        if direct and cyclic:
            return preceding
        elif direct:
            return preceding & before
        elif cyclic:
            return preceding - before
        else:
            return set()

    def outgoing(self, vertex, direct=True, cyclic=False):
        following = self.g.following(vertex)
        index = self.seq.index(vertex)
        after = set(self.seq[index + 1:])

        if direct and cyclic:
            return following
        elif direct:
            return following & after
        elif cyclic:
            return following - after
        else:
            return set()

    def previous_vertex(self, vertex):
        index = self.seq.index(vertex)
        return self.seq[index - 1] if index > 0 else None

    def next_vertex(self, vertex):
        index = self.seq.index(vertex)
        return self.seq[index + 1] if index < len(self.seq) - 1 else None

    def copy(self):
        """ Makes a copy of the layout for modification. """
        layout = _Layout(self.g, self.seq)

        layout.col = {v: self.col[v] for v in self.seq}
        if self.start:
            layout.start = {v: [set(c) for c in self.start[v]]
                            for v in self.seq}
        if self.end:
            layout.end = {v: [set(c) for c in self.end[v]]
                          for v in self.seq}
        if self.paths:
            layout.paths = {v: [set(c) for c in self.paths[v]]
                            for v in self.seq}

        return layout


def _rearrange_lines(layout, lines, vertex):
    """ Move around lines such that only one line has the next vertex, with
        all others avoiding that vertex.
    """
    col = layout.col[vertex]
    next_v = layout.next_vertex(vertex)

    if next_v is None:
        return

    while col >= len(lines):
        lines.append(set())

    if any(next_v in c for c in lines):
        # Move all references for next vertex to this column
        for vertices in lines:
            vertices.discard(next_v)
        lines[col].add(next_v)
    else:
        # New vertex; add column to lines
        lines.append({next_v})

    temp = set()
    # Move all other references from this column
    for v in lines[col] - {next_v}:
        temp.add(v)
        lines[col].remove(v)
    if temp:
        # Add new line to left of the next vertex
        lines.insert(col, temp)


def _remove_lines(lines):
    """ Remove all lines that are empty or duplicates of other lines in this
        row.

        If lines with single vertices exist, these vertices are removed from
        all other lines.
    """
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

    # Remove vertices from lines that already exist in other single lines
    for c in lines:
        if len(c) > 1:
            c -= single_lines

    # Clean up any empty columns
    for i in reversed(range(len(lines))):
        if not lines[i]:
            del lines[i]


def _add_outgoing_cycles(layout, start, end, vertex):
    if vertex not in {u[0] for u in layout.cycles.values()}:
        return

    column = layout.col[vertex]
    # Add lines for cycles
    for c in sorted(layout.cycles.keys()):
        u, v = layout.cycles[c]
        if vertex != u:
            continue
        while c > len(end):
            end.append(set())

        start[column].add(v)
        end.insert(c, {v})


def _add_incoming_cycles(layout, start, end, vertex):
    next_v = layout.next_vertex(vertex)
    if next_v is None:
        return

    cycles = layout.incoming(next_v, direct=False, cyclic=True)
    if not cycles:
        return

    next_c = layout.col[next_v] = end.index({next_v})
    while next_c >= len(start):
        start.append(set())

    column = next_c
    new_column = layout.col[vertex]
    # Order from furthest away to nearest
    incoming = [v for v in reversed(layout.seq) if v in cycles]
    for v in incoming:
        if v == next_v:
            # Don't want self-cycles
            continue
        if column in layout.cycles:
            column += 1
            while column > len(start):
                start.append(set())

        layout.cycles[column] = (v, next_v)
        # Insert new column for incoming cycle and track original vertex
        start.insert(column, {next_v})
        if new_column >= column:
            new_column += 1
        column += 1

    # Modify original vertex column and its lines
    original = layout.col[vertex]
    if new_column > original:
        index = layout.seq.index(vertex)
        if index < 1:
            return
        previous_v = layout.seq[index - 1]

        layout.end[previous_v][original:] = (
            [set()] * (new_column - original)
            + layout.end[previous_v][original:]
        )
        layout.col[vertex] = new_column


def _set_next_column(layout, lines, vertex):
    """ Sets the column of the next vertex based on the ending lines for this
        row.
    """
    next_v = layout.next_vertex(vertex)
    # Set column for next vertex using lines
    if next_v is not None:
        layout.col[next_v] = lines.index({next_v})


def _set_lines(layout):
    """ Set all lines and moving vertices into the correct columns. """
    if not layout.seq:
        return

    first_v = layout.seq[0]
    cycles = layout.incoming(first_v, direct=False, cyclic=True)
    if cycles:
        ordered = [v for v in reversed(layout.seq) if v in cycles]
        # Add new row for cycle before first vertex
        layout.seq.insert(0, None)
        layout.col[None] = 0
        layout.start[None] = [{first_v}] * len(cycles)
        layout.end[None] = [{first_v}]
        layout.cycles.update({c: (v, first_v) for c, v in enumerate(ordered)})

    lines_end = None
    for v in layout.seq:
        if v is None:
            continue

        col = layout.col[v]
        # Set starting lines to lines at end of previous row
        if lines_end is not None:
            lines_start = [set(c) for c in lines_end]
        else:
            lines_start = []

        # Remove current vertex, any outgoing cycles and add new columns
        to_remove = {u[1] for u in layout.cycles.values()} | {v}
        for c in lines_start:
            c -= to_remove
        while col >= len(lines_start):
            lines_start.append(set())

        # Add all outgoing vertices to current column except self
        lines_start[col] |= layout.outgoing(v)

        # Clean up empty columns except for current vertex
        lines_start = [c for i, c in enumerate(lines_start) if c or i <= col]
        lines_end = [set(c) for c in lines_start]

        _rearrange_lines(layout, lines_end, v)
        _remove_lines(lines_end)
        _add_outgoing_cycles(layout, lines_start, lines_end, v)
        _add_incoming_cycles(layout, lines_start, lines_end, v)
        _set_next_column(layout, lines_end, v)

        layout.start[v] = lines_start
        layout.end[v] = lines_end


def _draw_paths_row(start, end):
    """ Draws paths as a set of tuples from the starting and ending lines.

        All lines are assumed to split up, that is, no ending line would
        have more vertices than any starting line.
    """
    paths = set()
    for x0, v0 in enumerate(start):
        if v0 in end:
            paths.add((x0, end.index(v0)))
            continue
        for x1, v1 in enumerate(end):
            if v1 and v0 >= v1:
                paths.add((x0, x1))

    return paths


def _count_crossings(start, end):
    """ Counts crossings within a row defined by starting and ending lines.

        Each pair of paths are checked by seeing if the differences in starting
        and ending vertices' positions are non-zero and of opposite signs.
    """
    paths = _draw_paths_row(start, end)
    pairs = itertools.combinations(paths, 2)

    return sum(1 for (a, b), (c, d) in pairs if (a - c) * (b - d) < 0)


def _count_all_crossings(layout):
    """ Counts all crossings within the layout. """
    return sum(_count_crossings(layout.start[v], layout.end[v])
               for v in layout.seq)


def _median(collection):
    """ Calculates the median of an collection, eg a list. """
    ordered = sorted(collection)
    len_ = len(collection)
    middle = len_ // 2

    if not ordered:
        return -1
    elif len_ % 2 == 1:
        return ordered[middle]
    else:
        return (ordered[middle - 1] + ordered[middle]) / 2


def _median_order(start, end, forward=True):
    """ Sets order of a row by using the median of the positions of adjacent
        lines for each line.
    """
    median = {}
    paths = _draw_paths_row(start, end)

    if forward:
        len_ = len(end)
        for i in range(len_):
            previous_columns = {p[0] for p in paths if p[1] == i}
            median[i] = _median(previous_columns)
    else:
        len_ = len(start)
        for i in range(len_):
            next_columns = {p[1] for p in paths if p[0] == i}
            median[i] = _median(next_columns)

    # Vertices are left in place if they have no adjacent vertices
    moved = iter(sorted(i for i in range(len_) if median[i] >= 0))
    ordered = [next(moved) if median[i] >= 0 else i for i in range(len_)]

    if ordered != list(range(len_)):
        return ordered


def _transpose_order(start, end, forward=True):
    """ Swaps lines within a row to see if the number of crossings improve. """
    len_ = len(end) if forward else len(start)

    if len_ < 2:
        return

    order = list(range(len_))
    crossings = _count_crossings(start, end)

    improved = True
    while improved:
        improved = False
        for i in range(len_ - 1):
            new_order = order[:i] + [order[i + 1], order[i]] + order[i + 2:]
            if forward:
                temp = [set(end[j]) for j in new_order]
                new_crossings = _count_crossings(start, temp)
            else:
                temp = [set(start[j]) for j in new_order]
                new_crossings = _count_crossings(temp, end)

            if new_crossings < crossings:
                order = new_order
                crossings = new_crossings
                improved = True

    return order


def _set_new_order(layout, index, new):
    """ Sets the next row to the new order.

        If the index is negative, the first row will be modified instead.
    """
    if index >= len(layout.seq) - 1:
        return

    len_ = len(new)

    if index >= 0:
        v = layout.seq[index]
        end = layout.end[v]
        next_v = layout.seq[index + 1]
        next_s = layout.start[next_v]
    else:
        v = None
        end = None
        next_v = layout.seq[0]
        next_s = layout.start[next_v]

    if v is not None:
        layout.end[v] = [end[i] for i in new] + end[len_:]

    layout.start[next_v] = [next_s[i] for i in new] + next_s[len_:]

    if layout.col[next_v] < len_:
        layout.col[next_v] = new.index(layout.col[next_v])


def _order_lines(layout):
    """ Processes layout to reduce the number of crossings.

        Heuristics based on the dot algorithm are used where over a number of
        iterations the graph is transversed forwards and backwards.

        The layout is set to the new layout if the number of crossings is
        reduced.
    """
    # Make copies of current columns and lines to modify
    nl = layout.copy()

    crossings = _count_all_crossings(nl)
    enum_seq = list(enumerate(layout.seq))

    def iter_seq(f):
        return iter(enum_seq) if f else reversed(enum_seq)

    for i in range(ORDER_ITERATIONS):
        # Set line orderings with medians
        # alternate between iterating forwards and backwards
        forward = i % 2 == 0

        for j, v in iter_seq(forward):
            medians = _median_order(nl.start[v], nl.end[v], forward)
            if medians is not None:
                k = j if forward else j - 1
                _set_new_order(nl, k, medians)

        for j, v in iter_seq(forward):
            transpose = _transpose_order(nl.start[v], nl.end[v], forward)
            if transpose is not None:
                k = j if forward else j - 1
                _set_new_order(nl, k, transpose)

        # If crossings have been improved, copy them back into original data
        new_crossings = _count_all_crossings(nl)
        if new_crossings < crossings:
            rl = nl.copy()
            layout.start = rl.start
            layout.end = rl.end
            layout.col = rl.col


def _draw_paths(layout):
    """ Draws all paths and adds to layout. """
    for v in layout.seq:
        layout.paths[v] = _draw_paths_row(layout.start[v], layout.end[v])


def draw_graph(graph, sequence=None):
    """ Draws graph.

        The graph is laid out in steps:
        - All vertices are set in column 0.
        - Lines are set every row, with the vertices moved to the correct
        columns.
        - Using the dot graph algorithms, the lines are replaced using the
        median of adjacent vertices and each pair of lines on every row are
        transposed to reduce the number of crossings. If the new layout has
        fewer crossings, it replaces the current layout.
        - Finally all lines are drawn between vertices.

        :param graph: Graph object.
        :param sequence: List of vertices. If None, the sequence generated by
        graph is used instead.
        :returns: A list of tuples of the form (vertex, column, paths) where
        paths is the set of all paths between specific columns in that row.
    """
    gl = _Layout(graph, sequence)

    _set_lines(gl)
    # _order_lines(gl)
    _draw_paths(gl)

    data = [(v, gl.col[v], sorted(gl.paths[v])) for v in gl.seq]

    print(graph.adj)
    print(gl.cycles)
    for v in gl.seq:
        print("%s %s %r -> %r" % (v, gl.col[v], gl.start[v], gl.end[v]))
    print(data)
    print()

    return data


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
                raise TypeError("%r is not a tuple of two values" % e) from err
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
            sequence is generated instead.
            :returns: List of dictionaries, ordered using sequence, with
            vertex name, column and lines before/after.
        """
        return draw_graph(self, sequence)


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
