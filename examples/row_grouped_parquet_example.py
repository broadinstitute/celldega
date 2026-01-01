"""
Example: Creating a row-grouped Parquet file for efficient partial reading in JavaScript.

This demonstrates how to create Parquet files with multiple row groups,
which allows the JavaScript frontend to read only specific portions of the data.
"""

import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np
import pandas as pd
from pathlib import Path


def create_row_grouped_parquet(
    output_path: str,
    num_row_groups: int = 4,
    rows_per_group: int = 1000,
):
    """
    Create a Parquet file with multiple row groups.
    
    Each row group can be read independently by parquet-wasm,
    enabling efficient partial data loading.
    
    Args:
        output_path: Where to save the parquet file
        num_row_groups: Number of row groups to create
        rows_per_group: Number of rows in each row group
    """
    total_rows = num_row_groups * rows_per_group
    
    # Generate sample data
    np.random.seed(42)
    data = {
        'cell_id': [f'cell_{i}' for i in range(total_rows)],
        'x': np.random.uniform(0, 10000, total_rows).astype(np.float32),
        'y': np.random.uniform(0, 10000, total_rows).astype(np.float32),
        'cluster': np.random.choice(['A', 'B', 'C', 'D', 'E'], total_rows),
        'expression': np.random.exponential(5, total_rows).astype(np.float32),
        # Add a row_group_id column to easily verify which group was read
        'row_group_id': np.repeat(range(num_row_groups), rows_per_group),
    }
    
    df = pd.DataFrame(data)
    table = pa.Table.from_pandas(df)
    
    # Write with specific row group size
    # This creates multiple row groups that can be read independently
    pq.write_table(
        table,
        output_path,
        row_group_size=rows_per_group,
        compression='snappy',  # Good balance of speed and size
    )
    
    # Verify the file structure
    parquet_file = pq.ParquetFile(output_path)
    metadata = parquet_file.metadata
    
    print(f"Created Parquet file: {output_path}")
    print(f"  Total rows: {metadata.num_rows}")
    print(f"  Number of row groups: {metadata.num_row_groups}")
    print(f"  Number of columns: {metadata.num_columns}")
    print()
    
    for i in range(metadata.num_row_groups):
        rg = metadata.row_group(i)
        print(f"  Row group {i}: {rg.num_rows} rows")
    
    return output_path


def read_specific_row_groups(file_path: str, row_groups: list[int]):
    """
    Example of reading specific row groups (Python equivalent of what JS will do).
    
    Args:
        file_path: Path to parquet file
        row_groups: List of row group indices to read
    """
    parquet_file = pq.ParquetFile(file_path)
    
    # Read only specific row groups
    table = parquet_file.read_row_groups(row_groups)
    df = table.to_pandas()
    
    print(f"\nRead row groups {row_groups}:")
    print(f"  Shape: {df.shape}")
    print(f"  Row group IDs present: {sorted(df['row_group_id'].unique())}")
    print(df.head())
    
    return df


if __name__ == '__main__':
    # Create example output directory
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)
    
    # Create a row-grouped parquet file
    output_path = output_dir / 'row_grouped_example.parquet'
    create_row_grouped_parquet(
        str(output_path),
        num_row_groups=4,
        rows_per_group=1000,
    )
    
    # Demonstrate reading specific row groups
    read_specific_row_groups(str(output_path), [0, 2])  # Read only groups 0 and 2
    read_specific_row_groups(str(output_path), [1])     # Read only group 1
