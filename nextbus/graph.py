"""
Draws a route graph for a service.
"""
import collections
import collections.abc as abc
import itertools

from nextbus import db, models


ORDER_ITERATIONS = 6


# TODO: Service 180 and other still doesn't work - problem with cycles?


class MaxColumnError(Exception):
    """ Used if a row's columns exceed the maximum allowed by the layout. """
    pass


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


def _count_cycles(graph, sequence):
    """ Counts number of cycles in a sequence by checking the preceding nodes
        for every vertex in order.
    """
    cycles = set()
    indices = {v: i for i, v in enumerate(sequence)}
    for v in sequence:
        cycles |= {(u, v) for u in graph.preceding(v)
                   if indices[u] > indices[v]}

    return cycles


def _rearrange_cycles(graph, sequence):
    """ Find all cycles which may include vertices in the wrong order and
        move them around.
    """
    real_cycles = set()
    cycles = _count_cycles(graph, sequence)
    while cycles:
        u, v = cycle = cycles.pop()
        paths = graph.search_paths(v)
        if paths[u]:
            # Path for v -> u exists so u -> v is cyclic
            real_cycles.add(cycle)
            continue
        # u -> v is not cyclic; can assume that this is in the wrong order
        cutoff = sequence.index(u) + 1
        tree = {v} | {w for p in paths.values() for w in p}
        sequence[:cutoff] = (
            [w for w in sequence[:cutoff] if w not in tree] +
            [w for w in sequence[:cutoff] if w in tree]
        )
        cycles = _count_cycles(graph, sequence)
        if cycle in cycles:
            raise ValueError("Cycle %r still in set for graph %r" %
                             (cycle, graph))


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
    stack.extend((v, True) for v in reversed(diameter))
    stack.extend((v, False) for v in diameter)

    while stack:
        vertex, forward = stack.pop()

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
        stack.extendleft((v, True) for v in reversed(longest_ac))
        stack.extendleft((v, False) for v in longest_ac)
        # Maybe another distinct path here - return vertex to queue
        stack.append((vertex, forward))

    assert not g.vertices, "vertices %r still in graph" % g.vertices

    _rearrange_cycles(g0, sequence)

    return paths, sequence


class _Row:
    """ Helper class to hold data for each row in a layout. """
    def __init__(self, layout, vertex, column=None, start=None,
                 end=None, cycles_start=None, cycles_end=None):
        if vertex not in layout.seq:
            raise ValueError("Vertex %r not in sequence %r." %
                             (vertex, layout.seq))

        self.layout = layout
        self.vertex = vertex
        self.column = column
        self.start = start if start is not None else []
        self.end = end if end is not None else []
        self.cycles_start = cycles_start if cycles_start is not None else {}
        self.cycles_end = cycles_end if cycles_end is not None else {}

    def __repr__(self):
        return "<_Row(%r, %r)>" % (self.vertex, self.column)

    def copy(self, new_layout=None):
        return type(self)(
            layout=new_layout if new_layout is not None else self.layout,
            vertex=self.vertex,
            column=self.column,
            start=[set(c) for c in self.start],
            end=[set(c) for c in self.end],
            cycles_start={c: tuple(p) for c, p in self.cycles_start.items()},
            cycles_end={c: tuple(p) for c, p in self.cycles_end.items()}
        )

    @property
    def index(self):
        return self.layout.seq.index(self.vertex)

    def offset(self, steps):
        new_index = self.index + steps
        if new_index < 0 or new_index >= len(self.layout.seq):
            raise ValueError("Index %r (from %r) is outside layout sequence"
                             "range." % self.index)

        return self.layout.rows[self.layout.seq[new_index]]

    @property
    def previous(self):
        if self.index > 0:
            return self.offset(-1)

    @property
    def next_(self):
        if self.index < len(self.layout.seq) - 1:
            return self.offset(1)

    @property
    def incoming_lines(self):
        previous_row = self.previous
        if previous_row is not None:
            return previous_row.end

    @incoming_lines.setter
    def incoming_lines(self, new):
        previous_row = self.previous
        if previous_row is not None:
            previous_row.end = new
        else:
            raise AttributeError("No previous row exists for %r." % self)

    @property
    def outgoing_lines(self):
        return self.start if self.next_ is not None else None

    @outgoing_lines.setter
    def outgoing_lines(self, new):
        if self.next_ is None:
            raise AttributeError("No succeeding row exists for %r." % self)
        self.start = new

    def rearrange(self, new_order):
        incoming, outgoing = self.incoming_lines, self.outgoing_lines

        if incoming is None and outgoing is None:
            return

        len_order = len(new_order)
        len_incoming = len(incoming) if incoming is not None else len(outgoing)
        len_outgoing = len(outgoing) if outgoing is not None else len(incoming)

        if len_incoming != len_outgoing:
            raise ValueError("Incoming lines %r and outgoing lines %r do not "
                             "have the same columns." % (incoming, outgoing))

        if len_order != len_incoming:
            raise ValueError("New order %r not the same length as incoming "
                             "lines %r or outgoing lines %r for row %r" %
                             (new_order, incoming, outgoing, self))

        if new_order == list(range(len_incoming)):
            # Same order already; leave as is
            return

        if outgoing is not None:
            self.outgoing_lines = [outgoing[i] for i in new_order]

        if incoming is not None:
            self.incoming_lines = [incoming[i] for i in new_order]

        self.cycles_start = {new_order.index(c): p for c, p
                             in self.cycles_start.items()}
        self.cycles_end = {new_order.index(c): p for c, p
                           in self.cycles_end.items()}

        self.column = new_order.index(self.column)


class _Layout:
    """ Helper class to hold all data while setting vertices and lines. """
    def __init__(self, graph, sequence=None, max_columns=None):
        self.g = graph
        self.seq = graph.sequence() if sequence is None else sequence
        self.max_col = max_columns

        if len(self.seq) > len(set(self.seq)):
            raise ValueError("Sequence %r has non-unique vertices" % self.seq)

        self.rows = {v: _Row(self, v) for v in self.seq}
        self.cycles = set()
        self.paths = {}

    def _adjacent(self, vertex, direct, cyclic, forward):
        index = self.seq.index(vertex)
        if forward:
            adjacent = self.g.following(vertex)
            sequence = set(self.seq[index + 1:])
        else:
            adjacent = self.g.preceding(vertex)
            sequence = set(self.seq[:index])

        if direct and cyclic:
            return adjacent
        elif direct:
            return adjacent & sequence
        elif cyclic:
            return adjacent - sequence
        else:
            return set()

    def incoming(self, vertex, direct=True, cyclic=False):
        return self._adjacent(vertex, direct, cyclic, False)

    def outgoing(self, vertex, direct=True, cyclic=False):
        return self._adjacent(vertex, direct, cyclic, True)

    def copy(self):
        """ Makes a copy of the layout for modification. """
        layout = _Layout(self.g, self.seq)
        layout.rows = {v: self.rows[v].copy(layout) for v in self.seq}
        layout.cycles = {tuple(c) for c in self.cycles}
        layout.paths = {v: set(tuple(p) for p in self.paths[v])
                        for v in layout.paths}

        return layout


def _rearrange_lines(row):
    """ Move around lines such that only one line has the next vertex, with
        all others avoiding that vertex.
    """
    next_row = row.next_
    if next_row is None:
        return

    while row.column >= len(row.end):
        row.end.append(set())

    if any(next_row.vertex in c for c in row.end):
        if {next_row.vertex} in row.end:
            # Column dedicated to next vertex already exists; use it
            next_col = row.end.index({next_row.vertex})
        else:
            next_col = row.column
        # Move all references for next vertex to this column
        for vertices in row.end:
            vertices.discard(next_row.vertex)
        row.end[next_col].add(next_row.vertex)
    else:
        # New vertex; add column to lines
        row.end.append({next_row.vertex})

    temp = set()
    # Move all other references from this column
    for v in row.end[row.column] - {next_row.vertex}:
        temp.add(v)
        row.end[row.column].remove(v)

    if temp:
        # Add new line to left of the next vertex
        row.end.insert(row.column, temp)


def _remove_lines(row):
    """ Remove all lines that are empty or duplicates of other lines in this
        row.

        If lines with single vertices exist, these vertices are removed from
        all other lines.
    """
    single = set()
    seen = []
    to_remove = []
    # Find lines with only one vertex and mark duplicates for removal
    for i, c in enumerate(row.end):
        if len(c) == 1:
            single |= c
        if c not in seen:
            seen.append(c)
        else:
            to_remove.append(i)

    # Remove all duplicate lines that lead to a single vertex
    for i in reversed(to_remove):
        del row.end[i]

    # Remove vertices from lines that already exist in other single lines
    for c in row.end:
        if len(c) > 1:
            c -= single

    # Clean up any empty columns
    for i in reversed(range(len(row.end))):
        if not row.end[i]:
            del row.end[i]


def _add_outgoing_cycles(row):
    """ Add paths for cycles starting at this vertex. """
    if row.vertex not in [p[0] for p in row.layout.cycles]:
        return

    c = column = row.column
    # Add lines for cycles
    for u, v in row.layout.cycles:
        if row.vertex != u:
            continue

        row.start[column].add(v)
        row.end.insert(c, {v})
        row.cycles_start[c] = (u, v)
        c += 1


def _add_incoming_cycles_next(row):
    """ Add paths for cycles ending at the next vertex. They do not necessarily
        stay on the same columns as outgoing paths.
    """
    next_row = row.next_
    if next_row is None:
        return

    cycles = row.layout.incoming(next_row.vertex, direct=False, cyclic=True)
    if not cycles:
        return

    # Column for vertex in next row should have been set already
    while next_row.column > len(row.start):
        row.start.append(set())

    column = next_row.column
    new_column = row.column
    # Order from furthest away to nearest
    incoming = [v for v in reversed(row.layout.seq) if v in cycles]
    for v in incoming:
        if v == next_row.vertex:
            # Don't want self-cycles
            continue
        # Insert new column for incoming cycle and track original vertex
        new_cycle = (v, next_row.vertex)
        row.layout.cycles.add(new_cycle)
        row.cycles_end[column] = new_cycle
        row.start.insert(column, {next_row.vertex})
        if new_column >= column:
            new_column += 1
        column += 1

    # Modify original vertex column and its lines
    if new_column > row.column:
        incoming = row.incoming_lines
        if incoming is not None:
            incoming[row.column:] = ([set()] * (new_column - row.column)
                                     + incoming[row.column:])
        row.column = new_column


def _set_next_column(row):
    """ Sets the column of the next vertex based on the ending lines for this
        row.
    """
    next_row = row.next_
    if next_row is None:
        # Last in sequence; don't need to set next vertex
        return

    found = [c for c in row.end if next_row.vertex in c]
    if not found:
        raise ValueError("Vertex %r for next row not in lines %r." %
                         (next_row.vertex, row.end))
    elif len(found) > 2:
        raise ValueError("Next vertex %r is found in multiple columns for "
                         "lines %r." % (next_row.vertex, row.end))
    elif len(found[0]) > 1:
        raise ValueError("Multiple vertices found in lines %r for column where "
                         "next vertex %r is supposed to be." %
                         (row.end, next_row.vertex))

    next_row.column = row.end.index({next_row.vertex})


def _pad_columns(row):
    """ Add empty columns to either start of this row or end of last row such
        that they have the same number of columns.
    """
    incoming, outgoing = row.incoming_lines, row.outgoing_lines

    if incoming is None or outgoing is None:
        # Start or end of line; don't need to pad them
        return

    while len(incoming) < len(outgoing):
        incoming.append(set())

    while len(incoming) > len(outgoing):
        outgoing.append(set())

    while not incoming[-1] and not outgoing[-1]:
        del incoming[-1], outgoing[-1]


def _set_lines(layout):
    """ Set all lines and moving vertices into the correct columns. """
    if not layout.seq:
        return

    first_v = layout.seq[0]
    # Place first vertex in column 0
    layout.rows[first_v].column = 0

    cycles = layout.incoming(first_v, direct=False, cyclic=True)
    if cycles:
        pairs = [(v, first_v) for v in reversed(layout.seq) if v in cycles]
        # Add new row for cycle before first vertex
        layout.seq.insert(0, None)
        layout.cycles |= set(pairs)
        layout.rows[None] = _Row(
            layout, None,
            start=[{first_v}] * len(cycles),
            end=[{first_v}],
            cycles_end={c: p for c, p in enumerate(pairs)}
        )

    for v in layout.seq:
        if v is None:
            continue

        row = layout.rows[v]
        # Set starting lines to previous row or a single empty column
        if row.previous is not None:
            row.start = [set(c) for c in row.incoming_lines]
        else:
            row.start = [set()]

        # Remove current vertex, any outgoing cycles and add new columns
        to_remove = {v} | {p[1] for p in layout.cycles}
        for c in row.start:
            c -= to_remove

        # Add all outgoing vertices to current column except self
        row.start[row.column] |= layout.outgoing(v)

        row.end = [set(c) for c in row.start]

        _rearrange_lines(row)
        _remove_lines(row)
        _add_outgoing_cycles(row)
        _set_next_column(row)
        _add_incoming_cycles_next(row)
        _pad_columns(row)

        if layout.max_col is not None and len(row.end) > layout.max_col:
            raise MaxColumnError


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

    return sum(1 for (a, b), (c, d) in itertools.combinations(paths, 2)
               if (a - c) * (b - d) < 0)


def _count_all_crossings(layout):
    """ Counts all crossings within the layout. """
    return sum(_count_crossings(r.start, r.end) for r in layout.rows.values())


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


def _median_order(row, forward=True):
    """ Sets order of a row by using the median of the positions of adjacent
        lines for each line.
    """
    median = {}
    paths = _draw_paths_row(row.start, row.end)

    len_ = len(row.end) if forward else len(row.start)
    i, j = (0, 1) if forward else (1, 0)

    for c in range(len_):
        median[c] = _median([p[i] for p in paths if p[j] == c])

    # Vertices are left in place if they have no adjacent vertices
    moved = iter(sorted(i for i in range(len_) if median[i] >= 0))
    ordered = [next(moved) if median[i] >= 0 else i for i in range(len_)]

    if ordered != list(range(len_)):
        return ordered


def _transpose_order(row, forward=True):
    """ Swaps lines within a row to see if the number of crossings improve. """
    len_ = len(row.end) if forward else len(row.start)

    if len_ < 2:
        return

    order = list(range(len_))
    crossings = _count_crossings(row.start, row.end)

    improved = True
    while improved:
        improved = False
        for i in range(len_ - 1):
            new_order = order[:i] + [order[i + 1], order[i]] + order[i + 2:]
            if forward:
                temp = [set(row.end[j]) for j in new_order]
                new_crossings = _count_crossings(row.start, temp)
            else:
                temp = [set(row.start[j]) for j in new_order]
                new_crossings = _count_crossings(temp, row.end)

            if new_crossings < crossings:
                order = new_order
                crossings = new_crossings
                improved = True

    if order != list(range(len_)):
        return order


def _set_new_order(row, forward, new_order):
    """ Set row (or next row if working in forward direction) using new order.
    """
    set_row = row.next_ if forward else row
    if set_row is not None:
        set_row.rearrange(new_order)


def _order_lines(layout):
    """ Processes layout to reduce the number of crossings.

        Heuristics based on the dot algorithm are used where over a number of
        iterations the graph is transversed forwards and backwards.

        Rows are set to the new orderings if the number of crossings is reduced.
    """
    # Make copies of current columns and lines to modify
    nl = layout.copy()
    crossings = _count_all_crossings(nl)
    enum_seq = list(enumerate(nl.seq))

    def iter_seq(f): return iter(enum_seq) if f else reversed(enum_seq)

    for i in range(ORDER_ITERATIONS):
        # Set line orderings with medians
        # alternate between iterating forwards and backwards
        forward = i % 2 == 0

        for j, v in iter_seq(forward):
            row = nl.rows[v]
            after_median = _median_order(row, forward)
            if after_median is not None:
                _set_new_order(row, forward, after_median)

        for j, v in iter_seq(forward):
            row = nl.rows[v]
            after_transpose = _transpose_order(row, forward)
            if after_transpose is not None:
                _set_new_order(row, forward, after_transpose)

        # If crossings have been improved, copy them back into original data
        new_crossings = _count_all_crossings(nl)
        if new_crossings < crossings:
            layout.rows = {v: r.copy(layout) for v, r in nl.rows.items()}
            crossings = new_crossings


def _classify_paths(layout, paths, row):
    """ Define each path as cyclic or not, and attach the vertex they follow
        back to.
    """
    new_paths = set()
    set_paths = set(paths)

    next_row = row.next_

    def find_key(dict_, v):
        key = next((k for k in dict_ if dict_[k] == v), None)
        if key is None:
            raise ValueError("Dict %r does not have value %r" % (dict_, v))

        return key

    for u, w in layout.cycles:
        if row.vertex == u:
            # Start of cycle here
            path = row.column, find_key(row.cycles_start, (u, w))
            set_paths.remove(path)
            new_paths.add((*path, -1, w))
        if next_row is not None and next_row.vertex == w:
            # End of cycle here
            path = find_key(row.cycles_end, (u, w)), next_row.column
            set_paths.remove(path)
            new_paths.add((*path, 1, u))

    # Set remainder of paths
    for p in set_paths:
        new_paths.add((*p, 0, None))

    return new_paths


def _draw_paths(layout):
    """ Draws all paths and adds to layout. """
    for v in layout.seq:
        row = layout.rows[v]
        paths = _draw_paths_row(row.start, row.end)
        layout.paths[v] = _classify_paths(layout, paths, row)


def draw_graph(graph, sequence=None, max_columns=None):
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
        :param max_columns: Maximum number of columns. If a row is detected to
        exceed this maximum, the calculations stop.
        :returns: A list of tuples of the form (vertex, column, paths) where
        paths is the set of all paths between specific columns in that row.
    """
    gl = _Layout(graph, sequence, max_columns)

    _set_lines(gl)
    _order_lines(gl)
    _draw_paths(gl)

    data = [(v, gl.rows[v].column, sorted(gl.paths[v])) for v in gl.seq]

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
            within edge are removed as well.
        """
        if v1 not in self._v:
            raise KeyError(v1)
        if v2 not in self._v[v1]:
            raise KeyError(v2)

        self._v[v1].discard(v2)

        if delete and not self._v[v1] and v1 not in self.tails:
            del self[v1]
        if delete and not self._v[v2] and v2 not in self.tails:
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
            delete is True, any orphaned vertices on path are removed as well.
        """
        try:
            edges = path.edges
        except AttributeError:
            edges = path

        for e in edges:
            if not self.contains_edge(e):
                raise ValueError("Edge %r on path %r does not exist in graph "
                                 "%r" % (e, path, self))

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

    def draw(self, sequence=None, max_columns=None):
        """ Lays out graph using sequence.

            :param sequence: Use sequence to draw graph, If it is None the
            sequence is generated instead.
            :param max_columns: Maximum number of columns. If any row exceeds
            this maximum no layout will be returned.
            :returns: List of dictionaries, ordered using sequence, with
            vertex name, column and lines before/after.
        """
        return draw_graph(self, sequence, max_columns)


def _service_stops(service_id, direction=None):
    """ Get dictionary of distinct stops for a service.

        :param service_id: Service ID.
        :param direction: Groups journey patterns by direction.
        :returns: Dictionary with ATCO codes as keys for stop point objects.
    """
    pairs = (
        db.session.query(models.JourneyLink.stop_point_ref,
                         models.JourneyPattern.direction)
        .join(models.JourneyPattern.links)
        .filter(models.JourneyPattern.service_ref == service_id)
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


def service_graph(service_id, direction):
    """ Get list of stops and their preceding and following stops for a service.

        :param service_id: Service ID.
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
        .filter(models.JourneyPattern.service_ref == service_id,
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


def service_stop_list(service_id, direction):
    """ Queries all patterns for a service and creates list of stops sorted
        topologically.

        :param service_id: Service ID.
        :param direction: Groups journey patterns by direction - False for
        outbound and True for inbound.
    """
    dict_stops = _service_stops(service_id, direction)
    if not dict_stops:
        raise ValueError("No stops exist for service ID %s" % service_id)

    graph = service_graph(service_id, direction)
    stops = [dict_stops[v] for v in graph.sequence()]

    return stops


def service_json(service_id, reverse):
    """ Creates geometry JSON data for map.

        :param service_id: Service ID.
        :param reverse: Groups journey patterns by direction - False for
        outbound and True for inbound.
    """
    service = (
        models.Service.query
        .join(models.Service.patterns)
        .join(models.JourneyPattern.local_operator)
        .options(db.contains_eager(models.Service.local_operators),
                 db.contains_eager(models.Service.patterns))
        .filter(models.Service.id == service_id)
        .one_or_none()
    )

    if service is None:
        return None

    # Check line patterns - is there more than 1 direction?
    direction, mirrored = service.has_mirror(reverse)

    dict_stops = _service_stops(service.id, direction)
    if not dict_stops:
        raise ValueError("No stops exist for service %r" % service.id)

    graph = service_graph(service.id, direction)
    paths, sequence = graph.analyse()

    def coordinates(vertex):
        stop = dict_stops[vertex]
        return stop.longitude, stop.latitude

    # Serialise data
    lines = [[coordinates(v) for v in p] for p in paths if len(p) > 1]
    route_data = [dict_stops[s].to_geojson() for s in sequence]

    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": lines
        },
        "properties": {
            "service": service.id,
            "line": service.line,
            "description": service.description,
            "direction": direction
        }
    }

    data = {
        "service": service.id,
        "line": service.line,
        "description": service.description,
        "direction": direction,
        "operator": [o.name for o in service.local_operators],
        "mirrored": mirrored,
        "sequence": route_data,
        "paths": geojson
    }

    return data
