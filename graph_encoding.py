import igraph as ig


def zero_index_adjacency_list(adj_list):
    """Convert adjacency list to zero-based indexing.
    
    Args:
        adj_list: Dictionary with integer vertex keys.
    
    Returns:
        Dictionary with zero-indexed vertices.
    """
    first_key = min([int(key) for key in adj_list.keys()])
    zi_adj_list = {int(key) - first_key: [adi - first_key for adi in adj_list[key]] for key in adj_list.keys()}
    return zi_adj_list


def zero_index_edge_list(adj_list):
    """Convert adjacency list to zero-indexed edge list.
    
    Args:
        adj_list: Dictionary with vertex adjacencies.
    
    Returns:
        List of edges as [vertex1, vertex2] pairs with zero-based indices.
    """
    adj_list = zero_index_adjacency_list(adj_list)
    return [[fr, to] for fr, adj in adj_list.items() for to in adj if fr < to]


def igraph_from_adj_list(adj_list):
    """Create an igraph Graph from an adjacency list.
    
    Args:
        adj_list: Dictionary with vertex adjacencies.
    
    Returns:
        An igraph Graph object.
    """
    return ig.Graph(zero_index_edge_list(adj_list))


def vertex_encoding_init(adj_list):
    """Initialize vertex encoding array with vertex IDs and adjacency information.
    
    This provides a way to encode each vertex with additional properties that can
    be used in subsequent encoding functions.
    
    Args:
        adj_list: Dictionary with vertex adjacencies.
    
    Returns:
        Sorted list of [vertex_id, adjacency_list] pairs.
    """
    adj_list = zero_index_adjacency_list(adj_list)
    encoding_array = [[key, adj] for key, adj in adj_list.items()]
    encoding_array.sort(key=lambda x: x[0])
    return encoding_array


def add_encoding(arr, f):
    """Add an encoding function's output to each vertex encoding array.
    
    Args:
        arr: List of vertex encoding arrays.
        f: Function that takes (vertex_array, full_array) and returns encoding values.
    
    Returns:
        List with encoding function results appended to each vertex array.
    """
    return [[*arri] + f(arri, arr) for arri in arr]


vertex_degree = lambda arri, arr: [len(arri[1])]


def adjacent_degrees(arri, arr):
    """Compute sorted string of adjacent vertex degrees.
    
    Args:
        arri: Vertex encoding array [vertex_id, adjacencies, degree, ...].
        arr: Full list of all vertex encoding arrays.
    
    Returns:
        List containing underscore-separated string of sorted adjacent degrees.
    """
    adj_degrees = [[str(arr[adj][2]) for adj in arri[1]]]
    for ai in adj_degrees:
        ai.sort(reverse=True)
    adj_degrees = ['_'.join(ai) for ai in adj_degrees]
    return adj_degrees


def adjacent_degrees2(arri, arr):
    """Compute sorted string of adjacent vertices' degree patterns.
    
    Args:
        arri: Vertex encoding array [vertex_id, adjacencies, degree, degree_pattern, ...].
        arr: Full list of all vertex encoding arrays.
    
    Returns:
        List containing space-separated string of sorted adjacent degree patterns.
    """
    adj_degrees = [[arr[adj][2], str(arr[adj][3])] for adj in arri[1]]
    adj_degrees = [ai[1] for ai in sorted(adj_degrees, reverse=True, key=lambda x: (x[0], x[1]))]
    x = [" ".join(adj_degrees)]
    return x


def three_level_encoding(adj_list):
    """Generate a three-level hierarchical encoding of graph structure.
    
    Creates an encoding based on vertex degrees, adjacent degrees, and patterns
    of adjacent degree sequences.
    
    Args:
        adj_list: Dictionary with vertex adjacencies.
    
    Returns:
        String encoding with vertex patterns separated by ' x '.
    """
    init = vertex_encoding_init(adj_list)
    arr2 = add_encoding(init, vertex_degree)
    arr3 = add_encoding(arr2, adjacent_degrees)
    arr4 = add_encoding(arr3, adjacent_degrees2)
    return " x ".join([x[4] for x in sorted(arr4, key=lambda x: (x[2], x[3], x[4]), reverse=True)])
