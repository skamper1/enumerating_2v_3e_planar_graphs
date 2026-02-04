"""Configuration management for the planar graphs project.

Environment variables:
    DATA_DIR: Root directory for data files and output (default: ./data)
    PLANTRI_PATH: Path to plantri binary (default: ./plantri55/plantri)
"""

import os
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Data directory configuration
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")).resolve()

# Plantri binary path configuration
PLANTRI_PATH = os.getenv("PLANTRI_PATH", str(PROJECT_ROOT / "plantri55" / "plantri"))

# Subdirectories within DATA_DIR
PARQUET_DIR = DATA_DIR / "parquet_data"
DISTRIBUTION_DIR = PROJECT_ROOT / "distribution_data"
ISOMORPHISM_DIR = PROJECT_ROOT / "isomorphism_data"


def get_data_dir(data_dir=None):
    """Get the data directory, with optional override.
    
    Args:
        data_dir: Override the configured data directory.
        
    Returns:
        The data directory path.
    """
    if data_dir:
        return Path(data_dir).resolve()
    return DATA_DIR


def get_plantri_path(plantri_path=None):
    """Get the plantri binary path, with optional override.
    
    Args:
        plantri_path: Override the configured plantri path.
        
    Returns:
        The plantri binary path.
    """
    if plantri_path:
        return str(plantri_path)
    return PLANTRI_PATH


def get_parquet_dir(data_dir=None):
    """Get the parquet data directory.
    
    Args:
        data_dir: Override the base data directory.
        
    Returns:
        The parquet directory path.
    """
    return get_data_dir(data_dir) / "parquet_data"


def ensure_directories_exist(data_dir=None):
    """Ensure required directories exist.
    
    Args:
        data_dir: Override the base data directory.
    """
    parquet_dir = get_parquet_dir(data_dir)
    DISTRIBUTION_DIR.mkdir(parents=True, exist_ok=True)
    ISOMORPHISM_DIR.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)
