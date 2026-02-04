#!/usr/bin/env python3
"""Stream plantri output directly to Parquet with face graph processing.

This script runs plantri for each v in a range, processes stdout line-by-line,
computes face graphs and encodings, filters for connectivity-2, and writes
to partitioned Parquet files organized by degree sequence.
"""

import sys
import subprocess
import time
import argparse
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

from config import get_data_dir, get_plantri_path, ensure_directories_exist, get_parquet_dir
from graph_import import face_graphs_and_adjlists
from graph_encoding import three_level_encoding, zero_index_edge_list, vertex_encoding_init, add_encoding, vertex_degree, adjacent_degrees


def parse_plantri_line(line):
    """Parse a plantri output line into adjacency list.
    
    Args:
        line: Plantri output line (e.g., "10 abcdefghij,bcaghij,...")
        
    Returns:
        dict: 1-indexed adjacency list or None if invalid
    """
    parts = line.strip().split(" ")
    if len(parts) < 2:
        return None
    
    try:
        adjs = parts[1].split(",")
        graph_dict = {(index+1): [ord(adjij) - 96 for adjij in adi] for index, adi in enumerate(adjs)}
        return graph_dict
    except (IndexError, ValueError) as e:
        return None


def two_level_encoding(adj_list):
    """Compute 2-level encoding (degree + adjacent degrees).
    
    Args:
        adj_list: Adjacency list dictionary
        
    Returns:
        str: Two-level encoding string
    """
    init = vertex_encoding_init(adj_list)
    arr2 = add_encoding(init, vertex_degree)
    arr3 = add_encoding(arr2, adjacent_degrees)
    return " x ".join([x[3] for x in sorted(arr3, key=lambda x: (x[2], x[3]), reverse=True)])


def compute_degree_sequence(adj_list):
    """Compute reverse-sorted underscore-separated degree sequence.
    
    Args:
        adj_list: Adjacency list dictionary
        
    Returns:
        str: Degree sequence like "3_3_2_2"
    """
    degrees = sorted([len(neighbors) for neighbors in adj_list.values()], reverse=True)
    return "_".join(map(str, degrees))


def process_face_graph(adj_list, face_adj_list, connectivity):
    """Process a single face graph and return record dict.
    
    Args:
        adj_list: Original graph adjacency list
        face_adj_list: Face graph adjacency list
        connectivity: Face graph connectivity value
        
    Returns:
        dict or None: Record dict if connectivity==2, else None
    """
    if connectivity != 2:
        return None
    
    degree_seq = compute_degree_sequence(face_adj_list)
    edge_list = zero_index_edge_list(face_adj_list)
    encoding_2 = two_level_encoding(face_adj_list)
    encoding_3 = three_level_encoding(face_adj_list)
    
    return {
        'degree_sequence': degree_seq,
        'zero_indexed_edge_list': str(edge_list),
        'encoding_2_level': encoding_2,
        'encoding_3_level': encoding_3
    }


def write_parquet_batch(buffer, v, root_path):
    """Write a batch of records to partitioned Parquet.
    
    Args:
        buffer: List of record dicts
        v: Vertex count
        root_path: Root path for Parquet dataset
    """
    if not buffer:
        return
    
    schema = pa.schema([
        ('v', pa.int32()),
        ('original_graph_number', pa.int32()),
        ('graph_number', pa.int32()),
        ('degree_sequence', pa.string()),
        ('zero_indexed_edge_list', pa.string()),
        ('encoding_2_level', pa.string()),
        ('encoding_3_level', pa.string())
    ])
    
    table = pa.Table.from_pylist(buffer, schema=schema)
    
    pq.write_to_dataset(
        table,
        root_path=root_path,
        partition_cols=['v', 'degree_sequence'],
        compression='ZSTD',
        existing_data_behavior='overwrite_or_ignore'
    )


def process_v(v, root_path, plantri_path=None, batch_size=10000):
    """Process all graphs for a given vertex count.
    
    Args:
        v: Vertex count
        root_path: Root path for Parquet output
        plantri_path: Path to plantri binary (optional, uses config default if None)
        batch_size: Number of records per batch write
        
    Returns:
        tuple: (lines_processed, conn2_written)
    """
    plantri_binary = get_plantri_path(plantri_path)
    cmd = [plantri_binary, str(v), '-q', '-a']
    
    print(f"\n{'='*60}")
    print(f"Processing v={v}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    buffer = []
    lines_processed = 0
    conn2_written = 0
    graph_number = 0  # Running counter for connectivity-2 graphs written
    batch_start_time = time.time()
    
    try:
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            
            lines_processed += 1
            
            # Parse plantri line to adjacency list
            adj_list = parse_plantri_line(line)
            if not adj_list:
                print(f"  Warning: Could not parse line {lines_processed}: {line[:50]}...")
                continue
            
            # Compute bipartition and degree sequences like convert_graph.py does
            colouring = [0 for i in range(len(adj_list.keys()))]
            queue = [1]
            colouring[0] = 1
            bipartitions = [[[1, len(adj_list[1])]],[]]
            
            while queue:
                vertex = queue.pop(0)
                for adj in adj_list[vertex]:
                    if colouring[adj-1] == 0:
                        queue.append(adj)
                        colouring[adj-1] = colouring[vertex-1] % 2 + 1
                        bipartitions[colouring[adj-1]-1].append([adj, len(adj_list[adj])])
            
            bipartitions[0].sort(reverse=True, key = lambda x: x[1])
            bipartitions[1].sort(reverse=True, key = lambda x: x[1])
            bipartitions.sort(reverse=True, key = lambda x: [xi[1] for xi in x])
            remapb1 = [i for i in range(1, len(bipartitions[0]) + 1)]
            remapb2 = [i for i in range(len(bipartitions[0]) + 1, len(bipartitions[0]) + len(bipartitions[1]) + 1)]
            remap = {v_old: remapb1[i] for i, [v_old, d] in enumerate(bipartitions[0])} | {v_old: remapb2[i] for i, [v_old, d] in enumerate(bipartitions[1])}
            adj_list_remapped = {remap[k]: [remap[i] for i in v_adj] for k, v_adj in adj_list.items()}
            adj_list_remapped = {k: v_adj for k, v_adj in sorted(adj_list_remapped.items(), key=lambda item: item[0])}
            degree_sequences = [[bij[1] for bij in bi] for bi in bipartitions]
            
            # Create graph_data dict for face_graphs_and_adjlists
            graph_data = {"degree_sequences": degree_sequences, "adjacency_list": adj_list_remapped}
            
            try:
                # Compute face graphs and connectivity
                g1, g2, fal1, fal2 = face_graphs_and_adjlists(graph_data)
                c1 = g1.vertex_connectivity()
                c2 = g2.vertex_connectivity()
                
                # Process each face graph if connectivity == 2
                for face_adj_list, connectivity in [(fal1, c1), (fal2, c2)]:
                    record = process_face_graph(adj_list, face_adj_list, connectivity)
                    if record:
                        graph_number += 1
                        record['v'] = v
                        record['original_graph_number'] = lines_processed
                        record['graph_number'] = graph_number
                        buffer.append(record)
                        conn2_written += 1
                
                # Write batch if buffer is full
                if len(buffer) >= batch_size:
                    batch_time = time.time() - batch_start_time
                    write_parquet_batch(buffer, v, root_path)
                    print(f"[v={v}] Batch written: {batch_time:.2f}s | "
                          f"Lines: {lines_processed} | Conn-2 written: {conn2_written}")
                    buffer = []
                    batch_start_time = time.time()
                    
            except Exception as e:
                print(f"  Error processing line {lines_processed}: {e}")
                continue
        
        # Write remaining buffer
        if buffer:
            batch_time = time.time() - batch_start_time
            write_parquet_batch(buffer, v, root_path)
            print(f"[v={v}] Final batch: {batch_time:.2f}s | "
                  f"Lines: {lines_processed} | Conn-2 written: {conn2_written}")
        
        process.wait()
        
        if process.returncode != 0:
            stderr = process.stderr.read()
            print(f"  Error: plantri exited with code {process.returncode}", file=sys.stderr)
            if stderr:
                print(f"  {stderr}", file=sys.stderr)
            return lines_processed, conn2_written
        
        print(f"[v={v}] Complete: {lines_processed} lines processed, {conn2_written} connectivity-2 graphs written")
        return lines_processed, conn2_written
        
    except Exception as e:
        print(f"Error processing v={v}: {e}", file=sys.stderr)
        if process:
            process.terminate()
        return lines_processed, conn2_written


def print_all_parquet(root_path, v_min, v_max):
    """Read and print all Parquet data for testing.
    
    Args:
        root_path: Root path of Parquet dataset
        v_min: Minimum vertex count
        v_max: Maximum vertex count
    """
    print(f"\n{'='*60}")
    print("Reading back all Parquet data for verification")
    print(f"{'='*60}\n")
    
    for v in range(v_min, v_max + 1):
        try:
            # Read all partitions for this v
            dataset = pq.ParquetDataset(root_path, filters=[('v', '=', v)])
            table = dataset.read()
            
            print(f"\n--- v={v} ---")
            print(f"Total rows: {len(table)}")
            print(table.to_pandas())
            
        except Exception as e:
            print(f"No data found for v={v}: {e}")


def write_summary_markdown(summary_file, v_stats, overall_time):
    """Write processing summary to markdown file.
    
    Args:
        summary_file: Path to output markdown file
        v_stats: List of tuples (v, lines_processed, conn2_written, time)
        overall_time: Total processing time
    """
    with open(summary_file, 'w') as f:
        f.write("# Plantri to Parquet Processing Summary\n\n")
        f.write(f"**Total processing time:** {overall_time:.2f}s\n\n")
        
        # Summary table
        f.write("## Processing Statistics by Vertex Count\n\n")
        f.write("| v | Lines Processed | Connectivity-2 Graphs | Time (s) |\n")
        f.write("|---|---|---|---|\n")
        
        total_lines = 0
        total_conn2 = 0
        for v, lines, conn2, v_time in v_stats:
            f.write(f"| {v} | {lines:,} | {conn2:,} | {v_time:.2f} |\n")
            total_lines += lines
            total_conn2 += conn2
        
        f.write(f"| **Total** | **{total_lines:,}** | **{total_conn2:,}** | **{overall_time:.2f}** |\n\n")
        
        # Processing rate
        if overall_time > 0:
            lines_per_sec = total_lines / overall_time
            conn2_per_sec = total_conn2 / overall_time
            f.write("## Processing Rate\n\n")
            f.write(f"- Lines per second: {lines_per_sec:.2f}\n")
            f.write(f"- Connectivity-2 graphs per second: {conn2_per_sec:.2f}\n")


def main(data_dir=None, plantri_path=None):
    parser = argparse.ArgumentParser(
        description="Stream plantri output to Parquet with face graph processing"
    )
    parser.add_argument(
        '--v_min',
        type=int,
        default=10,
        help='Minimum vertex count (default: 10)'
    )
    parser.add_argument(
        '--v_max',
        type=int,
        default=14,
        help='Maximum vertex count (default: 14)'
    )
    parser.add_argument(
        '--printall',
        action='store_true',
        help='Print entire Parquet dataset after processing (for testing)'
    )
    parser.add_argument(
        '--summary',
        type=str,
        default=None,
        help='Output markdown summary file path (e.g., processing_summary.md)'
    )
    parser.add_argument(
        '--data_dir',
        type=str,
        default=None,
        help='Data directory (overrides DATA_DIR environment variable)'
    )
    parser.add_argument(
        '--plantri_path',
        type=str,
        default=None,
        help='Path to plantri binary (overrides PLANTRI_PATH environment variable)'
    )
    
    args = parser.parse_args()
    
    # Use provided arguments or defaults
    data_dir = args.data_dir or data_dir
    plantri_path = args.plantri_path or plantri_path
    
    # Setup output path
    root_path = get_parquet_dir(data_dir)
    ensure_directories_exist(data_dir)
    
    print(f"Output directory: {root_path.absolute()}")
    
    # Process each v
    v_stats = []
    overall_start = time.time()
    for v in range(args.v_min, args.v_max + 1):
        v_start = time.time()
        lines, conn2 = process_v(v, str(root_path), plantri_path=plantri_path)
        v_time = time.time() - v_start
        print(f"[v={v}] Total time: {v_time:.2f}s")
        v_stats.append((v, lines, conn2, v_time))
    
    overall_time = time.time() - overall_start
    print(f"\n{'='*60}")
    print(f"All processing complete: {overall_time:.2f}s")
    print(f"{'='*60}")
    
    # Optional: write summary to markdown
    if args.summary:
        write_summary_markdown(args.summary, v_stats, overall_time)
        print(f"\nSummary written to: {args.summary}")
    
    # Optional: print all data for testing
    if args.printall:
        print_all_parquet(str(root_path), args.v_min, args.v_max)


if __name__ == "__main__":
    main()
