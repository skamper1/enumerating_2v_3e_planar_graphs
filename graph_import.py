
import igraph as ig


def edgelist_from_graph_data(graph_data):
    """Convert a 1-indexed adjacency list from graph data to a 0-indexed edge list.
    
    Args:
        graph_data: Dictionary containing 'adjacency_list' key with vertex adjacencies.
    
    Returns:
        List of edges as tuples of vertex indices (zero indexed).
    """
    adj_list = graph_data["adjacency_list"]
    # Handle both string and integer keys
    if isinstance(next(iter(adj_list.keys())), str):
        return [(int(vi) - 1,vj - 1) for vi,adjsi in adj_list.items() for vj in adjsi if int(vi) < vj]
    else:
        return [(vi - 1,vj - 1) for vi,adjsi in adj_list.items() for vj in adjsi if vi < vj]

def graph_from_graph_data(graph_data):
    """Convert graph data to an igraph Graph object.
    
    Args:
        graph_data: Dictionary containing graph structure with 'adjacency_list' key.
    
    Returns:
        An igraph Graph object.
    """
    edge_list = edgelist_from_graph_data(graph_data)
    return ig.Graph(edges=edge_list)

def face_indices_from_graph_data(graph_data):
    """Compute face indices matrix from graph data.
    
    Args:
        graph_data: Dictionary with 'adjacency_list' and degree sequence information.
    
    Returns:
        2D matrix M where M[i][j] indicates which v1 vertex connects faces i and j.
    """
    # Handle both old and new JSON formats
    deg_seq_pair = graph_data.get("metadata", {}).get("degree_sequence_pair") or graph_data.get("degree_sequences")
    v1 = len(deg_seq_pair[0])
    v2 = len(deg_seq_pair[1])
    
    M = [[0 for i in range(v2)] for j in range(v2)]
    adj_list = graph_data["adjacency_list"]
    for vi in range(v1) :
        # check if face needs to be reversed
        forward = True
        # Handle both string and integer keys
        adjs1indexed = adj_list.get(str(vi+1)) or adj_list.get(vi+1)
        adjs = [ai - 1 - v1 for ai in adjs1indexed]
        l = len(adjs)
        for i in range(l) :
            
            fr = adjs[i]
            to = adjs[(i+1) % l]
            if M[fr][to] == 0:
                M[fr][to] = vi + 1  
            elif M[to][fr] == 0:
                M[to][fr] = vi + 1
            else :
                raise Exception("NOOOO")
    return M


def get_v1_v2_from_graph_data(graph_data):
    """Extract the bipartition sizes from graph data.
    
    Args:
        graph_data: Dictionary containing degree sequence information.
    
    Returns:
        Tuple (v1, v2) representing the sizes of the two vertex partitions.
    """
    # Handle both old and new JSON formats
    deg_seq_pair = graph_data.get("metadata", {}).get("degree_sequence_pair") or graph_data.get("degree_sequences")
    v1 = len(deg_seq_pair[0])
    v2 = len(deg_seq_pair[1])
    return (v1,v2)

def v1_face_sharing_vertex_edge_list(graph_data):
  """Get ordered edges around each v1 vertex showing face-sharing relationships.
  
  Args:
      graph_data: Dictionary containing graph structure.
  
  Returns:
      Dictionary mapping v1 vertices to ordered lists of edge pairs.
  """
  v1, v2 = get_v1_v2_from_graph_data(graph_data)
  adj_dict = graph_data["adjacency_list"]
  # Handle both string and integer keys
  if isinstance(next(iter(adj_dict.keys())), str):
    adj_list = [adj_dict[str(i)] for i in range(1, 1 + v1)]
  else:
    adj_list = [adj_dict[i] for i in range(1, 1 + v1)]
  edge_list_unordered = {(i+1): [(adj_listi[j], adj_listi[(j+1) % len(adj_listi)]) for j,adj_listij in enumerate(adj_listi)] for i, adj_listi in enumerate(adj_list)}
  return set_edge_orderings(edge_list_unordered)


def v2_face_sharing_vertex_edge_list(graph_data):
  """Get ordered edges around each v2 vertex showing face-sharing relationships.
  
  Args:
      graph_data: Dictionary containing graph structure.
  
  Returns:
      Dictionary mapping v2 vertices to ordered lists of edge pairs.
  """
  v1, v2 = get_v1_v2_from_graph_data(graph_data)
  adj_list = get_v2_ordered_adj_list(graph_data)
  return {vi: [(adj_listi[j], adj_listi[(j+1) % len(adj_listi)]) for j,adj_listij in enumerate(adj_listi)] for vi, adj_listi in adj_list.items()}


def reverse_edges(edges):
   """Reverse the order and direction of a list of edges.
   
   Args:
       edges: List of edge tuples.
   
   Returns:
       List of edges in reverse order with each edge direction flipped.
   """
   return [(edge[1], edge[0]) for edge in reversed(edges)]

def set_edge_orderings(vertex_edge_list0):
  """Orient edges consistently across vertices to maintain coherent face traversal.
  
  Args:
      vertex_edge_list0: Dictionary mapping vertices to lists of edge pairs.
  
  Returns:
      Dictionary with consistently oriented edges for all vertices.
  """
  vertex_edge_list = {vi: [(edge[0],edge[1]) for edge in edges] for vi, edges in vertex_edge_list0.items()}
  key_queue = [[*vertex_edge_list.keys()][0]]
  more_in_queue = True
  next_queue_index = 0 # index (easier queue with rolling index as need to check history)
  def add_to_queue(vi):
    """function to order the edges looked at for orientation (can't always go start to end)"""
    nonlocal key_queue, more_in_queue
    if vi not in key_queue:
      key_queue.append(vi)
      more_in_queue = True
  
  def next_in_queue():
    nonlocal key_queue, more_in_queue, next_queue_index
    nxt = key_queue[next_queue_index]
    next_queue_index += 1
    more_in_queue = next_queue_index < len(key_queue)
    return(nxt)
  
  
  #print(vertex_edge_list)
  #print("*****")
  while more_in_queue:
    vi = next_in_queue()
    edges = vertex_edge_list[vi]
    for edge in edges:
      # determine how many occurrences of this edge exist
      indexes_of_edge = {vj: edgesj.index(edge) for vj,edgesj in vertex_edge_list.items() if edge in edgesj and vi is not vj}
      if len(indexes_of_edge) > 0:
        vj = [*indexes_of_edge.keys()][0]
        #print(f"in vi {vi} reversing vj {vj} because of edge {edge} occuring {indexes_of_edge}")
        #print(vertex_edge_list)
        vertex_edge_list[vj] = reverse_edges(vertex_edge_list[vj])
        add_to_queue(vj)
      else:
        edge = (edge[1], edge[0])
        indexes_of_edge = {vj: edgesj.index(edge) for vj,edgesj in vertex_edge_list.items() if edge in edgesj and vi is not vj}
        #print(f"This should be len 1 looking for {(edge[1], edge[0])} {len(indexes_of_edge)}")
        add_to_queue([*indexes_of_edge.keys()][0])
  
      
    
  return vertex_edge_list

def find_edge_cycle(edges):
  """Reorder edges to form a connected cycle.
  
  Args:
      edges: List of edge tuples.
  
  Returns:
      List of edges reordered to form a cycle where each edge's endpoint connects to the next.
  """
  edges = [(vi,vj) for vi,vj in edges]
  for i in range(len(edges) - 1):
    edge = edges[i]
    vj = edge[1]
    # find next 
    p = [pos+i+1 for pos, edge in enumerate(edges[(i+1):]) if vj in edge]
    if p[0] != i+1:
      edgep = edges.pop(p[0])
      edges.insert(i+1, edgep)
  return(edges)

def get_v2_ordered_adj_list(graphdata):
  """Compute ordered adjacency list for v2 vertices based on face relationships.
  
  Args:
      graphdata: Dictionary containing graph structure.
  
  Returns:
      Dictionary mapping v2 vertices to ordered lists of adjacent v1 vertices.
  """
  v1, v2 = get_v1_v2_from_graph_data(graphdata)
  fs1 = v1_face_sharing_vertex_edge_list(graphdata)
  ordered_v1_edges = set_edge_orderings(fs1)
  # start finding order of edges about v2
  # find the locations of each vi (vertices in v2) in the edges.
  vi_indexes = {vi: [[(vj, i) for i, edge in enumerate(edges) if vi in edge] for vj, edges in ordered_v1_edges.items()] for vi in range(v1+1,v1+v2+1)}
  # retrieve just the vertices immediately before and after in the orientation about the vertices in v1
  # suffices to check if the edges are the start and end of a list or next to eachother.
  # removes empty arrays
  vi_indexes = {vi: [ind for ind in inds if ind] for vi, inds in vi_indexes.items()}
  nr={vi: [(ordered_v1_edges[vj][i][0],ordered_v1_edges[vj][j][1]) if j - i == 1 else (ordered_v1_edges[vj][j][0],ordered_v1_edges[vj][i][1]) for [(vj,i),(vj, j)] in inds] for vi, inds in vi_indexes.items()}
  sortednr = {vi: find_edge_cycle(nri) for vi, nri in nr.items()}
  
  ordered_v2_adj_list = {vi: [find_edge_in_ordered_face_edges((vi,vk),ordered_v1_edges) for (vj, vk) in edges] for vi, edges in sortednr.items() }  
  return(ordered_v2_adj_list)


def find_edge_in_ordered_face_edges(edge, ordered_face_edges):
  """Find which vertex contains a specific edge in its ordered edge list.
  
  Args:
      edge: Tuple representing an edge.
      ordered_face_edges: Dictionary mapping vertices to their edge lists.
  
  Returns:
      The vertex key that contains the specified edge.
  """
  p = [vk for vk, edges in ordered_face_edges.items() if edge in edges]
  return(p[0])

def convert_face_sharing_vertex_edge_list_to_face_adj_list(fs):
  """Convert face-sharing edge list to face adjacency list.
  
  Args:
      fs: Dictionary mapping vertices to ordered edge pairs.
  
  Returns:
      Dictionary mapping vertices to lists of adjacent vertices.
  """
  return({vi: [find_edge_in_ordered_face_edges((vk,vj),fs) for vj,vk in edges] for vi, edges in fs.items()})


def face_graph_from_graph_data(graph_data):
    """Create face graph from graph data.
    
    Args:
        graph_data: Dictionary containing graph structure.
    
    Returns:
        An igraph Graph representing the face adjacency structure.
    """
    M = face_indices_from_graph_data(graph_data)
    bool_M = [[1 if M[i][j] != 0 else 0 for j in range(len(M)) ] for i in range(len(M))]
    return ig.Graph.Adjacency(bool_M, mode = "undirected")

def face_graph_vertex_connectivity_from_graph_data(graph_data):
    """Compute the vertex connectivity of the face graph.
    
    Args:
        graph_data: Dictionary containing graph structure.
    
    Returns:
        The vertex connectivity value of the face graph.
    """
    g = face_graph_from_graph_data(graph_data)
    k = g.vertex_connectivity()
    return k

def igraph_from_adj_list(adj_list):
    """Convert an adjacency list dictionary to an igraph Graph object.
    
    Args:
        adj_list: Dictionary mapping vertex identifiers to lists of adjacent vertices.
    
    Returns:
        An igraph Graph object with vertex names.
    """
    edges = [(vi,vj) for vi, adjs in adj_list.items() for vj in adjs]
    reindex = min([min(edge) for edge in edges])
    highest = max([max(edge) for edge in edges])
    edgesr = [(vi - reindex, vj - reindex) for (vi,vj) in edges if vi < vj]
    edgesr
    g = ig.Graph(edgesr, directed = False, vertex_attrs={"name": [f'v{i}' for i in range(reindex, highest+1)]})
    return g

def face_graphs(graph_data):
    """Compute face graphs for both vertex partitions.
    
    Args:
        graph_data: Dictionary containing graph structure.
    
    Returns:
        Tuple (g1, g2) of igraph Graph objects for v1 and v2 face graphs.
    """
    fs1 = v1_face_sharing_vertex_edge_list(graph_data)
    fal1 = convert_face_sharing_vertex_edge_list_to_face_adj_list(fs1)
    g1 = igraph_from_adj_list(fal1)
    
    fs2 = v2_face_sharing_vertex_edge_list(graph_data)
    fal2 = convert_face_sharing_vertex_edge_list_to_face_adj_list(fs2)
    g2 = igraph_from_adj_list(fal2)
    
    return (g1, g2)


def face_graphs_and_adjlists(graph_data):
    """Compute face graphs and adjacency lists for both vertex partitions.
    
    Args:
        graph_data: Dictionary containing graph structure.
    
    Returns:
        Tuple (g1, g2, fal1, fal2) containing igraph Graph objects and adjacency list dicts.
    """
    fs1 = v1_face_sharing_vertex_edge_list(graph_data)
    fal1 = convert_face_sharing_vertex_edge_list_to_face_adj_list(fs1)
    g1 = igraph_from_adj_list(fal1)
    
    fs2 = v2_face_sharing_vertex_edge_list(graph_data)
    fal2 = convert_face_sharing_vertex_edge_list_to_face_adj_list(fs2)
    g2 = igraph_from_adj_list(fal2)
    
    return (g1, g2, fal1, fal2)

def plot_igraph(g):
    """Plot an igraph Graph using matplotlib.
    
    Args:
        g: An igraph Graph object to visualize.
    """
    fig, ax = plt.subplots(figsize=(6, 6))
    # Plot using igraph's matplotlib backend
    ig.plot(
        g,
        target=ax,
        layout=g.layout("kk"),
        vertex_label = g.vs["name"],
        vertex_size=60,
        vertex_color="lightblue",
        edge_width=1
    )
    plt.show()
