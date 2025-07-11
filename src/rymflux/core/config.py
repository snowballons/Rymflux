# rymflux/core/config.py

import yaml
from typing import List, Dict, Any

def load_sources_from_yaml(filepath: str) -> List[Dict[str, Any]]:
    """
    Loads and parses a YAML file containing a list of sources.

    Args:
        filepath: The path to the sources.yaml file.

    Returns:
        A list of dictionaries, where each dictionary is a source configuration.
        Returns an empty list if the file is not found or is empty.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            # The YAML file has a top-level 'sources' key
            if data and "sources" in data:
                return data["sources"]
    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{filepath}'")
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
    
    return []