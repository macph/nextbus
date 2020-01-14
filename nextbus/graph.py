"""
Draws a route graph for a service.
"""
import collections
from collections import abc
import functools
import itertools

from nextbus import db, models


MAX_COLUMNS = 5


class MaxColumnError(Exception):
    """ Used if a row's columns exceed the maximum allowed by the layout. """
    pass


class LayoutError(Exception):
    """ Used if errors encountered in laying out graph. """
    pass


def _coalesce(*args):
    """ Returns first non-null argument, or None if all are null. """
    return next((a for a in args if a is not None), None)


class Path(abc.Sequence):
    """ Immutable path as sequence of vertices. """
    def __init__(self, vertices=None):
        self._v = tuple(vertices) if vertices is not None else ()

    def __repr__(self):
        return f"<Path({self._v!r}, cyclic={self.cyclic})>"

    def __getitem__(self, index):
        return self._v[index]

    def __contains__(self, vertex):
        return vertex in self._v

    def __len__(self):
        return len(self._v)

    def __eq__(self, other):
        if not hasattr(other, "_v"):
            return False
        elif self._v == other._v:
            return True
        elif len(self._v) != len(other._v):
            return False
        elif not self.cyclic or not other.cyclic:
            return False
        else:
            list_ = other._v[:-1]
            return any(sublist == list_ for sublist in self._slice())

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def cyclic(self):
        return len(self._v) > 1 and self._v[0] == self._v[-1]

    @property
    def edges(self):
        return [(self._v[i], self._v[i+1]) for i in range(len(self._v) - 1)]

    def _slice(self, length=None):
        """ Yields slices of path of a set length. If the path is cyclic the
            slice will wrap around the list.
        """
        list_ = self._v[:-1] if self.cyclic else self._v[:]
        len_a = len(list_)
        len_b = _coalesce(length, len_a)

        if len_a < len_b:
            return
        elif self.cyclic:
            for i in range(len_a):
                sub = list_[i:i + len_b]
                if i + len_b > len_a:
                    sub += list_[:i + len_b - len_a]
                yield sub
        else:
            for i in range(len_a - len_b + 1):
                yield list_[i:i + len_b]

    def contains_edge(self, edge):
        """ Checks if edge is in path. """
        return edge in self.edges

    def contains_path(self, path):
        """ Checks if path is within this path. """
        if not self:
            return False
        elif self == path:
            return True
        elif path.cyclic:
            return False
        else:
            return any(sublist == path._v for sublist in self._slice(len(path)))

    def make_acyclic(self):
        """ Create an acyclic path by removing the last vertex. """
        return Path(self[:-1]) if self.cyclic else Path(self)

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
            raise ValueError(
                f"Cycle {cycle!r} still in set for graph {graph!r}"
            )


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
        return [], sorted(g.isolated, key=graph.sort)
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
            new_paths = g.search_paths(vertex, forward=forward).values()
        except KeyError:
            continue
        if not any(new_paths):
            continue

        # Add paths to list
        longest = max(sorted(new_paths, key=graph.path_sort), key=len)
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

    if g.vertices:
        # Expect all vertices and edges to be removed from connected graph.
        raise ValueError(
            f"Vertices {g.vertices!r} still left over from graph {g0!r}"
        )

    _rearrange_cycles(g0, sequence)

    return paths, sequence


class LayoutRow:
    """ Helper class to hold data for each row in a layout. """
    def __init__(self, layout, vertex, column=None, start=None, end=None,
                 cycles_start=None, cycles_end=None):
        if vertex not in layout.sequence:
            raise ValueError(
                f"Vertex {vertex!r} not in sequence {layout.sequence!r}."
            )

        self.layout = layout
        self.vertex = vertex
        self.column = column
        self.start = _coalesce(start, [])
        self.end = _coalesce(end, [])
        self.cycles_start = _coalesce(cycles_start, {})
        self.cycles_end = _coalesce(cycles_end, {})

        self._is_set = False

    def __repr__(self):
        return f"<LayoutRow({self.layout!r}, {self.vertex!r}, {self.column!r})>"

    @property
    def index(self):
        """ Index of vertex in layout's sequence. """
        return self.layout.sequence.index(self.vertex)

    @property
    def previous(self):
        """ Previous row, or None if this is the first row. """
        if self.index > 0:
            return self.layout.rows[self.layout.sequence[self.index - 1]]
        else:
            return None

    @property
    def next(self):
        """ Next row, or None if this is the last row. """
        if self.index < len(self.layout.sequence) - 1:
            return self.layout.rows[self.layout.sequence[self.index + 1]]
        else:
            return None

    def copy(self, new_layout=None):
        """ Returns another LayoutRow with the same data. If new_layout is not
            None, the new row will be set to the new layout.
        """
        return LayoutRow(
            layout=_coalesce(new_layout, self.layout),
            vertex=self.vertex,
            column=self.column,
            start=[set(c) for c in self.start],
            end=[set(c) for c in self.end],
            cycles_start={c: tuple(p) for c, p in self.cycles_start.items()},
            cycles_end={c: tuple(p) for c, p in self.cycles_end.items()}
        )

    def _rearrange_lines(self):
        """ Move around lines such that only one line has the next vertex, with
            all others avoiding that vertex.
        """
        next_row = self.next
        if next_row is None:
            return

        while self.column >= len(self.end):
            self.end.append(set())

        if any(next_row.vertex in c for c in self.end):
            if {next_row.vertex} in self.end:
                # Column dedicated to next vertex already exists; use it
                next_col = self.end.index({next_row.vertex})
            else:
                next_col = self.column
            # Move all references for next vertex to this column
            for vertices in self.end:
                vertices.discard(next_row.vertex)
            self.end[next_col].add(next_row.vertex)
        else:
            # New vertex; add column to lines
            self.end.append({next_row.vertex})

        temp = set()
        # Move all other references from this column
        for v in self.end[self.column] - {next_row.vertex}:
            temp.add(v)
            self.end[self.column].remove(v)

        if temp:
            # Add new line to left of the next vertex
            self.end.insert(self.column, temp)

    def _remove_lines(self):
        """ Remove all lines that are empty or duplicates of other lines in this
            row.

            If lines with single vertices exist, these vertices are removed from
            all other lines.
        """
        single = set()
        seen = []
        to_remove = []
        # Find lines with only one vertex and mark duplicates for removal
        for i, c in enumerate(self.end):
            if len(c) == 1:
                single |= c
            if c not in seen:
                seen.append(c)
            else:
                to_remove.append(i)

        # Remove all duplicate lines that lead to a single vertex
        for i in reversed(to_remove):
            del self.end[i]

        # Remove vertices from lines that already exist in other single lines
        for c in self.end:
            if len(c) > 1:
                c -= single

        # Clean up any empty columns
        for i in reversed(range(len(self.end))):
            if not self.end[i]:
                del self.end[i]

    def _add_outgoing_cycles(self):
        """ Add paths for cycles starting at this vertex. """
        if self.vertex not in [p[0] for p in self.layout.cycles]:
            return

        col = min(self.column, len(self.end))
        # Add lines for cycles
        for u, v in self.layout.cycles:
            if self.vertex != u:
                continue

            self.start[self.column].add(v)
            self.end.insert(col, {v})
            self.cycles_start[col] = (u, v)
            col += 1

    def _add_incoming_cycles_next(self):
        """ Add paths for cycles ending at the next vertex. They do not
            necessarily stay on the same columns as outgoing paths.
        """
        next_row = self.next
        if next_row is None:
            return

        cycles = self.layout.incoming(next_row.vertex, direct=False,
                                      cyclic=True)
        if not cycles:
            return

        # Column for vertex in next row should have been set already
        while next_row.column > len(self.start):
            self.start.append(set())

        # Order from furthest away to nearest
        incoming = [v for v in reversed(self.layout.sequence) if v in cycles]
        diff = 0
        for v in incoming:
            if v == next_row.vertex:
                # Don't want self-cycles
                continue
            new_cycle = (v, next_row.vertex)
            # Insert new column for incoming cycle
            new_column = next_row.column + diff
            self.layout.cycles.add(new_cycle)
            self.cycles_end[new_column] = new_cycle
            self.start.insert(new_column, {next_row.vertex})
            diff += 1

        if diff > 0:
            previous_row = self.previous
            if previous_row is not None:
                # Modify ending lines for previous row
                for _ in range(diff):
                    previous_row.end.insert(next_row.column, set())
                # Modify starting cycles for previous row as well
                previous_cycles = previous_row.cycles_start
                for c in sorted(previous_cycles, reverse=True):
                    if c >= next_row.column:
                        previous_cycles[c + diff] = previous_cycles.pop(c)

            if self.column >= next_row.column:
                self.column += diff

    def _set_next_column(self):
        """ Sets the column for the next row based on the ending lines for this
            row.
        """
        next_row = self.next
        if next_row is None:
            # Last in sequence; don't need to set next vertex
            return

        found = [c for c in self.end if next_row.vertex in c]
        if not found:
            raise LayoutError(
                f"Vertex {next_row.vertex!r} for next row not in lines "
                f"{self.end!r}."
            )
        elif len(found) > 2:
            raise LayoutError(
                f"Next vertex {next_row.vertex!r} is found in multiple columns "
                f"for lines {self.end!r}."
            )
        elif len(found[0]) > 1:
            raise LayoutError(
                f"Multiple vertices found in lines {self.end!r} for column "
                f"where next vertex {next_row.vertex!r} is supposed to be."
            )

        next_row.column = self.end.index({next_row.vertex})

    def _pad_columns(self):
        """ Add empty columns to either start of this row or end of last row
            such that they have the same number of columns.
        """
        previous_row = self.previous

        if previous_row is None:
            # Start of layout; don't need to pad columns
            return

        while len(previous_row.end) < len(self.start):
            previous_row.end.append(set())

        while len(previous_row.end) > len(self.start):
            self.start.append(set())

        while not previous_row.end[-1] and not self.start[-1]:
            del previous_row.end[-1], self.start[-1]

    def set_lines(self):
        """ Sets lines for this row. """
        if self._is_set:
            return

        # Set starting lines to previous row or a single empty column
        previous_row = self.previous
        if previous_row is not None:
            self.start = [set(c) for c in previous_row.end]
        else:
            self.start = [set()]
        # Remove current vertex, any outgoing cycles and add new columns
        to_remove = {self.vertex} | {p[1] for p in self.layout.cycles}
        for c in self.start:
            c -= to_remove
        # Add all outgoing vertices to current column except self
        self.start[self.column] |= self.layout.outgoing(self.vertex)

        self.end = [set(c) for c in self.start]

        self._rearrange_lines()
        self._remove_lines()
        self._add_outgoing_cycles()
        self._set_next_column()
        self._add_incoming_cycles_next()
        self._pad_columns()

        self._is_set = True

    def lines(self, *, start=None, end=None):
        """ Draws lines as a set of tuples from the starting and ending lines.

            All lines are assumed to split up, that is, no ending line would
            have more vertices than any starting line.

            :param start: Use this set of lines instead of row's starting lines.
            :param end: Use this set of lines instead of row's end lines.
        """
        starting = _coalesce(start, self.start)
        ending = _coalesce(end, self.end)

        paths = set()
        for c0, v0 in enumerate(starting):
            if v0 and v0 in ending:
                paths.add((c0, ending.index(v0)))
                continue
            for c1, v1 in enumerate(ending):
                if v1 and v0 >= v1:
                    paths.add((c0, c1))

        return paths

    def count_crossings(self, *, start=None, end=None):
        """ Counts crossings within a row defined by starting and ending lines.

            Each pair of paths are checked by seeing if the differences in
            starting and ending vertices' positions are non-zero and of opposite
            signs.

            :param start: Use this set of lines instead of row's starting lines.
            :param end: Use this set of lines instead of row's end lines.
        """
        paths = self.lines(start=start, end=end)

        return sum(1 for (a, b), (c, d) in itertools.combinations(paths, 2)
                   if (a - c) * (b - d) < 0)

    def rearrange(self, new_order):
        """ Moves lines and columns around on starting lines for this row and
            ending lines for the last row.

            :param new_order: List of indices, eg [0, 2, 1] for a 3-column row
            will swap the second and third columns.
        """
        previous = self.previous

        len_incoming = len(previous.end) if previous is not None else None
        len_outgoing = len(self.start)

        if previous is not None and len_incoming != len_outgoing:
            raise LayoutError(
                f"Incoming lines {previous.end!r} and outgoing lines "
                f"{self.start!r} do not have the same number of columns."
            )

        if set(new_order) != set(range(len_outgoing)):
            if previous is not None:
                raise ValueError(
                    f"New order {new_order!r} is not a permutation with same "
                    f"length as incoming lines {previous.end} or outgoing "
                    f"lines {self.start!r} for row {self!r}."
                )
            else:
                raise ValueError(
                    f"New order {new_order!r} is not a permutation with same "
                    f"length as outgoing lines {self.start!r} for row {self!r}"
                )

        if new_order == list(range(len_outgoing)):
            # Same order already; leave as is
            return

        self.start = [self.start[i] for i in new_order]

        if previous is not None:
            previous.end = [previous.end[i] for i in new_order]
            # Column data for starting cycles is on previous row
            # Can ignore cycles on last row - they won't be crossed
            previous.cycles_start = {new_order.index(c): p for c, p
                                     in previous.cycles_start.items()}

        self.cycles_end = {new_order.index(c): p for c, p
                           in self.cycles_end.items()}

        self.column = new_order.index(self.column)

    def paths(self):
        """ Draws paths for each row and classify them based on whether they
            part of cycles.
        """
        set_paths = self.lines()
        new_paths = set()

        next_row = self.next
        # Reverse cycles dictionaries - the cycles should be unique already
        start = {p: c for c, p in self.cycles_start.items()}
        end = {p: c for c, p in self.cycles_end.items()}

        for u, v in self.layout.cycles:
            if self.vertex == u:
                # Start of cycle here
                path = self.column, start[(u, v)]
                set_paths.remove(path)
                new_paths.add((*path, -1, v))
            if next_row is not None and next_row.vertex == v:
                # End of cycle here
                path = end[(u, v)], next_row.column
                set_paths.remove(path)
                new_paths.add((*path, 1, u))

        # Set remainder of paths
        for p in set_paths:
            new_paths.add((*p, 0, None))

        return new_paths


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
    paths = row.paths()

    len_ = len(row.end) if forward else len(row.start)
    i, j = (0, 1) if forward else (1, 0)

    for c in range(len_):
        median[c] = _median([p[i] for p in paths if p[j] == c])

    # Vertices are left in place if they have no adjacent vertices
    moved = iter(sorted(i for i in range(len_) if median[i] >= 0))
    order = [next(moved) if median[i] >= 0 else i for i in range(len_)]

    return order


def _transpose_order(row, forward=True):
    """ Swaps lines within a row to see if the number of crossings improve. """
    len_ = len(row.end) if forward else len(row.start)
    order = list(range(len_))

    if len_ < 2:
        return order

    crossings = row.count_crossings()
    improved = True
    while improved:
        improved = False
        for i in range(len_ - 1):
            new_order = order[:i] + [order[i + 1], order[i]] + order[i + 2:]
            if forward:
                temp = [set(row.end[j]) for j in new_order]
                new_crossings = row.count_crossings(end=temp)
            else:
                temp = [set(row.start[j]) for j in new_order]
                new_crossings = row.count_crossings(start=temp)

            if new_crossings < crossings:
                order = new_order
                crossings = new_crossings
                improved = True

    return order


class LayoutColumns(abc.Mapping):
    """ Column view for Layout. """
    def __init__(self, layout):
        self.layout = layout

    def __len__(self):
        return len(self.layout.rows)

    def __iter__(self):
        return iter(self.layout.rows)

    def __getitem__(self, item):
        return self.layout.rows[item].column


class Layout:
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
        :param max_columns: Maximum number of columns. If a row is detected to
        exceed this maximum, the calculations stop and a MaxColumnError raised.
        :param ordered: Try ordering vertices and lines within each row to
        reduce crossings.
        :param _create: Internal parameter to draw layout on initialization.
    """
    ORDER_ITERATIONS = 8

    def __init__(self, graph, max_columns=None, ordered=True, _create=True):
        self.g = graph
        self.sequence = graph.sequence()
        self.max_col = max_columns
        self.ordered = ordered

        self.rows = {v: LayoutRow(self, v) for v in self.sequence}
        self.columns = LayoutColumns(self)
        self.cycles = set()
        self.paths = {}

        if _create:
            self._set_lines()
            self._order_lines()
            self._draw_paths()

    def __repr__(self):
        return f"<Layout({self.g!r})>"

    def _adjacent(self, vertex, direct, cyclic, forward):
        index = self.sequence.index(vertex)
        if forward:
            adjacent = self.g.following(vertex)
            sequence = set(self.sequence[index + 1:])
        else:
            adjacent = self.g.preceding(vertex)
            sequence = set(self.sequence[:index])

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

    def copy_from(self, layout):
        """ Copies data from another layout. """
        if self.g != layout.g or self.sequence != layout.sequence:
            raise ValueError(
                f"This layout {self!r} and other layout {layout!r} do not "
                f"reference the same graph."
            )

        self.rows = {v: layout.rows[v].copy(self) for v in layout.sequence}
        self.cycles = {tuple(c) for c in layout.cycles}
        self.paths = {v: set(tuple(p) for p in layout.paths[v])
                      for v in layout.paths}

    def copy(self):
        """ Makes a copy of the layout for modification. """
        layout = Layout(self.g, _create=False)
        layout.copy_from(self)

        return layout

    def crossings(self):
        """ Counts all crossings within the layout. """
        return sum(r.count_crossings() for r in self.rows.values())

    def _set_lines(self):
        """ Set all lines and move vertices into the correct columns. """
        if not self.sequence:
            return

        first_v = self.sequence[0]
        # Place first vertex in column 0
        self.rows[first_v].column = 0

        cycles = self.incoming(first_v, direct=False, cyclic=True)
        if cycles:
            pairs = [(v, first_v) for v in reversed(self.sequence)
                     if v in cycles]
            # Add new row for cycle before first vertex
            self.sequence.insert(0, None)
            self.cycles |= set(pairs)
            self.rows[None] = LayoutRow(
                self, None,
                start=[{first_v}] * len(cycles),
                end=[{first_v}],
                cycles_end={c: p for c, p in enumerate(pairs)}
            )

        for v in self.sequence:
            if v is None:
                continue

            row = self.rows[v]
            row.set_lines()

            if self.max_col is not None and len(row.end) > self.max_col:
                raise MaxColumnError

    def _order_lines(self):
        """ Processes layout to reduce the number of crossings.

            Heuristics based on the dot algorithm are used where over a number
            of iterations the graph is transversed forwards and backwards.

            Rows are set to the new orderings if the number of crossings is
            reduced.
        """
        if not self.ordered:
            return

        # Make copies of current columns and lines to modify
        nl = self.copy()
        crossings = nl.crossings()

        # Iterate over rows in either order
        # If iterating from start, rearrange the next row
        # If iterating from end, rearrange this row
        rows_forward = [(nl.rows[v], nl.rows[v].next) for v in nl.sequence[:-1]]
        rows_reverse = [(nl.rows[v], nl.rows[v]) for v in nl.sequence[-2::-1]]

        for i in range(self.ORDER_ITERATIONS):
            # Set line orderings with medians
            # alternate between iterating forwards and backwards
            forward = i % 2 == 0
            rows = rows_forward if forward else rows_reverse

            for row, set_row in rows:
                set_row.rearrange(_median_order(row, forward))

            for row, set_row in rows:
                set_row.rearrange(_transpose_order(row, forward))

            # If crossings have been improved, copy them back into original data
            new_crossings = nl.crossings()
            if new_crossings < crossings:
                self.copy_from(nl)
                crossings = new_crossings

    def _draw_paths(self):
        """ Draws all paths and adds to layout. """
        for v in self.sequence:
            self.paths[v] = self.rows[v].paths()

    def serialize(self):
        """ Outputs layout in form suitable for JSON.

            :returns: A list of lists of the form [vertex, column, paths] where
            paths is the set of all paths between specific columns in that row.
        """
        data = []
        for v in self.sequence:
            paths = sorted(list(p) for p in self.paths[v])
            data.append([v, self.columns[v], paths])

        return data


def _memoize_graph(graph, method):
    """ Wraps graph method in a function that remembers adjacency list and last
        result.
    """
    adj = None
    result = None

    @functools.wraps(method)
    def _method(*args, **kwargs):
        nonlocal adj, result

        new_adj = graph.adj
        if adj != new_adj:
            result = method(*args, **kwargs)
            adj = new_adj

        return result

    return _method


class Graph:
    """ Directed graph.

        :param pairs: Edges as iterables of length 2.
        :param singles: Vertices without any edges.
        :param sort: Optional function to sort vertices by when comparing paths
    """
    def __init__(self, pairs=None, singles=None, sort=None):
        self._v = collections.defaultdict(set)
        if pairs is not None:
            for v1, v2 in pairs:
                self.add_edge(v1, v2)
        if singles is not None:
            for v in singles:
                self.add_vertex(v)

        if sort is not None:
            self._sort = sort
        else:
            def do_nothing(item):
                return item
            self._sort = do_nothing

        self.analyse = _memoize_graph(self, self.analyse)
        self.draw = _memoize_graph(self, self.draw)

    def __repr__(self):
        return f"<Graph({set(self)!r})>" if self else "<Graph()>"

    def __iter__(self):
        return iter(self.vertices)

    def __bool__(self):
        return bool(self.vertices)

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

    @classmethod
    def from_adj(cls, adj_list):
        """ Creates graph from adjacency list as a dict of vertices and
            iterables of following vertices.
        """
        adj = {}
        for start, end in adj_list.items():
            adj[start] = set(end)

        for v in set().union(*adj_list.values()):
            if v not in adj:
                adj[v] = set()

        new_graph = cls()
        new_graph._v = adj

        return new_graph

    @property
    def adj(self):
        """ Adjacency list for this graph as a dictionary of sets. """
        return {v: set(w) for v, w in self._v.items()}

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

    @property
    def sort(self):
        """ Ranking function for sorting vertices. """
        return self._sort

    @property
    def path_sort(self):
        """ Function for sorting paths by their rankings. """
        sort = self._sort

        def path_sort(path):
            return tuple(sort(u) for u in path)

        return path_sort

    def copy(self):
        """ Makes a copy of the graph. """
        return Graph(self.edges, self.isolated, self._sort)

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
            raise TypeError(f"{edge!r} is not a tuple of two values") from err

        return u in self._v and v in self._v[u]

    def contains_path(self, path):
        return all(self.contains_edge(e) for e in path.edges)

    def add_vertex(self, v):
        if v is not None and v not in self._v:
            self._v[v] = set()

    def remove_vertex(self, v):
        del self._v[v]
        for u in self._v:
            self._v[u].discard(v)

    def add_edge(self, v1, v2):
        if v2 is not None:
            self._v[v1].add(v2)
            if v2 not in self._v:
                self._v[v2] = set()
        elif v1 not in self._v:
            self._v[v1] = set()

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
            self.remove_vertex(v1)
        if delete and not self._v[v2] and v2 not in self.tails:
            self.remove_vertex(v2)

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
                raise TypeError(f"{e!r} is not a tuple of two values") from err
            self.add_edge(v1, v2)

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
                raise ValueError(
                    f"Edge {e!r} on path {path!r} does not exist in graph "
                    f"{self!r}"
                )

        for v1, v2 in edges:
            self.remove_edge(v1, v2, delete)

    def update(self, adj):
        """ Updates graph with an adjacency list in the form of a dictionary of
            vertex heads with neighbouring nodes as iterables.
        """
        for u in dict(adj):
            if not adj[u]:
                self.add_vertex(u)
                continue
            for v in adj[u]:
                self.add_edge(u, v)

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

        connected = [Graph(s, sort=self._sort) for s in groups.values()]
        isolated = [Graph(singles=[v], sort=self._sort) for v in self.isolated]

        if connected or isolated:
            return connected + isolated
        else:
            return [Graph()]

    def search_paths(self, v, t=None, forward=True):
        """ Does BFS on graph to find shortest paths from vertex v to all other
            vertices (including itself), or vice versa if forward is False.

            If target vertex `t` is None, all paths are searched and returned as
            a dictionary of vertices with shortest paths. Otherwise, only the
            shortest path starting at `v` and ending at `t` is returned.

            Edges following vertices are sorted to give a consistent result.
        """
        if v not in self:
            raise KeyError(v)
        if t is not None and t not in self:
            raise KeyError(v)

        paths = {}
        queue = collections.deque()

        # Add all immediately adjacent paths to queue
        if forward:
            adjacent = sorted(self.following(v), key=self._sort)
            queue.extendleft(Path([v, w]) for w in adjacent)
        else:
            adjacent = sorted(self.preceding(v), key=self._sort)
            queue.extendleft(Path([u, v]) for u in adjacent)

        while queue:
            p = queue.pop()
            u = p[-1]
            if u in paths:
                # A shorter path was already found
                continue

            paths[u] = p
            if t is not None and u == t:
                break
            # Add all adjacent paths to queue
            if u != v and forward:
                adjacent = sorted(self.following(u), key=self._sort)
                queue.extendleft(p.append_with(w) for w in adjacent)
            elif u != v:
                adjacent = sorted(self.preceding(u), key=self._sort)
                queue.extendleft(p.prepend_with(w) for w in adjacent)

        # Find all vertices not covered by BFS
        for u in self.vertices - paths.keys():
            paths[u] = Path()

        return paths if t is None else {t: paths[t]}

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

        paths_from = self.search_paths(v1, t=v2)

        return paths_from[v2] if paths_from[v2] else None

    def diameter(self):
        """ Finds the longest path in this graph that is the shortest path
            between a pair of vertices.

            Longest paths are sorted by their vertices as to give a consistent
            result.
        """
        paths = []

        for v in sorted(self):
            paths.extend(self.search_paths(v).values())

        if paths:
            max_len = max(len(p) for p in paths)
            longest_paths = sorted((p for p in paths if len(p) == max_len),
                                   key=self.path_sort)
            return longest_paths[0]
        else:
            return Path()

    def analyse(self):
        """ Finds all distinct paths for this graph and the topological order
            of vertices, starting with the diameter.

            The results are cached if the adjacency list does not change.
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

    def draw(self, max_columns=None):
        """ Lays out graph using sequence.

            :param max_columns: Maximum number of columns. If any row exceeds
            this maximum no layout will be returned.
            :returns: Layout object with layout drawn.
        """
        return Layout(self, max_columns=max_columns)


def service_graph_stops(service_id, direction):
    """ Creates graph and dictionary of stops from a service using pairs of
        adjacent stops in journey patterns.

        :param service_id: Service ID.
        :param direction: Groups journey patterns by direction - False for
        outbound and True for inbound.
        :returns: Graph of service and dict of stop models with ATCO codes as
        keys.
    """
    stop_refs = (
        db.session.query(
            models.JourneyPattern.id.label("pattern_id"),
            models.JourneyLink.sequence.label("sequence"),
            models.JourneyLink.stop_point_ref.label("stop_ref"),
            db.func.count(models.Journey.id).label("journeys")
        )
        .select_from(models.JourneyPattern)
        .join(models.JourneyPattern.links)
        .join(models.JourneyPattern.journeys)
        .join(models.JourneyLink.stop_point)
        .filter(models.JourneyPattern.service_ref == service_id,
                models.JourneyPattern.direction.is_(direction),
                models.StopPoint.active)
        .group_by(models.JourneyPattern.id, models.JourneyLink.sequence,
                  models.JourneyLink.stop_point_ref)
        .subquery()
    )
    stop_journeys = (
        db.session.query(stop_refs.c.stop_ref,
                         db.func.max(stop_refs.c.journeys)
                         .label("max_journeys"))
        .group_by(stop_refs.c.stop_ref)
        .subquery()
    )
    pairs = (
        db.session.query(
            stop_refs.c.stop_ref.label("current"),
            stop_refs.c.sequence,
            db.func.lead(stop_refs.c.stop_ref)
            .over(partition_by=stop_refs.c.pattern_id,
                  order_by=stop_refs.c.sequence).label("next")
        )
        .subquery()
    )
    adj_stops = (
        db.session.query(
            models.StopPoint,
            db.func.max(stop_journeys.c.max_journeys).label("journeys"),
            db.func.min(pairs.c.sequence).label("sequence"),
            db.func.array_remove(db.func.array_agg(db.distinct(pairs.c.next)),
                                 None).label("next_stops")
        )
        .options(db.contains_eager(models.StopPoint.locality))
        .join(models.StopPoint.locality)
        .join(pairs, pairs.c.current == models.StopPoint.atco_code)
        .join(stop_journeys, pairs.c.current == stop_journeys.c.stop_ref)
        .group_by(models.StopPoint.atco_code, models.Locality.code)
    )

    stops = {}
    ranking = {}
    edges = []
    for s in adj_stops.all():
        stop = s.StopPoint
        stops[stop.atco_code] = stop
        ranking[stop.atco_code] = -s.journeys, s.sequence, stop.atco_code
        edges.extend((stop.atco_code, n) for n in s.next_stops)

    return Graph(edges, sort=ranking.get), stops


def service_graph(service_id, direction):
    """ Creates Graph object from a service using adjacent stops on journey
        patterns.

        :param service_id: Service ID.
        :param direction: Groups journey patterns by direction.
        :returns: Graph object with vertices labelled by ATCO codes.
    """
    return service_graph_stops(service_id, direction)[0]


def service_stops(service_id, direction):
    """ Get dictionary of distinct stops for a service.

        :param service_id: Service ID.
        :param direction: Groups journey patterns by direction.
        :returns: Dictionary with ATCO codes as keys for stop point objects.
    """
    return service_graph_stops(service_id, direction)[1]


def service_stop_list(service_id, direction):
    """ Queries all patterns for a service and creates list of stops sorted
        topologically.

        :param service_id: Service ID.
        :param direction: Groups journey patterns by direction - False for
        outbound and True for inbound.
    """
    graph, dict_stops = service_graph_stops(service_id, direction)
    if not dict_stops:
        raise ValueError(f"No stops exist for service ID {service_id}")

    return [dict_stops[v] for v in graph.sequence()]


def service_json(service_code, reverse, max_columns=MAX_COLUMNS):
    """ Creates geometry JSON data for map.

        :param service_code: Service ID.
        :param reverse: Groups journey patterns by direction - False for
        outbound and True for inbound.
        :param max_columns: Maximum columns before giving up on drawing graph
    """
    service = (
        models.Service.query
        .join(models.Service.patterns)
        .outerjoin(models.JourneyPattern.operator)
        .options(db.contains_eager(models.Service.patterns),
                 db.contains_eager(models.Service.operators))
        .filter(models.Service.code == service_code)
        .one_or_none()
    )

    if service is None:
        return None

    # Check line patterns - is there more than 1 direction?
    reverse_, mirrored = service.has_mirror(reverse)

    other_services = [{
        "code": s.service.code,
        "line": s.service.line,
        "direction": "inbound" if s.direction else "outbound",
        "reverse": s.direction,
        "shortDescription": s.service.short_description,
        "origin": s.origin,
        "destination": s.destination
    } for s in service.similar(reverse_, 0.5)]

    graph, stops = service_graph_stops(service.id, reverse_)
    paths, sequence = graph.analyse()
    try:
        layout = graph.draw(max_columns).serialize()
    except MaxColumnError:
        layout = None

    # Serialise data
    paths = {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [
                [[stops[v].longitude, stops[v].latitude] for v in p]
                for p in paths if len(p) > 1
            ]
        }
    }

    data = {
        "code": service.code,
        "line": service.line,
        "description": service.description,
        "shortDescription": service.short_description,
        "direction": "inbound" if reverse_ else "outbound",
        "reverse": reverse_,
        "mirrored": mirrored,
        "operators": [o.name for o in service.operators],
        "stops": {c: s.to_geojson() for c, s in stops.items()},
        "sequence": sequence,
        "paths": paths,
        "layout": layout,
        "other": other_services
    }

    return data
