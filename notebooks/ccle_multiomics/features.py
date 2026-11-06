"""Stable display identifiers for feature-stacked CCLE assays."""

from __future__ import annotations


MODALITY_SUFFIX_SEPARATOR = "::"


def stacked_feature_id(feature_id: object, modality: str) -> str:
    """Make a unique, human-readable ID without obscuring the feature name.

    ``CDH1::rna`` remains recognizable to people and can be parsed by the
    JavaScript UI before it makes a UniProt query. A double colon is safe for
    CCLE's metabolite labels, which often already contain a single colon (for
    example, ``C38:5 PC``).
    """
    if not modality or MODALITY_SUFFIX_SEPARATOR in modality:
        raise ValueError("modality must be a nonempty label without '::'")
    return f"{feature_id}{MODALITY_SUFFIX_SEPARATOR}{modality}"


def split_stacked_feature_id(display_id: object) -> tuple[str, str | None]:
    """Return ``(original_feature_id, modality)`` from a stacked display ID."""
    value = str(display_id)
    if MODALITY_SUFFIX_SEPARATOR not in value:
        return value, None
    feature_id, modality = value.rsplit(MODALITY_SUFFIX_SEPARATOR, maxsplit=1)
    return feature_id, modality or None
