import math
from operator import add
from functools import partial
import numpy as np
import cv2

OPENCV_MAJOR = cv2.__version__[0]


class FinderPattern():
    """A representation of the location of a Datamatrix 'finder pattern'
    in an image. All points and lengths are in units of Pixels"""

    def __init__(self, x_corner, vec_base, vec_side):
        self.corner = x_corner
        self.baseVector = vec_base
        self.sideVector = vec_side

        # positions of the three corners
        self.c1 = tuple(x_corner)
        self.c2 = tuple(x_corner + vec_base)
        self.c3 = tuple(x_corner + vec_side)

        # Position of center of the datamatrix in image pixels
        self.center = tuple(map(int, x_corner + (vec_base + vec_side)/2))

        # Radius of datamatrix (distance from center to a corner) in pixels
        self.radius = int(math.sqrt((vec_base[0]*vec_base[0] + vec_base[1]*vec_base[1])/2))

    def pack(self):
        return tuple([self.corner, self.baseVector, self.sideVector])

    def point_in_radius(self, point):
        return (point[0] - self.center[0])**2 + (point[1] - self.center[1])**2 < self.radius

    def bounds(self):
        return (self.center, self.radius)


class Locator():
    """Utility for finding the positions of all of the datamatrix barcodes
    in an image """

    def __init__(self):
        # Assume that all datamatricies are roughly the same
        #   size so filter out any obviously mis-sized ones
        self._median_radius_tolerance = 0.3
        self._median_radius = 0

    def locate_datamatrices(self, grayscale_image):
        """Get the positions of (hopefully all) datamatrices within an image.
        """

        finder_patterns = []

        # Use a couple of different values of C as much more likely to locate the finder patterns
        for C in [16,8]:
            # Perform a fairly generic morphological operation to make it easier to
            # find contours in general and datamatricies in particular.
            morphed_image = self._do_morph(grayscale_image, blocksize=35, C=C)

            # TESTING
            #cv2.imwrite("C:/PROJECTS_WORKSPACE/8815 Diamond/datamatrix/test-output/morph_test.jpg", morphed_image)

            # Find a bunch of contours in the image.
            contour_vertex_sets = self._get_contours(morphed_image)

            # Convert lists of vertices to lists of edges (easier to work with).
            edge_sets = map(self._convert_to_edge_set, contour_vertex_sets)

            # Discard all edge sets which probably aren't datamatrix perimeters.
            edge_sets = filter(self._filter_non_trivial, edge_sets)
            edge_sets = filter(self._filter_longest_adjacent, edge_sets)
            edge_sets = filter(self._filter_longest_approx_orthogonal, edge_sets)
            edge_sets = filter(self._filter_longest_similar_in_length, edge_sets)

            # Convert edge sets to FinderPattern objects
            fps = [self._get_finder_pattern(es) for es in edge_sets]

            # check that this doesnt overlap with any previous finder patterns
            for fp in fps:
                in_radius = False
                for ex in finder_patterns:
                    in_radius = in_radius | ex.point_in_radius(fp.center)
                if not in_radius:
                    finder_patterns.append(fp)

        # Filter out any which differ significantly in size
        if len(finder_patterns) > 3:
            self._median_radius = np.median([fp.radius for fp in finder_patterns])
            finder_patterns = filter(self._filter_median_radius, finder_patterns)

        return finder_patterns

    def _do_morph(self, gray, blocksize, C):
        """Perform a generic morphological operation on an image.
        """
        thresh = cv2.adaptiveThreshold(gray, 255.0, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, blocksize, C)
        element = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        return cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, element, iterations=1)


    def _get_contours(self, arr):
        """Find contours and return them as lists of vertices.
        """
        # List of return values changed between version 2 and 3
        if OPENCV_MAJOR == '3':
            _, raw_contours, _ = cv2.findContours(arr.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        else:
            raw_contours, _ = cv2.findContours(arr.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        return [cv2.approxPolyDP(rc, 6.0, True).reshape(-1, 2) for rc in raw_contours]

    def _convert_to_edge_set(self, vertex_list):
        """Return a list of edges based on the given list of vertices.
        """
        return list(self._pairs_circular(vertex_list))

    def _pairs_circular(self, iterable):
        """Generate pairs from an iterable. Best illustrated by example:

        >>> list(pairs_circular('abcd'))
        [('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'a')]
        """
        iterator = iter(iterable)
        x = next(iterator)
        zeroth = x  # Keep the first element so we can wrap around at the end.
        while True:
            try:
                y = next(iterator)
                yield((x, y))
            except StopIteration:  # Iterator is exhausted so wrap around to start.
                try:
                    yield((y, zeroth))
                except UnboundLocalError:  # Iterable has one element. No pairs.
                    pass
                break
            x = y

    def _filter_non_trivial(self, edge_set):
        """Return True iff the number of edges is non-small.
        """
        return len(edge_set) > 6

    def _filter_longest_adjacent(self, edges):
        """Return True iff the two longest edges are adjacent.
        """
        i, j = self._longest_pair_indices(edges)
        return abs(i - j) in (1, len(edges) - 1)

    def _filter_longest_approx_orthogonal(self, edges):
        """Return True iff the two longest edges are approximately orthogonal.
        """
        i, j = self._longest_pair_indices(edges)
        v_i, v_j = (np.subtract(*edges[x]) for x in (i, j))
        return abs(_cosine(v_i, v_j)) < 0.1

    def _filter_longest_similar_in_length(self, edges):
        """Return True iff the two longest edges are similar in length.
        """
        i, j = self._longest_pair_indices(edges)
        l_i, l_j = (_length(edges[x]) for x in (i, j))
        return abs(l_i - l_j)/abs(l_i + l_j) < 0.1

    def _filter_median_radius(self, fp):
        """Return true iff finder pattern radius is close to the median"""
        median = self._median_radius
        tolerance = self._median_radius_tolerance * median
        return (median - tolerance) < fp.radius < (median + tolerance)

    def _longest_pair_indices(self, edges):
        """Return the indices of the two longest edges in a list of edges.
        """
        return np.asarray(map(_length, edges)).argsort()[-2:][::-1]

    def _get_finder_pattern(self, edges):
        """Return information about the "main" corner from a set of edges.

        This function finds the corner between the longest two edges, which should
        be spatially adjacent (it is up to the caller to make sure of this). It
        returns the position of the corner, and vectors corresponding to the said
        two edges, pointing away from the corner. These two vectors are returned in
        an order such that their cross product is positive, i.e. (see diagram) the
        base vector (a) comes before the side vector (b).

              ^side
              |
              |   base
              X--->
         corner

        This provides a convenient way to refer to the position of a datamatrix.
        """
        i, j = self._longest_pair_indices(edges)
        pair_longest_edges = [edges[x] for x in (i, j)]
        x_corner = self._get_shared_vertex(*pair_longest_edges)
        c, d = map(partial(self._get_other_vertex, x_corner), pair_longest_edges)
        vec_c, vec_d = map(partial(np.add, -x_corner), (c, d))

        # FIXME: There seems to be a sign error here...
        if vec_c[0]*vec_d[1] - vec_c[1]*vec_d[0] < 0:
            vec_base, vec_side = vec_c, vec_d
        else:
            vec_base, vec_side = vec_d, vec_c

        return FinderPattern(x_corner, vec_base, vec_side)

    def _get_shared_vertex(self, edge_a, edge_b):
        """Return a vertex shared by two edges, if any.
        """
        for vertex_a in edge_a:
            for vertex_b in edge_b:
                if (vertex_a == vertex_b).all():
                    return vertex_a

    def _get_other_vertex(self, vertex, edge):
        """Return an element of `edge` which does not equal `vertex`.
        """
        for vertex_a in edge:
            if not (vertex_a == vertex).all():
                return vertex_a


def _length(edge):
    return _distance(*edge)


def _distance(point_a, point_b):
    return _modulus(np.subtract(point_a, point_b))


def _modulus(vector):
    return quadrature_add(*vector)


def _cosine(vec_a, vec_b):
    return np.dot(vec_a, vec_b)/(_modulus(vec_a) * _modulus(vec_b))


def quadrature_add(*values):
    return math.sqrt(reduce(add, (c*c for c in values)))