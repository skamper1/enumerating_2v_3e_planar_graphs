# README

This repository contains a collection python scripts that together with the program plantri (https://users.cecs.anu.edu.au/~bdm/plantri/) by Gunnar Brinkmann and Heidi Van den Camp (University of Ghent), and Brendan McKay (Australian National University) enumerate the number of non-isomorphic planar graphs with $n$ edges that are exactly 2-vertex-connected and at least 3-edge-connected.

These counts define the sequence [A393183](https://oeis.org/A393183) in the On-Line Encyclopedia of Integer Sequences (OEIS).

## Setup

1. **Configure environment (optional)**: Copy `.env.example` to `.env` and customize paths:
   ```bash
   cp .env.example .env
   ```
   - `DATA_DIR`: Root directory for data files (default: `./data`)
   - `PLANTRI_PATH`: Path to plantri binary (default: `./plantri55/plantri`)

2. **Build plantri** (if needed):
   ```bash
   cd plantri55
   make plantri
   ```

## Scripts

There are three main processing scripts and helper function modules (`graph_encoding.py` and `graph_import.py`):

1. **`plantri_to_parquet.py`** — Calls plantri, processes the graph data for all quartic graphs of a given v, splits them by their bipartition and finds the "face" or diagonal graphs. It then writes only the exactly 2-vertex connected graphs to `.parquet` files in directories split by degree sequence with an encoding to further categorise these graphs still grouping isomorphisms together.

2. **`analyze_distribution.py`** — Reads through these encodings and counts them by degree sequence and reports on the distribution.

3. **`check_isomorphisms.py`** — Runs isomorphism checks across all graphs with the same encoding and reports the number of unique (non-isomorphic graphs).

## Usage Examples

### 1. Generate Parquet Data from Plantri

Process graphs for vertex counts 12 to 14:

```bash
python plantri_to_parquet.py --v_min 12 --v_max 14 --summary processing_summary.md
```

With custom data directory:

```bash
python plantri_to_parquet.py --v_min 12 --v_max 14 --data_dir /custom/path --summary processing_summary.md
```

### 2. Analyze Distribution

Analyze distribution for v=12 and output to `distribution_data/`:

```bash
python analyze_distribution.py --v 12 --summary distribution_v12.md
```

The script automatically outputs to the `distribution_data/` directory.

### 3. Check Isomorphisms

Check isomorphisms for all degree sequences at v=12:

```bash
python check_isomorphisms.py --v 12 --summary isomorphism_v12.md
```

Check specific degree sequences only:

```bash
python check_isomorphisms.py --v 12 --degree_seq "4 4 4 4 4 4" "4 4 4 4 3 5" --summary isomorphism_v12.md
```

With CSV output and custom parameters:

```bash
python check_isomorphisms.py --v 12 --summary isomorphism_v12.md --csv results_v12.csv --min_group_size 3
```

The script automatically outputs markdown and CSV files to the `isomorphism_data/` directory.

## Results

These results are provided up to v=25 for distribution data and v=24 for isomorphism data in the `distribution_data/` and `isomorphism_data/` directories respectively.





