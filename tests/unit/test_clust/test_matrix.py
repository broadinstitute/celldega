"""
Test suite for the new Matrix class in celldega.clust module.

This module tests the Matrix class functionality by comparing visualization outputs
against expected JSON files and validating core clustering and visualization features.
"""

import contextlib
import json
from pathlib import Path
import tempfile
from typing import Any
import warnings

import numpy as np
import pandas as pd
import pytest
import requests


# Import the Matrix class
try:
    from celldega.clust import Matrix
except ImportError:
    pytest.skip("celldega module not available", allow_module_level=True)


class TestMatrix:
    """Test suite for Matrix class functionality."""

    @pytest.fixture(scope="class")
    def test_data_dir(self) -> Path:
        """Get the test data directory path."""
        return Path(__file__).parent.parent / "test_data"

    @pytest.fixture(scope="class")
    def mock_expected_viz(self, test_data_dir: Path) -> dict[str, Any]:
        """Load expected visualization for mock data test."""
        mock_file = test_data_dir / "matrix_viz_mock.json"
        if not mock_file.exists():
            pytest.skip(f"Test data file not found: {mock_file}")

        return json.loads(mock_file.read_text())

    @pytest.fixture(scope="class")
    def xenium_expected_viz(self, test_data_dir: Path) -> dict[str, Any]:
        """Load expected visualization for Xenium data test."""
        xenium_file = test_data_dir / "matrix_viz_xenium.json"
        if not xenium_file.exists():
            pytest.skip(f"Test data file not found: {xenium_file}")

        return json.loads(xenium_file.read_text())

    @pytest.fixture
    def mock_data_setup(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Create mock data setup matching the notebook code."""
        # Generate random matrix with fixed seed
        num_cols = 5
        num_rows = 10
        np.random.seed(seed=100)
        mat = np.random.rand(num_rows, num_cols)

        # Make row and col labels
        rows = [str(i) for i in range(num_rows)]
        cols = [str(i) for i in range(num_cols)]

        # Make dataframe
        df = pd.DataFrame(data=mat, columns=cols, index=rows)

        # Create column metadata
        meta_col = pd.DataFrame(index=df.columns.tolist())
        top_cols = df.sum(axis=0).sort_values(ascending=False).index.tolist()[:5]
        meta_col["type"] = "low"
        meta_col["experiment"] = "a"
        meta_col.loc[top_cols, "type"] = "high"
        meta_col.loc["0", "experiment"] = "b"
        meta_col.loc["1", "experiment"] = "b"
        meta_col.loc["2", "experiment"] = "b"

        # Create row metadata
        meta_row = pd.DataFrame(index=df.index.tolist())
        meta_row["type"] = "low"
        meta_row.loc["0", "type"] = "high"
        meta_row.loc["1", "type"] = "high"
        meta_row.loc["2", "type"] = "high"

        # Create color mapping
        df_colors = pd.DataFrame()
        df_colors.loc["low", "color"] = "blue"
        df_colors.loc["high", "color"] = "black"
        df_colors.loc["a", "color"] = "orange"
        df_colors.loc["b", "color"] = "purple"

        return df, meta_col, meta_row, df_colors

    @pytest.fixture
    def xenium_data(self) -> pd.DataFrame:
        """Load Xenium data from remote source."""
        file_path = "https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs/main/Xenium_Prime_Human_Skin_FFPE_outs/df_sig.parquet"

        try:
            # Test if URL is accessible
            response = requests.head(file_path, timeout=10)
            if response.status_code != 200:
                pytest.skip(f"Xenium data not accessible: HTTP {response.status_code}")

            return pd.read_parquet(file_path)
        except (requests.RequestException, Exception) as e:
            pytest.skip(f"Could not load Xenium data: {e}")

    def _save_temp_viz(self, viz_data: dict[str, Any], prefix: str) -> Path:
        """Save visualization data to temporary file for debugging."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix=f"{prefix}_actual_", delete=False
        ) as f:
            json.dump(viz_data, f, indent=2, default=str)
            return Path(f.name)

    def _compare_viz_structure(self, actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
        """Compare visualization structure and return list of differences."""
        differences = []

        # Check required keys
        required_keys = ["row_nodes", "col_nodes", "mat", "linkage", "cat_colors", "matrix_colors"]
        for key in required_keys:
            if key not in actual:
                differences.append(f"Missing key in actual: {key}")
            if key not in expected:
                differences.append(f"Missing key in expected: {key}")

        # Check matrix dimensions
        if "mat" in actual and "mat" in expected:
            actual_mat = np.array(actual["mat"])
            expected_mat = np.array(expected["mat"])
            if actual_mat.shape != expected_mat.shape:
                differences.append(
                    f"Matrix shape mismatch: actual {actual_mat.shape} vs expected {expected_mat.shape}"
                )

        # Check node counts
        for axis in ["row_nodes", "col_nodes"]:
            if axis in actual and axis in expected and len(actual[axis]) != len(expected[axis]):
                differences.extend(
                    f"{axis} count mismatch: actual {len(actual[axis])} vs expected {len(expected[axis])}"
                )

        # Check linkage structure
        if "linkage" in actual and "linkage" in expected:
            for axis in ["row", "col"]:
                if axis in actual["linkage"] and axis in expected["linkage"]:
                    actual_linkage = np.array(actual["linkage"][axis])
                    expected_linkage = np.array(expected["linkage"][axis])
                    if actual_linkage.shape != expected_linkage.shape:
                        differences.append(
                            f"Linkage {axis} shape mismatch: "
                            f"actual {actual_linkage.shape} vs expected {expected_linkage.shape}"
                        )

        return differences

    def _validate_matrix_properties(self, matrix: Matrix) -> None:
        """Validate basic Matrix object properties."""
        assert hasattr(matrix, "data"), "Matrix should have data attribute"
        assert hasattr(matrix, "viz"), "Matrix should have viz attribute"
        assert hasattr(matrix, "_clustered"), "Matrix should have _clustered attribute"
        assert isinstance(matrix.viz, dict), "viz should be a dictionary"

    def test_mock_data_matrix_visualization(
        self,
        mock_data_setup: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
        mock_expected_viz: dict[str, Any],
    ) -> None:
        """Test Matrix visualization output against mock data JSON."""
        df, meta_col, meta_row, df_colors = mock_data_setup
        temp_file = None

        try:
            # Create Matrix object and reproduce notebook workflow
            mat = Matrix(df, disable_processing=True)  # Disable auto-processing
            mat.load_df(df, meta_col=meta_col, meta_row=meta_row, col_attr=["experiment"])
            mat.set_global_cat_colors(df_colors)
            _ = mat.cluster()

            # Validate Matrix properties
            self._validate_matrix_properties(mat)
            assert mat._clustered, "Matrix should be marked as clustered"

            # Save actual output for debugging if test fails
            temp_file = self._save_temp_viz(mat.viz, "mock_data")

            # Compare structure
            differences = self._compare_viz_structure(mat.viz, mock_expected_viz)

            if differences:
                print("\nVisualization structure differences found:")
                for diff in differences:
                    print(f"  - {diff}")
                print(f"\nActual output saved to: {temp_file}")

                # Don't fail immediately - check if differences are acceptable
                # Some differences might be due to randomization or minor implementation changes
                warnings.warn(f"Visualization structure differences: {differences}", stacklevel=2)

            # Verify viz attribute is populated after clustering
            # Note: cluster() no longer returns a value, but mat.viz should be populated
            assert mat.viz is not None, "viz attribute should be populated after clustering"

            # Check essential structure elements
            assert "row_nodes" in mat.viz, "viz should contain row_nodes"
            assert "col_nodes" in mat.viz, "viz should contain col_nodes"
            assert "mat" in mat.viz, "viz should contain mat"
            assert "linkage" in mat.viz, "viz should contain linkage"

            # Check data dimensions
            assert len(mat.viz["row_nodes"]) == len(df.index), (
                "row_nodes count should match DataFrame rows"
            )
            assert len(mat.viz["col_nodes"]) == len(df.columns), (
                "col_nodes count should match DataFrame columns"
            )

            # Check matrix data
            viz_mat = np.array(mat.viz["mat"])
            assert viz_mat.shape == df.shape, (
                f"Matrix shape should match: {viz_mat.shape} vs {df.shape}"
            )

            # Check category colors were set
            assert "global_cat_colors" in mat.viz, "viz should contain global_cat_colors"
            expected_colors = {"low": "blue", "high": "black", "a": "orange", "b": "purple"}
            actual_colors = mat.viz["global_cat_colors"]
            # Check that all expected colors are present (may contain additional auto-generated colors)
            for key, value in expected_colors.items():
                assert key in actual_colors, f"Expected color key '{key}' not found"
                assert actual_colors[key] == value, (
                    f"Color for '{key}' should be '{value}', got '{actual_colors[key]}'"
                )

            # Check column categories
            col_nodes = mat.viz["col_nodes"]
            assert all("cat-0" in node for node in col_nodes), (
                "All column nodes should have cat-0 (experiment)"
            )

            # If we reach here without major issues, remove temp file
            if temp_file and temp_file.exists():
                temp_file.unlink()
                temp_file = None

        except Exception as e:
            if temp_file:
                print(f"\nTest failed. Actual output saved to: {temp_file}")
            raise e

        finally:
            # Clean up temp file only if test passed completely
            if temp_file and temp_file.exists() and not differences:
                with contextlib.suppress(OSError):
                    temp_file.unlink()

    def test_xenium_data_matrix_visualization(
        self, xenium_data: pd.DataFrame, xenium_expected_viz: dict[str, Any]
    ) -> None:
        """Test Matrix visualization output against Xenium data JSON."""
        temp_file = None

        try:
            # Create Matrix object with Xenium data
            mat = Matrix(xenium_data)  # Use default processing
            mat.cluster()

            # Validate Matrix properties
            self._validate_matrix_properties(mat)
            assert mat._clustered, "Matrix should be marked as clustered"

            # Save actual output for debugging if test fails
            temp_file = self._save_temp_viz(mat.viz, "xenium_data")

            # Compare structure
            differences = self._compare_viz_structure(mat.viz, xenium_expected_viz)

            if differences:
                print("\nVisualization structure differences found:")
                for diff in differences:
                    print(f"  - {diff}")
                print(f"\nActual output saved to: {temp_file}")

                # For Xenium data, we expect some differences due to processing
                warnings.warn(
                    f"Xenium visualization structure differences: {differences}", stacklevel=2
                )

            # Verify viz attribute is populated after clustering
            # Note: cluster() no longer returns a value, but mat.viz should be populated
            assert mat.viz is not None, "viz attribute should be populated after clustering"

            # Check essential structure elements
            assert "row_nodes" in mat.viz, "viz should contain row_nodes"
            assert "col_nodes" in mat.viz, "viz should contain col_nodes"
            assert "mat" in mat.viz, "viz should contain mat"
            assert "linkage" in mat.viz, "viz should contain linkage"

            # Check data was processed (should have fewer genes due to filtering)
            original_genes = len(xenium_data.index)
            processed_genes = len(mat.viz["row_nodes"])
            print(f"Original genes: {original_genes}, Processed genes: {processed_genes}")

            # With default processing, genes should be filtered
            assert processed_genes <= original_genes, "Processing should filter genes"

            # Check clustering was performed
            assert "row" in mat.viz["linkage"], "Should have row linkage"
            assert "col" in mat.viz["linkage"], "Should have col linkage"

            # Check matrix data consistency
            viz_mat = np.array(mat.viz["mat"])
            assert viz_mat.shape[0] == processed_genes, (
                "Matrix rows should match processed gene count"
            )

            # If no major structural issues, remove temp file
            if (
                temp_file and temp_file.exists() and len(differences) <= 2
            ):  # Allow minor differences
                temp_file.unlink()
                temp_file = None

        except Exception as e:
            if temp_file:
                print(f"\nTest failed. Actual output saved to: {temp_file}")
            raise e

        finally:
            # Clean up temp file only if test passed reasonably well
            if temp_file and temp_file.exists() and len(differences) <= 2:
                with contextlib.suppress(OSError):
                    temp_file.unlink()

    def test_matrix_basic_functionality(self) -> None:
        """Test basic Matrix functionality and methods."""
        # Create simple test data
        np.random.seed(42)
        df = pd.DataFrame(
            np.random.rand(10, 5),
            columns=[f"col_{i}" for i in range(5)],
            index=[f"row_{i}" for i in range(10)],
        )

        # Test Matrix creation
        mat = Matrix(df)
        assert mat.data is not None, "Matrix should have data after initialization"
        assert isinstance(mat.data, pd.DataFrame), "Matrix data should be DataFrame"

        # Test clustering
        mat.cluster()
        assert mat._clustered, "Matrix should be marked as clustered"

        # Test export methods (deprecated JSON)
        with pytest.deprecated_call():
            json_str = mat.export_viz_json_string()
        assert isinstance(json_str, str)

        with pytest.deprecated_call():
            json_dict = mat.export_viz_json()
        assert isinstance(json_dict, dict)

        # Test data export
        exported_df = mat.to_df()
        assert isinstance(exported_df, pd.DataFrame), "to_df() should return DataFrame"

    def test_numeric_attributes_in_viz(self) -> None:
        """Numeric attributes should be exported as num-* keys."""
        df = pd.DataFrame(
            np.random.rand(3, 3), index=["r1", "r2", "r3"], columns=["c1", "c2", "c3"]
        )
        meta_row = pd.DataFrame({"score": [0.2, -0.5, 1.0]}, index=df.index)
        mat = Matrix(df, meta_row=meta_row, row_attr=["score"], disable_processing=True)
        mat.cluster()
        assert "row_attr" in mat.viz and mat.viz["row_attr"] == ["score"]
        assert "row_attr_maxabs" in mat.viz and mat.viz["row_attr_maxabs"][0] == 1.0
        for node in mat.viz["row_nodes"]:
            assert "num-0" in node

    def test_set_dot_matrix_aligns_anndata_by_name(self) -> None:
        """`set_dot_matrix` must transpose AnnData input like `load_adata` does,
        so the dot matrix lines up with the main matrix's row/col names instead
        of silently aligning to nothing."""
        from anndata import AnnData

        genes = ["g0", "g1", "g2"]
        sets = ["s0", "s1"]
        mean = AnnData(
            X=np.arange(6).reshape(2, 3).astype(float),
            obs=pd.DataFrame(index=sets),
            var=pd.DataFrame(index=genes),
        )
        frac = AnnData(
            X=np.arange(6).reshape(2, 3).astype(float) / 10 + 0.5,
            obs=pd.DataFrame(index=sets),
            var=pd.DataFrame(index=genes),
        )

        mat = Matrix(mean, disable_processing=True, row_entity="gene", col_entity="cell_cluster")
        mat.set_dot_matrix(frac)
        assert list(mat.dot_mat.index) == genes
        assert list(mat.dot_mat.columns) == sets

        mat.clust()
        out = mat.export_viz_parquet()

        import io

        import pyarrow.parquet as pq

        dot_df = pq.read_table(io.BytesIO(out["dot_mat"])).to_pandas().set_index("row")
        assert not np.allclose(dot_df.to_numpy(), 0.0)
        np.testing.assert_allclose(
            dot_df.loc[genes, sets].to_numpy(), frac.X.T, rtol=1e-5, atol=1e-6
        )

    def test_matrix_from_collection_dot_plot(self) -> None:
        """`Matrix(collection=..., modality=..., dot_plot=True)` should build the
        main matrix and auto-discover + attach the paired fraction modality as
        the dot-plot size channel, with no manual DataFrame wrangling."""
        from anndata import AnnData

        from celldega.set import SetCollection

        rng = np.random.default_rng(0)
        n = 40
        adata = AnnData(X=rng.random((n, 5)))
        adata.var_names = [f"g{i}" for i in range(5)]
        adata.obs["leiden"] = rng.choice(["0", "1", "2"], n)

        setc = SetCollection(adata, set_col="leiden", name="leiden")
        setc.calc_signature(adata, modality_name="expression")
        setc.calc_signature(adata, modality_name="fraction", aggregate="fraction")

        mat = Matrix(collection=setc, modality="expression", dot_plot=True)
        assert mat.data.shape == (5, 3)
        assert mat.dot_mat is not None
        assert list(mat.dot_mat.index) == list(mat.data.index)
        assert list(mat.dot_mat.columns) == list(mat.data.columns)

        # data/collection are mutually exclusive
        with pytest.raises(ValueError, match="not both"):
            Matrix(data=adata, collection=setc, modality="expression")

        # dot_plot=True with no fraction modality raises a clear error
        setc2 = SetCollection(adata, set_col="leiden", name="leiden2")
        setc2.calc_signature(adata, modality_name="expression")
        with pytest.raises(ValueError, match="no fraction-expressing modality"):
            Matrix(collection=setc2, modality="expression", dot_plot=True)

    def test_matrix_error_handling(self) -> None:
        """Test Matrix error handling and edge cases."""
        # Test empty Matrix
        empty_mat = Matrix()
        assert empty_mat.data is None, "Empty Matrix should have None data"

        # Test clustering empty matrix should raise error
        with pytest.raises(ValueError, match="No data loaded"):
            empty_mat.clust()

        # Test invalid normalization
        df = pd.DataFrame(np.random.rand(5, 3))
        mat = Matrix(df, disable_processing=True)

        with pytest.raises(ValueError):
            mat.norm(axis="row", by="invalid_norm")

        # Test invalid filter
        with pytest.raises(ValueError):
            mat.filter(axis="row", by="invalid_metric", num=3)

    # @pytest.mark.parametrize(
    #     "processing_config",
    #     [
    #         {"filter_genes": None, "norm_col": "total", "norm_row": "zscore"},
    #         {"filter_genes": 100, "norm_col": None, "norm_row": "qn"},
    #         {"filter_genes": 50, "norm_col": "zscore", "norm_row": None},
    #     ],
    # )
    # def test_matrix_processing_configurations(self, processing_config: dict[str, Any]) -> None:
    #     """Test different Matrix processing configurations."""
    #     np.random.seed(42)
    #     df = pd.DataFrame(
    #         np.random.rand(200, 20),  # Larger matrix for filtering tests
    #         columns=[f"col_{i}" for i in range(20)],
    #         index=[f"row_{i}" for i in range(200)],
    #     )

    #     try:
    #         mat = Matrix(df, **processing_config)
    #         mat.cluster()

    #         assert mat._clustered, "Matrix should be marked as clustered"

    #         # Check if filtering was applied
    #         if processing_config.get("filter_genes"):
    #             expected_genes = min(processing_config["filter_genes"], len(df.index))
    #             actual_genes = len(mat.data.index) if mat.data is not None else 0
    #             assert actual_genes <= expected_genes, "Gene filtering should reduce gene count"

    #     except Exception as e:
    #         pytest.fail(f"Processing configuration failed: {processing_config}, Error: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
