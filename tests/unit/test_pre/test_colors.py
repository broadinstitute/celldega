"""Cluster palettes are a deterministic, hue-evenly-spaced set of hex colours with one
entry per cluster, in the order the clusters were given.

The one content-dependent rule: any cluster whose name contains ``Blank`` -- the
negative-control probes of a Xenium/MERSCOPE panel -- is forced to white so it disappears
against the landscape background, while still consuming its slot in the hue wheel.

``_hsv_to_hex`` is byte-identical to the private copy at ``celldega/viz/widget.py``; this
file pins the ``pre`` copy only.
"""

import pytest

from celldega.pre.colors import _create_cluster_colors, _hsv_to_hex


_HEX_DIGITS = set("0123456789abcdef")


def _clusters(n: int) -> list[str]:
    return [f"cluster_{i}" for i in range(n)]


# --- _hsv_to_hex ------------------------------------------------------------


@pytest.mark.parametrize("hue", [0.0, 0.125, 1 / 3, 0.5, 0.875, 1.0])
def test_hsv_to_hex_returns_a_seven_char_lowercase_hex_string(hue: float) -> None:
    value = _hsv_to_hex(hue)

    assert len(value) == 7
    assert value.startswith("#")
    assert set(value[1:]) <= _HEX_DIGITS


def test_hsv_to_hex_is_deterministic_for_a_given_hue() -> None:
    assert _hsv_to_hex(0.42) == _hsv_to_hex(0.42)
    # Pinned literals: saturation 0.65 / value 0.9 are baked into the function, so
    # these change only if the palette itself is deliberately changed.
    assert _hsv_to_hex(0.0) == "#e55050"
    assert _hsv_to_hex(1 / 3) == "#50e550"


def test_hsv_to_hex_separates_distinct_hues() -> None:
    values = [_hsv_to_hex(i / 6) for i in range(6)]

    assert len(set(values)) == 6


def test_hsv_to_hex_wraps_at_the_top_of_the_hue_wheel() -> None:
    assert _hsv_to_hex(1.0) == _hsv_to_hex(0.0)


# --- _create_cluster_colors -------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 5, 40])
def test_one_colour_per_cluster(n: int) -> None:
    colors = _create_cluster_colors(_clusters(n))

    assert len(colors) == n
    assert all(len(c) == 7 and c.startswith("#") for c in colors)


def test_single_cluster_gets_hue_zero() -> None:
    # n == 1 means the only hue sampled is 0/1; guards the division by n.
    assert _create_cluster_colors(["solo"]) == [_hsv_to_hex(0.0)]


def test_distinct_clusters_get_distinct_colours() -> None:
    colors = _create_cluster_colors(_clusters(8))

    assert len(set(colors)) == 8


def test_blank_clusters_are_white_and_others_are_not() -> None:
    colors = _create_cluster_colors(["a", "Blank-1", "b", "BlankCodeword_0042"])

    assert colors[1] == "#FFFFFF"
    assert colors[3] == "#FFFFFF"
    assert colors[0] != "#FFFFFF"
    assert colors[2] != "#FFFFFF"
    assert colors[0] != colors[2]


def test_blank_cluster_still_consumes_its_hue_slot() -> None:
    """The palette is indexed positionally, so whitening a Blank does not shift the
    colours of the clusters after it."""
    without_blank = _create_cluster_colors(["a", "b", "c"])
    with_blank = _create_cluster_colors(["a", "Blank-1", "c"])

    assert with_blank == [without_blank[0], "#FFFFFF", without_blank[2]]


def test_blank_match_is_case_sensitive_and_substring_based() -> None:
    colors = _create_cluster_colors(["blank", "NegControl_Blank", "Blankety"])

    assert colors[0] != "#FFFFFF"  # lowercase "blank" is not matched
    assert colors[1] == "#FFFFFF"
    assert colors[2] == "#FFFFFF"


def test_all_blank_clusters_collapse_to_white() -> None:
    colors = _create_cluster_colors(["Blank-1", "Blank-2"])

    assert colors == ["#FFFFFF", "#FFFFFF"]


def test_empty_cluster_list_returns_empty_palette() -> None:
    # n == 0 would be a ZeroDivisionError if the hue were computed eagerly; the
    # comprehension over range(0) means it is not.
    assert _create_cluster_colors([]) == []
