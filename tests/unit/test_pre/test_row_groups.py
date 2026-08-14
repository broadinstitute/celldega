"""
Tests for row group storage mode functionality.

Tests the core concepts of row-grouped Parquet file creation
for transcripts, cell boundaries, CBG data, and image tiles.
"""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


class TestRowGroupMetadata:
    """Test metadata storage in row-grouped Parquet files."""

    def test_storage_mode_in_metadata(self, tmp_path):
        """Test that storage_mode is correctly stored in Parquet schema metadata."""
        schema = pa.schema(
            [
                ("id", pa.int64()),
                ("value", pa.float64()),
            ]
        )

        metadata = {
            b"storage_mode": b"row_groups_formula",
            b"tile_grid_info": json.dumps(
                {
                    "num_tiles_x": 10,
                    "num_tiles_y": 20,
                }
            ).encode("utf-8"),
        }

        schema_with_metadata = schema.with_metadata(metadata)

        output_path = tmp_path / "test_metadata.parquet"

        with pq.ParquetWriter(str(output_path), schema_with_metadata) as writer:
            table = pa.Table.from_pydict({"id": [1, 2, 3], "value": [1.0, 2.0, 3.0]})
            writer.write_table(table)

        # Read back and verify metadata
        pf = pq.ParquetFile(output_path)
        read_metadata = pf.schema_arrow.metadata

        assert b"storage_mode" in read_metadata
        assert read_metadata[b"storage_mode"] == b"row_groups_formula"

        tile_grid = json.loads(read_metadata[b"tile_grid_info"])
        assert tile_grid["num_tiles_x"] == 10
        assert tile_grid["num_tiles_y"] == 20

    def test_multiple_row_groups_written(self, tmp_path):
        """Test that multiple row groups can be written to a single file."""
        schema = pa.schema(
            [
                ("tile_x", pa.int64()),
                ("tile_y", pa.int64()),
                ("data", pa.float64()),
            ]
        )

        output_path = tmp_path / "multi_row_groups.parquet"

        with pq.ParquetWriter(str(output_path), schema, write_statistics=False) as writer:
            # Write 6 row groups (simulating a 3x2 tile grid)
            for tile_x in range(3):
                for tile_y in range(2):
                    table = pa.Table.from_pydict(
                        {
                            "tile_x": [tile_x, tile_x],
                            "tile_y": [tile_y, tile_y],
                            "data": [
                                float(tile_x * 10 + tile_y),
                                float(tile_x * 10 + tile_y + 0.5),
                            ],
                        }
                    )
                    writer.write_table(table)

        # Verify row group count
        pf = pq.ParquetFile(output_path)
        assert pf.metadata.num_row_groups == 6

    def test_empty_row_groups(self, tmp_path):
        """Test that empty row groups can be written to maintain index alignment."""
        schema = pa.schema(
            [
                ("tile_x", pa.int64()),
                ("tile_y", pa.int64()),
                ("data", pa.float64()),
            ]
        )

        output_path = tmp_path / "with_empty_row_groups.parquet"

        with pq.ParquetWriter(str(output_path), schema, write_statistics=False) as writer:
            # Write 4 row groups, 2 empty
            # Row group 0: has data
            writer.write_table(pa.Table.from_pydict({"tile_x": [0], "tile_y": [0], "data": [1.0]}))
            # Row group 1: empty
            writer.write_table(schema.empty_table())
            # Row group 2: empty
            writer.write_table(schema.empty_table())
            # Row group 3: has data
            writer.write_table(pa.Table.from_pydict({"tile_x": [1], "tile_y": [1], "data": [2.0]}))

        # Verify structure
        pf = pq.ParquetFile(output_path)
        assert pf.metadata.num_row_groups == 4

        # Check row counts per row group
        assert pf.read_row_group(0).num_rows == 1
        assert pf.read_row_group(1).num_rows == 0
        assert pf.read_row_group(2).num_rows == 0
        assert pf.read_row_group(3).num_rows == 1

    def test_cbg_gene_metadata(self, tmp_path):
        """Test that gene-to-row-group mapping can be stored in metadata."""
        genes = ["ACTB", "BRCA1", "CFTR"]
        gene_to_row_group = {gene: idx for idx, gene in enumerate(sorted(genes))}

        schema = pa.schema(
            [
                ("cell_id", pa.int64()),
                ("expression", pa.float64()),
            ]
        )

        metadata = {
            b"storage_mode": b"row_groups_cbg",
            b"gene_to_row_group": json.dumps(gene_to_row_group).encode("utf-8"),
        }

        schema_with_metadata = schema.with_metadata(metadata)
        output_path = tmp_path / "cbg.parquet"

        with pq.ParquetWriter(
            str(output_path), schema_with_metadata, write_statistics=False
        ) as writer:
            for _gene in sorted(genes):
                table = pa.Table.from_pydict(
                    {
                        "cell_id": [1, 2, 3],
                        "expression": [0.1, 0.2, 0.3],
                    }
                )
                writer.write_table(table)

        # Read back and verify
        pf = pq.ParquetFile(output_path)
        read_metadata = pf.schema_arrow.metadata

        assert b"gene_to_row_group" in read_metadata
        read_mapping = json.loads(read_metadata[b"gene_to_row_group"])
        assert read_mapping["ACTB"] == 0
        assert read_mapping["BRCA1"] == 1
        assert read_mapping["CFTR"] == 2


class TestFormulaBasedIndexing:
    """Test the formula-based indexing scheme."""

    def test_formula_index_computation(self):
        """Test that the formula row_group_index = tile_x * num_tiles_y + tile_y works correctly."""
        num_tiles_x = 10
        num_tiles_y = 5

        # Verify all tile coordinates map to unique, sequential indices
        indices = set()
        for tile_x in range(num_tiles_x):
            for tile_y in range(num_tiles_y):
                index = tile_x * num_tiles_y + tile_y
                assert index not in indices, f"Duplicate index {index}"
                indices.add(index)

        # Verify indices cover full range
        assert indices == set(range(num_tiles_x * num_tiles_y))

    def test_formula_reversibility(self):
        """Test that we can reverse the formula to get tile coordinates from index."""
        num_tiles_x = 10
        num_tiles_y = 5

        for tile_x in range(num_tiles_x):
            for tile_y in range(num_tiles_y):
                index = tile_x * num_tiles_y + tile_y

                # Reverse the formula
                recovered_tile_x = index // num_tiles_y
                recovered_tile_y = index % num_tiles_y

                assert recovered_tile_x == tile_x
                assert recovered_tile_y == tile_y

    def test_formula_with_large_grid(self):
        """Test formula with realistic grid dimensions (like Xenium data)."""
        # Typical Xenium grid: 137x55
        num_tiles_x = 137
        num_tiles_y = 55
        total_tiles = num_tiles_x * num_tiles_y

        # Spot check some tiles
        test_cases = [
            (0, 0, 0),
            (0, 54, 54),
            (1, 0, 55),
            (136, 54, 136 * 55 + 54),
        ]

        for tile_x, tile_y, expected_index in test_cases:
            computed = tile_x * num_tiles_y + tile_y
            assert computed == expected_index, (
                f"({tile_x}, {tile_y}) -> {computed}, expected {expected_index}"
            )

        # Verify max index
        assert (num_tiles_x - 1) * num_tiles_y + (num_tiles_y - 1) == total_tiles - 1


class TestLandscapeParametersRowGroups:
    """Test landscape_parameters.json structure for row group mode."""

    def test_landscape_parameters_structure(self, tmp_path):
        """Test that landscape_parameters.json contains correct structure."""
        params = {
            "technology": "Xenium",
            "tile_size": 250,
            "use_row_groups": True,
            "row_group_files": {
                "transcripts": "transcripts.parquet",
                "cell_segmentation": "cell_segmentation.parquet",
                "cbg": "cbg.parquet",
                "images": {
                    "dapi": {
                        "path": "image_parquet/dapi.parquet",
                        "zoom_info": {
                            "max_zoom": 14,
                            "tiles_per_zoom": {"11": 100, "12": 400, "13": 1600, "14": 6400},
                        },
                    },
                },
            },
            "tile_grid": {
                "num_tiles_x": 137,
                "num_tiles_y": 55,
                "tile_size": 250,
            },
            "image_dimensions": {
                "dapi": {"width": 34000, "height": 13500},
            },
        }

        output_path = tmp_path / "landscape_parameters.json"
        with Path.open(output_path, "w") as f:
            json.dump(params, f, indent=2)

        # Read back and verify
        with Path.open(output_path) as f:
            read_params = json.load(f)

        # Verify key fields
        assert read_params["use_row_groups"] is True
        assert "row_group_files" in read_params
        assert read_params["row_group_files"]["transcripts"] == "transcripts.parquet"
        assert "tile_grid" in read_params
        assert read_params["tile_grid"]["num_tiles_x"] == 137
        assert read_params["tile_grid"]["num_tiles_y"] == 55

        # Verify image config
        assert "images" in read_params["row_group_files"]
        dapi_config = read_params["row_group_files"]["images"]["dapi"]
        assert dapi_config["path"] == "image_parquet/dapi.parquet"
        assert "zoom_info" in dapi_config


class TestRowGroupReading:
    """Test reading specific row groups from Parquet files."""

    def test_read_specific_row_groups(self, tmp_path):
        """Test that specific row groups can be read efficiently."""
        schema = pa.schema(
            [
                ("tile_id", pa.int64()),
                ("value", pa.float64()),
            ]
        )

        output_path = tmp_path / "tiles.parquet"

        # Write 10 row groups
        with pq.ParquetWriter(str(output_path), schema) as writer:
            for i in range(10):
                table = pa.Table.from_pydict(
                    {
                        "tile_id": [i] * 5,
                        "value": [float(i * 10 + j) for j in range(5)],
                    }
                )
                writer.write_table(table)

        # Read only specific row groups
        pf = pq.ParquetFile(output_path)

        # Read row groups 2 and 5
        table_2 = pf.read_row_group(2)
        table_5 = pf.read_row_group(5)

        # Verify correct data
        assert table_2.column("tile_id").to_pylist() == [2, 2, 2, 2, 2]
        assert table_5.column("tile_id").to_pylist() == [5, 5, 5, 5, 5]

    def test_read_multiple_row_groups_at_once(self, tmp_path):
        """Test reading multiple row groups in a single call."""
        schema = pa.schema(
            [
                ("tile_id", pa.int64()),
            ]
        )

        output_path = tmp_path / "tiles.parquet"

        with pq.ParquetWriter(str(output_path), schema) as writer:
            for i in range(5):
                table = pa.Table.from_pydict({"tile_id": [i]})
                writer.write_table(table)

        # Read multiple row groups
        pf = pq.ParquetFile(output_path)
        combined = pf.read_row_groups([0, 2, 4])

        # Should have 3 rows (one from each row group)
        assert combined.num_rows == 3
        # Values should be from row groups 0, 2, 4
        assert set(combined.column("tile_id").to_pylist()) == {0, 2, 4}
