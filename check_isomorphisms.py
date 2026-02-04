"""
Memory-efficient isomorphism checking for plantri Parquet data.
Loads one encoding_3_level group at a time and checks for isomorphisms.
"""

import argparse
import ast
import csv
import duckdb
import glob
import igraph as ig
import os
from pathlib import Path
from datetime import datetime
import time

from config import get_data_dir, get_parquet_dir, ISOMORPHISM_DIR, ensure_directories_exist

def get_all_degree_sequences(conn, v, parquet_dir):
    """Get all degree sequences for a given v."""
    parquet_path = str(Path(parquet_dir) / f"v={v}/**/*.parquet")
    query = f"""
    SELECT DISTINCT degree_sequence
    FROM read_parquet('{parquet_path}')
    ORDER BY degree_sequence
    """
    df = conn.execute(query).fetchdf()
    return df['degree_sequence'].tolist()

def get_encoding_groups_for_degree_seq(conn, v, degree_seq, parquet_dir):
    """Generator that yields encoding_3_level groups for a degree sequence, ordered by size descending."""
    parquet_path = str(Path(parquet_dir) / f"v={v}/degree_sequence={degree_seq}/*.parquet")
    query = f"""
    SELECT 
        encoding_3_level,
        COUNT(*) as group_size
    FROM read_parquet('{parquet_path}')
    GROUP BY encoding_3_level
    ORDER BY group_size DESC
    """
    df = conn.execute(query).fetchdf()
    for _, row in df.iterrows():
        yield row

def load_graphs_for_encoding3(conn, v, degree_seq, encoding_3_level, parquet_dir):
    """Generator that yields graphs for a specific encoding_3_level group one at a time."""
    parquet_path = str(Path(parquet_dir) / f"v={v}/degree_sequence={degree_seq}/*.parquet")
    query = f"""
    SELECT 
        graph_number,
        zero_indexed_edge_list
    FROM read_parquet('{parquet_path}')
    WHERE encoding_3_level = '{encoding_3_level}'
    """
    df = conn.execute(query).fetchdf()
    
    for _, row in df.iterrows():
        edge_list = ast.literal_eval(row['zero_indexed_edge_list'])  # Convert string to list
        g = ig.Graph(edges=edge_list)
        yield (row['graph_number'], g)

def check_isomorphisms_in_group(graphs):
    """Check for isomorphisms within a group and return unique graphs."""
    unique_graphs = []
    total_count = 0
    
    for graph_id, graph in graphs:
        total_count += 1
        is_unique = True
        for unique_graph in unique_graphs:
            if graph.isomorphic(unique_graph):
                is_unique = False
                break
        
        if is_unique:
            unique_graphs.append(graph)
    
    return total_count, len(unique_graphs)

def analyze_degree_sequence(conn, v, degree_seq, md_file, csv_writer, parquet_dir, min_group_size=2, max_groups=None):
    """Analyze all encoding groups for a degree sequence, stream results to files."""
    print(f"\nAnalyzing degree_sequence: {degree_seq}")
    
    groups_gen = get_encoding_groups_for_degree_seq(conn, v, degree_seq, parquet_dir)
    
    total_graphs = 0
    total_unique = 0
    groups_processed = 0
    
    start_time = time.time()
    
    for row in groups_gen:
        encoding_3_level = row['encoding_3_level']
        group_size = row['group_size']
        
        # Skip groups below minimum size
        if group_size < min_group_size:
            continue
        
        # Check if we've reached max_groups limit
        if max_groups and groups_processed >= max_groups:
            break
        
        groups_processed += 1
        
        # Skip isomorphism check for single-graph groups
        if group_size == 1:
            total_graphs += 1
            total_unique += 1
        else:
            # Load and check this group
            graphs = load_graphs_for_encoding3(conn, v, degree_seq, encoding_3_level, parquet_dir)
            orig_count, unique_count = check_isomorphisms_in_group(graphs)
            total_graphs += orig_count
            total_unique += unique_count
        
        # Progress reporting every 1000 groups
        if groups_processed % 1000 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / groups_processed
            avg_size = total_graphs / groups_processed
            print(f"  Processed {groups_processed} groups | "
                  f"Avg size: {avg_size:.1f} | Avg time: {avg_time:.3f}s/group")
    
    elapsed = time.time() - start_time
    print(f"Completed: {groups_processed} groups in {elapsed:.2f}s")
    print(f"Total graphs: {total_graphs:,} → Unique: {total_unique:,}")
    
    result = {
        'degree_sequence': degree_seq,
        'groups_analyzed': groups_processed,
        'total_graphs': total_graphs,
        'unique_graphs': total_unique
    }
    
    # Write to markdown immediately
    md_file.write(f"## Degree Sequence: {degree_seq}\n\n")
    md_file.write(f"- **Groups analyzed:** {groups_processed}\n")
    md_file.write(f"- **Total graphs:** {total_graphs:,}\n")
    md_file.write(f"- **Unique graphs:** {total_unique:,}\n")
    md_file.write(f"- **Duplicates removed:** {total_graphs - total_unique:,}\n\n")
    md_file.flush()
    
    # Write to CSV immediately
    csv_writer.writerow(result)
    
    return result

def count_graphs_below_threshold(conn, v, degree_sequences, min_group_size, parquet_dir):
    """Count graphs in groups below the min_group_size threshold.
    These are automatically unique since they can't have isomorphisms."""
    total_below_threshold = 0
    
    for degree_seq in degree_sequences:
        parquet_path = str(Path(parquet_dir) / f"v={v}/degree_sequence={degree_seq}/*.parquet")
        query = f"""
        SELECT 
            COUNT(*) as count
        FROM (
            SELECT 
                encoding_3_level,
                COUNT(*) as group_size
            FROM read_parquet('{parquet_path}')
            GROUP BY encoding_3_level
            HAVING COUNT(*) < {min_group_size}
        )
        """
        result = conn.execute(query).fetchone()
        if result and result[0]:
            # Sum the group sizes (each group below threshold contributes all its graphs)
            query2 = f"""
            SELECT 
                SUM(group_size) as total
            FROM (
                SELECT 
                    COUNT(*) as group_size
                FROM read_parquet('{parquet_path}')
                GROUP BY encoding_3_level
                HAVING COUNT(*) < {min_group_size}
            )
            """
            result2 = conn.execute(query2).fetchone()
            if result2 and result2[0]:
                total_below_threshold += result2[0]
    
    return total_below_threshold


def main(data_dir=None):
    parser = argparse.ArgumentParser(description='Check isomorphisms in plantri results')
    parser.add_argument('--v', type=int, required=True, help='Vertex count to analyze')
    parser.add_argument('--degree_seq', nargs='+', 
                       help='Degree sequences to analyze (space-separated). If omitted, analyzes all degree sequences.')
    parser.add_argument('--min_group_size', type=int, default=2,
                       help='Minimum group size to analyze (default: 2)')
    parser.add_argument('--max_groups', type=int, help='Maximum groups per degree sequence')
    parser.add_argument('--data_dir', type=str, default=None,
                       help='Data directory (overrides DATA_DIR environment variable)')
    parser.add_argument('--summary', required=True, help='Output markdown file')
    parser.add_argument('--csv', help='Output CSV file')
    
    args = parser.parse_args()
    
    # Use provided arguments or defaults
    data_dir = args.data_dir or data_dir
    parquet_dir = get_parquet_dir(data_dir)
    
    # Ensure directories exist
    ensure_directories_exist(data_dir)
    
    # Setup output paths
    output_path = ISOMORPHISM_DIR / args.summary
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Clean up the specific CSV file that's about to be written to
    if args.csv:
        csv_path = ISOMORPHISM_DIR / args.csv
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(csv_path):
            try:
                os.remove(csv_path)
            except OSError:
                pass
    else:
        csv_path = None
    
    conn = duckdb.connect()
    
    # Get degree sequences to analyze
    if args.degree_seq:
        degree_sequences = args.degree_seq
    else:
        print(f"Fetching all degree sequences for v={args.v}...")
        degree_sequences = get_all_degree_sequences(conn, args.v, parquet_dir)
        print(f"Found {len(degree_sequences)} degree sequences to analyze")
    
    # Open files once at the start
    with open(output_path, 'w') as md_file:
        # Write markdown header
        md_file.write(f"# Isomorphism Analysis for v={args.v}\n\n")
        md_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        md_file.flush()
        
        # Open CSV file if requested
        csv_file = open(csv_path, 'w', newline='') if csv_path else None
        csv_writer = None
        if csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=['degree_sequence', 'groups_analyzed', 
                                                               'total_graphs', 'unique_graphs'])
            csv_writer.writeheader()
            csv_file.flush()
        
        try:
            # Track totals for final summary
            total_graphs_all = 0
            total_unique_all = 0
            
            # Process each degree sequence
            for degree_seq in degree_sequences:
                result = analyze_degree_sequence(conn, args.v, degree_seq, md_file, csv_writer, parquet_dir,
                                               args.min_group_size, args.max_groups)
                total_graphs_all += result['total_graphs']
                total_unique_all += result['unique_graphs']
            
            # Count graphs in groups below threshold
            print(f"\nCounting graphs in groups below threshold...")
            graphs_below_threshold = count_graphs_below_threshold(conn, args.v, degree_sequences, args.min_group_size, parquet_dir)
            print(f"Found {graphs_below_threshold:,} graphs in small groups (automatically unique)")
            
            # Append final summary
            grand_total_unique = total_unique_all + graphs_below_threshold
            grand_total_graphs = total_graphs_all + graphs_below_threshold
            
            md_file.write("---\n\n")
            md_file.write("## Summary\n\n")
            md_file.write(f"- **Total graphs analyzed (groups >= min_size):** {total_graphs_all:,}\n")
            md_file.write(f"- **Unique graphs (from analyzed groups):** {total_unique_all:,}\n")
            md_file.write(f"- **Graphs in small groups (< min_size, all unique):** {graphs_below_threshold:,}\n")
            md_file.write(f"- **Grand total unique graphs:** {grand_total_unique:,}\n")
            md_file.write(f"- **Grand total all graphs:** {grand_total_graphs:,}\n")
            md_file.flush()
            
            print("\nAnalysis complete!")
            
        finally:
            if csv_file:
                csv_file.close()

if __name__ == "__main__":
    main()
