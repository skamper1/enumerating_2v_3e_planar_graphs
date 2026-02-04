"""
Fast distribution analysis for plantri Parquet data using SQL queries.
Provides statistics without loading graph objects.
"""

import argparse
import duckdb
from pathlib import Path
from datetime import datetime

from config import get_data_dir, get_parquet_dir, DISTRIBUTION_DIR, ensure_directories_exist

def count_degree_sequences(conn, v, parquet_dir):
    """Count graphs per degree sequence."""
    parquet_path = str(Path(parquet_dir) / f"v={v}/**/*.parquet")
    query = f"""
    SELECT 
        degree_sequence,
        COUNT(*) as count
    FROM read_parquet('{parquet_path}')
    GROUP BY degree_sequence
    ORDER BY count DESC
    """
    return conn.execute(query).fetchdf()

def count_encoding_groups(conn, v, parquet_dir):
    """Count size of each encoding_3_level group."""
    parquet_path = str(Path(parquet_dir) / f"v={v}/**/*.parquet")
    query = f"""
    SELECT 
        degree_sequence,
        encoding_3_level,
        COUNT(*) as group_size
    FROM read_parquet('{parquet_path}')
    GROUP BY degree_sequence, encoding_3_level
    ORDER BY group_size DESC
    """
    return conn.execute(query).fetchdf()

def write_distribution_summary(v, deg_seq_counts, encoding_groups, output_path):
    """Write detailed distribution summary to markdown."""
    with open(output_path, 'w') as f:
        f.write(f"# Distribution Analysis for v={v}\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Degree sequence counts
        f.write("## Graphs per Degree Sequence\n\n")
        f.write("| Degree Sequence | Graph Count |\n")
        f.write("|-----------------|-------------|\n")
        for _, row in deg_seq_counts.iterrows():
            f.write(f"| {row['degree_sequence']} | {row['count']:,} |\n")
        
        total_graphs = deg_seq_counts['count'].sum()
        f.write(f"\n**Total graphs:** {total_graphs:,}\n\n")
        
        # Encoding group statistics
        f.write("## Encoding Group Statistics\n\n")
        f.write(f"- **Total encoding groups:** {len(encoding_groups):,}\n")
        f.write(f"- **Mean group size:** {encoding_groups['group_size'].mean():.2f}\n")
        f.write(f"- **Median group size:** {encoding_groups['group_size'].median():.0f}\n")
        f.write(f"- **Max group size:** {encoding_groups['group_size'].max():,}\n\n")
        
        # Group size distribution
        f.write("### Group Size Distribution\n\n")
        size_bins = [1, 2, 5, 10, 20, 50, 100, 500, 1000, float('inf')]
        bin_labels = ['1', '2-4', '5-9', '10-19', '20-49', '50-99', '100-499', '500-999', '1000+']
        
        for i, label in enumerate(bin_labels):
            lower = size_bins[i]
            upper = size_bins[i+1]
            if upper == float('inf'):
                count = len(encoding_groups[encoding_groups['group_size'] >= lower])
            else:
                count = len(encoding_groups[(encoding_groups['group_size'] >= lower) & 
                                           (encoding_groups['group_size'] < upper)])
            f.write(f"- **{label} graphs:** {count:,} groups\n")
        
        # Groups per degree sequence
        f.write("\n## Groups per Degree Sequence\n\n")
        groups_per_deg = encoding_groups.groupby('degree_sequence').agg({
            'encoding_3_level': 'count',
            'group_size': ['sum', 'mean', 'max']
        }).round(2)
        groups_per_deg.columns = ['num_groups', 'total_graphs', 'avg_group_size', 'max_group_size']
        groups_per_deg = groups_per_deg.sort_values('total_graphs', ascending=False)
        
        f.write("| Degree Sequence | Num Groups | Total Graphs | Avg Group Size | Max Group Size |\n")
        f.write("|-----------------|------------|--------------|----------------|----------------|\n")
        for deg_seq, row in groups_per_deg.iterrows():
            f.write(f"| {deg_seq} | {int(row['num_groups']):,} | {int(row['total_graphs']):,} | "
                   f"{row['avg_group_size']:.2f} | {int(row['max_group_size']):,} |\n")

def main(data_dir=None):
    parser = argparse.ArgumentParser(description='Analyze distribution of plantri results')
    parser.add_argument('--v', type=int, required=True, help='Vertex count to analyze')
    parser.add_argument('--data_dir', type=str, default=None,
                       help='Data directory (overrides DATA_DIR environment variable)')
    parser.add_argument('--summary', required=True, help='Output markdown file')
    
    args = parser.parse_args()
    
    # Use provided arguments or defaults
    data_dir = args.data_dir or data_dir
    parquet_dir = get_parquet_dir(data_dir)
    
    # Ensure directories exist
    ensure_directories_exist(data_dir)
    
    conn = duckdb.connect()
    
    print(f"Analyzing v={args.v}...")
    print("Counting degree sequences...")
    deg_seq_counts = count_degree_sequences(conn, args.v, parquet_dir)
    
    print("Counting encoding groups...")
    encoding_groups = count_encoding_groups(conn, args.v, parquet_dir)
    
    # Ensure output directory exists
    output_path = DISTRIBUTION_DIR / args.summary
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Writing summary to {output_path}...")
    write_distribution_summary(args.v, deg_seq_counts, encoding_groups, str(output_path))
    
    print(f"\nAnalysis complete!")
    print(f"Total graphs: {deg_seq_counts['count'].sum():,}")
    print(f"Degree sequences: {len(deg_seq_counts)}")
    print(f"Encoding groups: {len(encoding_groups):,}")

if __name__ == "__main__":
    main()
