from pathlib import Path
import sys
from unittest.mock import Mock

import numpy as np
import pytest


# Add the source directory to the path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

from celldega.clust.make_viz import viz_json


class TestVizJsonBase:
    """Base class with common test utilities and fixtures."""

    @staticmethod
    def create_base_net_mock(**overrides):
        """Create a base mock network object with optional overrides."""
        defaults = {
            "viz": {"linkage": {}, "row_nodes": [], "col_nodes": [], "links": [], "mat": []},
            "dat": {
                "nodes": {"row": ["gene1", "gene2"], "col": ["sample1", "sample2"]},
                "node_info": {
                    "row": {
                        "Y": np.array([[1, 2], [3, 4]]),  # Use numpy array so .tolist() works
                        "ini": [0, 1],
                        "clust": [0, 1],
                        "rank": [0, 1],
                        "value": [],
                        "info": [],
                    },
                    "col": {
                        "Y": np.array([[5, 6], [7, 8]]),  # Use numpy array so .tolist() works
                        "ini": [0, 1],
                        "clust": [0, 1],
                        "rank": [0, 1],
                        "value": [],
                        "info": [],
                    },
                },
                "mat": np.array([[1.0, 2.0], [3.0, 4.0]]),
            },
        }

        # Apply overrides recursively
        def deep_update(base, updates):
            for key, value in updates.items():
                if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                    deep_update(base[key], value)
                else:
                    base[key] = value

        deep_update(defaults, overrides)

        net = Mock()
        net.viz = defaults["viz"]
        net.dat = defaults["dat"]
        return net

    @staticmethod
    def assert_basic_structure(net, expected_rows=2, expected_cols=2):
        """Assert basic visualization structure is correct."""
        assert "linkage" in net.viz
        assert "row" in net.viz["linkage"]
        assert "col" in net.viz["linkage"]
        assert len(net.viz["row_nodes"]) == expected_rows
        assert len(net.viz["col_nodes"]) == expected_cols

    @staticmethod
    def assert_node_structure(node, name, ini=0, clust=0, rank=0):
        """Assert basic node structure."""
        assert node["name"] == name
        assert node["ini"] == ini
        assert node["clust"] == clust
        assert node["rank"] == rank


class TestVizJsonBasic(TestVizJsonBase):
    """Test basic functionality of viz_json function."""

    def test_matrix_mode_basic(self):
        """Test basic functionality with matrix output."""
        net = self.create_base_net_mock()

        viz_json(net, dendro=True, links=False)

        self.assert_basic_structure(net)
        assert net.viz["mat"] == [[1.0, 2.0], [3.0, 4.0]]
        assert len(net.viz["links"]) == 0

    def test_links_mode_basic(self):
        """Test basic functionality with links output."""
        net = self.create_base_net_mock()

        viz_json(net, dendro=True, links=True)

        self.assert_basic_structure(net)
        assert len(net.viz["links"]) == 4  # 2x2 matrix = 4 links

        # Check first link structure
        first_link = net.viz["links"][0]
        assert first_link == {"source": 0, "target": 0, "value": 1.0}

    def test_node_structure_creation(self):
        """Test that node structure is created correctly."""
        net = self.create_base_net_mock()

        viz_json(net, dendro=True, links=False)

        self.assert_node_structure(net.viz["row_nodes"][0], "gene1")
        self.assert_node_structure(net.viz["col_nodes"][0], "sample1")

    def test_linkage_data_conversion(self):
        """Test linkage data is properly converted to lists."""
        net = self.create_base_net_mock()

        viz_json(net, dendro=True, links=False)

        assert net.viz["linkage"]["row"] == [[1, 2], [3, 4]]
        assert net.viz["linkage"]["col"] == [[5, 6], [7, 8]]


class TestVizJsonWithFeatures(TestVizJsonBase):
    """Test viz_json with additional features like categories, values, etc."""

    def test_with_values_and_info(self):
        """Test with value and info data."""
        net = self.create_base_net_mock(
            dat={"node_info": {"row": {"value": ["val1", "val2"], "info": ["info1", "info2"]}}}
        )

        viz_json(net, dendro=True, links=False)

        row_node = net.viz["row_nodes"][0]
        assert row_node["value"] == "val1"
        assert row_node["info"] == "info1"

    def test_with_rankvar(self):
        """Test with rankvar data."""
        net = self.create_base_net_mock(dat={"node_info": {"row": {"rankvar": [0.5, 0.8]}}})

        viz_json(net, dendro=True, links=False)

        assert net.viz["row_nodes"][0]["rankvar"] == 0.5
        assert net.viz["row_nodes"][1]["rankvar"] == 0.8

    def test_with_categories(self):
        """Test category processing."""
        net = self.create_base_net_mock(
            dat={
                "node_info": {
                    "row": {
                        "cat-0": ["typeA", "typeB"],
                        "cat-1": ["classX", "classY"],
                        "cat_0_index": [0, 1],
                        "cat_1_index": [0, 1],
                    }
                }
            }
        )

        viz_json(net, dendro=True, links=False)

        row_node = net.viz["row_nodes"][0]
        assert row_node["cat-0"] == "typeA"
        assert row_node["cat-1"] == "classX"
        assert row_node["cat_0_index"] == 0
        assert row_node["cat_1_index"] == 0

    def test_with_pvalues(self):
        """Test p-value processing."""
        net = self.create_base_net_mock(
            dat={
                "node_info": {
                    "row": {
                        "cat-0": ["typeA", "typeB"],
                        "pval_cat_0": {"typeA": 0.01, "typeB": 0.05},
                        "cat_0_index": [0, 1],
                    }
                }
            }
        )

        viz_json(net, dendro=True, links=False)

        assert net.viz["row_nodes"][0]["cat_0_pval"] == 0.01
        assert net.viz["row_nodes"][1]["cat_0_pval"] == 0.05


class TestVizJsonEdgeCases(TestVizJsonBase):
    """Test edge cases and boundary conditions."""

    def test_empty_nodes(self):
        """Test with empty node lists."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": [], "col": []},
                "node_info": {
                    "row": {
                        "Y": np.array([]),
                        "ini": [],
                        "clust": [],
                        "rank": [],
                        "value": [],
                        "info": [],
                    },
                    "col": {
                        "Y": np.array([]),
                        "ini": [],
                        "clust": [],
                        "rank": [],
                        "value": [],
                        "info": [],
                    },
                },
                "mat": np.array([]),
            }
        )

        viz_json(net, dendro=True, links=False)

        self.assert_basic_structure(net, expected_rows=0, expected_cols=0)
        assert net.viz["mat"] == []

    def test_single_node(self):
        """Test with single node in each dimension."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": ["gene1"], "col": ["sample1"]},
                "node_info": {
                    "row": {
                        "Y": np.array([[1]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": ["val1"],
                        "info": ["info1"],
                    },
                    "col": {
                        "Y": np.array([[2]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": [],
                        "info": [],
                    },
                },
                "mat": np.array([[5.0]]),
            }
        )

        viz_json(net, dendro=True, links=False)

        self.assert_basic_structure(net, expected_rows=1, expected_cols=1)
        assert net.viz["mat"] == [[5.0]]

        row_node = net.viz["row_nodes"][0]
        self.assert_node_structure(row_node, "gene1")
        assert row_node["value"] == "val1"
        assert row_node["info"] == "info1"

    def test_nan_values_in_matrix(self):
        """Test NaN handling in matrix/links mode."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": ["gene1"], "col": ["sample1"]},
                "node_info": {
                    "row": {
                        "Y": np.array([[1]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": [],
                        "info": [],
                    },
                    "col": {
                        "Y": np.array([[2]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": [],
                        "info": [],
                    },
                },
                "mat": np.array([[np.nan]]),
            }
        )

        viz_json(net, dendro=True, links=True)

        link = net.viz["links"][0]
        assert np.isnan(link["value"])
        # Bug reproduction: value_orig gets set to "NaN" string when value is NaN
        assert "value_orig" in link
        assert link["value_orig"] == "NaN"

    def test_empty_value_info_lists(self):
        """Test behavior with empty value and info lists."""
        net = self.create_base_net_mock()  # Default has empty value and info lists

        viz_json(net, dendro=True, links=False)

        row_node = net.viz["row_nodes"][0]
        assert "value" not in row_node
        assert "info" not in row_node


class TestVizJsonErrorHandling(TestVizJsonBase):
    """Test error handling and robustness."""

    def test_missing_parameters(self):
        """Test various missing parameter scenarios."""
        # Missing net parameter
        with pytest.raises(TypeError):
            viz_json()

        # None net parameter
        with pytest.raises(AttributeError):
            viz_json(None)

    def test_missing_attributes(self):
        """Test missing required attributes."""
        # Missing viz attribute
        net = Mock()
        net.dat = {
            "nodes": {"row": [], "col": []},
            "node_info": {"row": {"Y": np.array([])}, "col": {"Y": np.array([])}},
        }
        del net.viz

        with pytest.raises(AttributeError):
            viz_json(net)

        # Missing dat attribute
        net = Mock()
        net.viz = {"linkage": {}, "row_nodes": [], "col_nodes": [], "links": [], "mat": []}
        del net.dat

        with pytest.raises(AttributeError):
            viz_json(net)

        # Missing node_info in dat
        net = Mock()
        net.viz = {"linkage": {}, "row_nodes": [], "col_nodes": [], "links": [], "mat": []}
        net.dat = {"nodes": {"row": [], "col": []}}  # Missing node_info

        with pytest.raises(KeyError):
            viz_json(net)

    def test_malformed_node_info(self):
        """Test with malformed node_info structure."""
        # Create mock directly without using base mock to avoid deep merge issues
        net = Mock()

        net.viz = {"linkage": {}, "row_nodes": [], "col_nodes": [], "links": [], "mat": []}

        net.dat = {
            "nodes": {"row": ["gene1"], "col": ["sample1"]},
            "node_info": {
                "row": {
                    "Y": np.array([[1]]),
                    # Missing required keys like 'ini', 'clust', 'rank'
                    # Only have 'value' and 'info'
                    "value": [],
                    "info": [],
                },
                "col": {
                    "Y": np.array([[2]]),
                    "ini": [0],
                    "clust": [0],
                    "rank": [0],
                    "value": [],
                    "info": [],
                },
            },
            "mat": np.array([[1.0]]),
        }

        # Should raise KeyError for missing 'ini' key in row node_info
        with pytest.raises(KeyError):
            viz_json(net)

    def test_mismatched_data_lengths(self):
        """Test behavior with mismatched data lengths."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": ["gene1", "gene2"]},  # 2 nodes
                "node_info": {
                    "row": {
                        "Y": np.array([[1, 2]]),
                        "ini": [0],  # Only 1 element, but 2 nodes
                        "clust": [0, 1],
                        "rank": [0, 1],
                    }
                },
            }
        )

        with pytest.raises(IndexError):
            viz_json(net)


class TestVizJsonBugReproduction(TestVizJsonBase):
    """Test cases that reproduce specific bugs identified in analysis."""

    def test_value_orig_bug(self):
        """Test the value_orig logic bug in links mode."""
        net = self.create_base_net_mock(dat={"mat": np.array([[np.nan]])})

        # Reduce to single cell for simplicity
        net.dat["nodes"]["row"] = ["gene1"]
        net.dat["nodes"]["col"] = ["sample1"]
        for axis in ["row", "col"]:
            for key in net.dat["node_info"][axis]:
                if isinstance(net.dat["node_info"][axis][key], list):
                    net.dat["node_info"][axis][key] = net.dat["node_info"][axis][key][:1]

        viz_json(net, dendro=True, links=True)

        link = net.viz["links"][0]
        # Bug: value_orig is never set before the check, but gets set when NaN is detected
        assert np.isnan(link["value"])
        assert "value_orig" in link
        assert link["value_orig"] == "NaN"

    def test_category_name_replacement(self):
        """Test category name replacement logic with dashes."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": ["gene1"], "col": ["sample1"]},
                "node_info": {
                    "row": {
                        "Y": np.array([[1]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": [],
                        "info": [],
                        "cat-0": ["category-with-dashes"],
                        "pval_cat_0": {"category-with-dashes": 0.01},
                        "cat_0_index": [0],
                    },
                    "col": {
                        "Y": np.array([[2]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": [],
                        "info": [],
                    },
                },
                "mat": np.array([[1.0]]),
            }
        )

        viz_json(net, dendro=True, links=False)

        row_node = net.viz["row_nodes"][0]
        assert row_node["cat-0"] == "category-with-dashes"
        assert "cat_0_pval" in row_node
        assert row_node["cat_0_pval"] == 0.01

    def test_missing_pval_data(self):
        """Test handling when p-value data is missing for categories."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": ["gene1"], "col": ["sample1"]},
                "node_info": {
                    "row": {
                        "Y": np.array([[1]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": [],
                        "info": [],
                        "cat-0": ["typeA"],
                        # Missing pval_cat_0 - should not crash
                        "cat_0_index": [0],
                    },
                    "col": {
                        "Y": np.array([[2]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": [],
                        "info": [],
                    },
                },
                "mat": np.array([[1.0]]),
            }
        )

        viz_json(net, dendro=True, links=False)

        row_node = net.viz["row_nodes"][0]
        assert row_node["cat-0"] == "typeA"
        assert "cat_0_pval" not in row_node  # Should not be present

    def test_performance_issue_demonstration(self):
        """Test that demonstrates the O(n²) performance issue with clust.index()."""
        # Create scenario where clust.index() calls are expensive
        n_nodes = 10
        clust_list = list(range(n_nodes))

        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": [f"gene_{i}" for i in range(n_nodes)], "col": ["sample_1"]},
                "node_info": {
                    "row": {
                        "Y": np.array([list(range(n_nodes))]),
                        "ini": list(range(n_nodes)),
                        "clust": clust_list,  # This causes O(n²) with .index() calls
                        "rank": list(range(n_nodes)),
                        "value": [],
                        "info": [],
                    }
                },
                "mat": np.random.rand(n_nodes, 1),
            }
        )

        viz_json(net, dendro=True, links=False)

        # Verify clust values were computed (even if inefficiently)
        for i, node in enumerate(net.viz["row_nodes"]):
            assert node["clust"] == i


class TestVizJsonIntegration(TestVizJsonBase):
    """Integration tests combining multiple features."""

    def test_full_featured_network(self):
        """Test with a comprehensive network object."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": ["GENE1", "GENE2", "GENE3"], "col": ["SAMPLE1", "SAMPLE2"]},
                "node_info": {
                    "row": {
                        "Y": np.array([[0.5, 1.0, 1.5], [2.0, 2.5, 3.0]]),
                        "ini": [0, 1, 2],
                        "clust": [0, 1, 2],
                        "rank": [2, 1, 0],
                        "rankvar": [0.1, 0.5, 0.9],
                        "value": ["high", "medium", "low"],
                        "info": ["protein_coding", "lncRNA", "miRNA"],
                        "cat-0": ["pathway_A", "pathway_B", "pathway_A"],
                        "cat-1": ["chr1", "chr2", "chr1"],
                        "pval_cat_0": {"pathway_A": 0.001, "pathway_B": 0.05},
                        "cat_0_index": [0, 1, 0],
                        "cat_1_index": [0, 1, 0],
                    },
                    "col": {
                        "Y": np.array([[1.0, 2.0]]),
                        "ini": [0, 1],
                        "clust": [0, 1],
                        "rank": [1, 0],
                        "value": ["ctrl", "treat"],
                        "info": ["control", "treatment"],
                        "cat-0": ["batch1", "batch2"],
                        "cat_0_index": [0, 1],
                    },
                },
                "mat": np.random.rand(3, 2),
            }
        )

        viz_json(net, dendro=True, links=False)

        self.assert_basic_structure(net, expected_rows=3, expected_cols=2)

        # Check comprehensive row node features
        row_node = net.viz["row_nodes"][0]
        expected_keys = [
            "name",
            "ini",
            "clust",
            "rank",
            "rankvar",
            "value",
            "info",
            "cat-0",
            "cat-1",
            "cat_0_pval",
            "cat_0_index",
            "cat_1_index",
        ]
        for key in expected_keys:
            assert key in row_node

        assert row_node["name"] == "GENE1"
        assert row_node["cat_0_pval"] == 0.001  # pathway_A p-value

    def test_matrix_vs_links_consistency(self):
        """Test that matrix and links modes produce consistent data."""
        net = self.create_base_net_mock()
        test_matrix = net.dat["mat"].copy()

        # Test matrix mode
        viz_json(net, links=False)
        matrix_result = net.viz["mat"]

        # Reset and test links mode
        net.viz["links"] = []
        net.viz["mat"] = []
        viz_json(net, links=True)
        links_result = net.viz["links"]

        # Verify consistency
        assert len(links_result) == 4  # 2x2 matrix

        # Reconstruct matrix from links
        reconstructed = np.zeros((2, 2))
        for link in links_result:
            reconstructed[link["source"], link["target"]] = link["value"]

        np.testing.assert_array_equal(reconstructed, test_matrix)
        assert matrix_result == test_matrix.tolist()

    def test_various_data_types(self):
        """Test with various data types (unicode, numbers, etc.)."""
        net = self.create_base_net_mock(
            dat={
                "nodes": {"row": ["gene_α", "gene_β"], "col": ["sample_γ"]},
                "node_info": {
                    "row": {
                        "Y": np.array([[1, 2]]),
                        "ini": [0, 1],
                        "clust": [0, 1],
                        "rank": [0, 1],
                        "value": ["δ_value", "ε_value"],
                        "info": ["ζ_info", "η_info"],
                        "cat-0": ["Category with spaces", "Category_123"],
                        "cat-1": [42, 3.14],  # Numeric categories
                        "cat_0_index": [0, 1],
                        "cat_1_index": [0, 1],
                    },
                    "col": {
                        "Y": np.array([[2]]),
                        "ini": [0],
                        "clust": [0],
                        "rank": [0],
                        "value": ["κ_value"],
                        "info": ["λ_info"],
                    },
                },
                "mat": np.array([[1.0], [2.0]]),
            }
        )

        viz_json(net, dendro=True, links=False)

        # Check unicode and complex data handling
        row_node_0 = net.viz["row_nodes"][0]
        assert row_node_0["name"] == "gene_α"
        assert row_node_0["value"] == "δ_value"
        assert row_node_0["cat-0"] == "Category with spaces"
        assert row_node_0["cat-1"] == 42

        col_node_0 = net.viz["col_nodes"][0]
        assert col_node_0["name"] == "sample_γ"
        assert col_node_0["value"] == "κ_value"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
