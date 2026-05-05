"""Selection/query layer for AnnData-backed entities.

The :mod:`celldega.select` module separates three related ideas:

- attributes, such as ``adata.obs`` columns or gene expression vectors;
- queries, such as "B cells from samples S1 or S2";
- samplers/rankers, such as random sampling or high-expression quantile bins.

The main entry point is :class:`Selector`, which evaluates these expressions
against one AnnData object and returns a :class:`Selection`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral
from typing import Any, Literal, Protocol
import warnings

import numpy as np
import pandas as pd


QueryOp = Literal[
    "eq",
    "ne",
    "lt",
    "le",
    "gt",
    "ge",
    "isin",
    "notin",
    "isna",
    "notna",
    "between",
]
BooleanOp = Literal["and", "or", "not"]
QuantileBin = Literal["low", "mid", "high"]
RankDirection = Literal["high", "low"]


def _json_value(value: Any) -> Any:
    """Convert common scientific Python values to JSON-friendly objects."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, tuple | list):
        return [_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if value is None or value is pd.NA:
        return None
    if not isinstance(value, Sequence):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def _as_1d_array(matrix: Any) -> np.ndarray:
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    elif hasattr(matrix, "todense"):
        matrix = matrix.todense()
    return np.asarray(matrix).reshape(-1)


def _validate_count(n: int | None, name: str = "n") -> None:
    if n is not None and n < 0:
        raise ValueError(f"{name} must be non-negative")


def _stable_scores_dict(scores: pd.Series | None) -> dict[str, float] | None:
    if scores is None:
        return None
    return {str(index): float(value) for index, value in scores.items()}


class Query:
    """Base class for boolean query expressions.

    Query objects are usually created by comparing attributes returned by
    :meth:`Selector.attr` or :meth:`Selector.gene`.
    """

    def evaluate(self, selector: Selector) -> pd.Series:
        """Evaluate this query against a selector and return a boolean mask."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation of this query."""
        raise NotImplementedError

    def __and__(self, other: Query) -> Query:
        return BooleanQuery("and", (self, _coerce_query(other)))

    def __or__(self, other: Query) -> Query:
        return BooleanQuery("or", (self, _coerce_query(other)))

    def __invert__(self) -> Query:
        return BooleanQuery("not", (self,))


def _coerce_query(value: Any) -> Query:
    if not isinstance(value, Query):
        raise TypeError("Can only combine celldega.select query expressions")
    return value


@dataclass(frozen=True, eq=False)
class Attribute:
    """Reference to an AnnData-backed attribute.

    Attributes are lazy references. They become concrete values only when a
    query or sampler is evaluated by a :class:`Selector`.

    Attributes are usually created through :meth:`Selector.attr` or
    :meth:`Selector.gene` rather than instantiated directly.
    """

    kind: Literal["obs", "gene"]
    name: str
    layer: str | None = None
    raw: bool = False

    def evaluate(self, selector: Selector) -> pd.Series:
        """Return this attribute as a Series aligned to ``selector.ids``."""
        if self.kind == "obs":
            return selector._obs_attribute(self.name)
        if self.kind == "gene":
            return selector._gene_attribute(self.name, layer=self.layer, raw=self.raw)
        raise ValueError(f"Unknown attribute kind: {self.kind}")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.kind, "name": self.name}
        if self.layer is not None:
            result["layer"] = self.layer
        if self.raw:
            result["raw"] = True
        return result

    def isin(self, values: Sequence[Any]) -> Query:
        """Match values contained in ``values``."""
        return PredicateQuery("isin", self, tuple(values))

    def notin(self, values: Sequence[Any]) -> Query:
        """Match values not contained in ``values``."""
        return PredicateQuery("notin", self, tuple(values))

    def isna(self) -> Query:
        """Match missing values."""
        return PredicateQuery("isna", self)

    def notna(self) -> Query:
        """Match non-missing values."""
        return PredicateQuery("notna", self)

    def between(
        self,
        left: Any,
        right: Any,
        inclusive: Literal["both", "neither", "left", "right"] = "both",
    ) -> Query:
        """Match values between ``left`` and ``right``."""
        return PredicateQuery("between", self, (left, right), {"inclusive": inclusive})

    def __eq__(self, other: Any) -> Query:  # type: ignore[override]
        return PredicateQuery("eq", self, other)

    def __ne__(self, other: Any) -> Query:  # type: ignore[override]
        return PredicateQuery("ne", self, other)

    def __lt__(self, other: Any) -> Query:
        return PredicateQuery("lt", self, other)

    def __le__(self, other: Any) -> Query:
        return PredicateQuery("le", self, other)

    def __gt__(self, other: Any) -> Query:
        return PredicateQuery("gt", self, other)

    def __ge__(self, other: Any) -> Query:
        return PredicateQuery("ge", self, other)


@dataclass(frozen=True)
class PredicateQuery(Query):
    op: QueryOp
    attr: Attribute
    value: Any = None
    options: dict[str, Any] | None = None

    def evaluate(self, selector: Selector) -> pd.Series:
        values = self.attr.evaluate(selector)

        if self.op == "eq":
            mask = values == self.value
        elif self.op == "ne":
            mask = values != self.value
        elif self.op == "lt":
            mask = values < self.value
        elif self.op == "le":
            mask = values <= self.value
        elif self.op == "gt":
            mask = values > self.value
        elif self.op == "ge":
            mask = values >= self.value
        elif self.op == "isin":
            mask = values.isin(self.value)
        elif self.op == "notin":
            mask = ~values.isin(self.value)
        elif self.op == "isna":
            mask = values.isna()
        elif self.op == "notna":
            mask = values.notna()
        elif self.op == "between":
            left, right = self.value
            inclusive = (self.options or {}).get("inclusive", "both")
            mask = values.between(left, right, inclusive=inclusive)
        else:
            raise ValueError(f"Unsupported query operation: {self.op}")

        return pd.Series(mask, index=values.index).fillna(False).astype(bool)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "op": self.op,
            "attr": self.attr.to_dict(),
        }
        if self.op not in {"isna", "notna"}:
            result["value"] = _json_value(self.value)
        if self.options:
            result["options"] = _json_value(self.options)
        return result


@dataclass(frozen=True)
class BooleanQuery(Query):
    op: BooleanOp
    queries: tuple[Query, ...]

    def evaluate(self, selector: Selector) -> pd.Series:
        if self.op == "not":
            if len(self.queries) != 1:
                raise ValueError("NOT queries must contain exactly one child query")
            return ~self.queries[0].evaluate(selector)

        if len(self.queries) < 2:
            raise ValueError(f"{self.op.upper()} queries must contain at least two child queries")

        masks = [query.evaluate(selector) for query in self.queries]
        result = masks[0]
        for mask in masks[1:]:
            if self.op == "and":
                result = result & mask
            elif self.op == "or":
                result = result | mask
            else:
                raise ValueError(f"Unsupported boolean operation: {self.op}")
        return result.fillna(False).astype(bool)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "queries": [query.to_dict() for query in self.queries],
        }


@dataclass(frozen=True)
class Selection:
    """Ordered ids selected from a :class:`Selector`.

    ``Selection`` is the object returned by :meth:`Selector.select`. It stores
    stable ordered ids plus the query, sampler, scores, and provenance used to
    create that order. It is intentionally list-like, so it can be iterated,
    indexed, and passed to consumers such as :class:`celldega.viz.Yearbook`.

    Attributes
    ----------
    ids
        Ordered selected entity ids. For AnnData objects these are usually
        names from ``adata.obs_names``.
    query
        JSON-ready query representation, or ``None`` when no query was used.
    sampler
        JSON-ready sampler representation, or ``None`` when ids were returned in
        source order.
    candidate_count
        Number of entities matching the query before sampling.
    selected_count
        Number of ids returned in :attr:`ids`.
    provenance
        Execution metadata, including source AnnData shape and sampler details.
    scores
        Optional score values keyed by selected id. Ranking samplers, such as
        quantile-bin gene selection, may populate this.
    """

    ids: list[str]
    query: dict[str, Any] | None
    sampler: dict[str, Any] | None
    candidate_count: int
    selected_count: int
    provenance: dict[str, Any]
    scores: dict[str, float] | None = None

    def __iter__(self):
        return iter(self.ids)

    def __len__(self) -> int:
        return len(self.ids)

    def __getitem__(self, index):
        return self.ids[index]

    def names(self) -> list[str]:
        """Return selected entity names in stable result order.

        This is the most direct way to pass a selection to code that expects a
        plain list of ids.
        """
        return list(self.ids)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the selection.

        This is an alias for :meth:`to_json`.
        """
        return self.to_json()

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-ready object including query, sampler, and provenance."""
        result = {
            "ids": self.ids,
            "query": self.query,
            "sampler": self.sampler,
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "provenance": _json_value(self.provenance),
        }
        if self.scores is not None:
            result["scores"] = self.scores
        return result

    def to_frame(self) -> pd.DataFrame:
        """Return selected ids as a ranking DataFrame.

        This is an alias for :meth:`to_dataframe`.
        """
        return self.to_dataframe()

    def to_dataframe(self) -> pd.DataFrame:
        """Return selected ids as a ranking DataFrame.

        The returned frame always contains ``id`` and zero-based ``rank``
        columns. If the sampler produced scores, a ``score`` column is included.
        """
        frame = pd.DataFrame({"id": self.ids, "rank": np.arange(len(self.ids))})
        if self.scores is not None:
            frame["score"] = [self.scores.get(inst_id) for inst_id in self.ids]
        return frame

    def page(self, page: int, per_page: int) -> list[str]:
        """Return one zero-based page of ids.

        Parameters
        ----------
        page
            Zero-based page index.
        per_page
            Number of ids to return.
        """
        _validate_count(page, "page")
        if per_page <= 0:
            raise ValueError("per_page must be positive")
        start = page * per_page
        return self.ids[start : start + per_page]


@dataclass(frozen=True)
class SamplingResult:
    ids: list[str]
    scores: pd.Series | None
    provenance: dict[str, Any]


class Sampler(Protocol):
    """Protocol implemented by sampler/ranker objects."""

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        """Select and order ids from the candidate ids."""

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable sampler description."""


@dataclass(frozen=True)
class RandomSampler:
    """Randomly order or sample candidate ids.

    Parameters
    ----------
    n
        Number of ids to return. If ``None``, all candidate ids are shuffled.
    seed
        Optional random seed for reproducible selections.
    replace
        Whether ids may be sampled more than once.
    """

    n: int | None = None
    seed: int | None = None
    replace: bool = False

    def __post_init__(self) -> None:
        _validate_count(self.n)

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        del selector
        count = len(candidate_ids) if self.n is None else self.n
        if len(candidate_ids) == 0 or count == 0:
            return SamplingResult([], None, {"available": len(candidate_ids), "sampled": 0})

        rng = np.random.default_rng(self.seed)
        if self.replace:
            positions = rng.choice(len(candidate_ids), size=count, replace=True)
        else:
            count = min(count, len(candidate_ids))
            positions = rng.permutation(len(candidate_ids))[:count]

        ids = [str(value) for value in candidate_ids.take(positions)]
        return SamplingResult(
            ids=ids,
            scores=None,
            provenance={
                "available": len(candidate_ids),
                "sampled": len(ids),
                "seed": self.seed,
                "replace": self.replace,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "random",
            "n": self.n,
            "seed": self.seed,
            "replace": self.replace,
        }


@dataclass(frozen=True)
class QuantileBinSampler:
    """Sample ids from a low/mid/high quantile bin for an attribute.

    This sampler is useful for representative inspection, for example selecting
    high-valued entities for an attribute while preserving a stable ranked
    order in the returned selection.
    """

    attr: Attribute
    bin: QuantileBin
    n: int | None = None
    seed: int | None = None
    q_low: float = 1 / 3
    q_high: float = 2 / 3
    proportion: float | None = None
    percentile: float | None = None

    def __post_init__(self) -> None:
        _validate_count(self.n)
        if self.bin not in {"low", "mid", "high"}:
            raise ValueError("bin must be one of 'low', 'mid', or 'high'")
        if not 0 <= self.q_low <= self.q_high <= 1:
            raise ValueError("q_low and q_high must satisfy 0 <= q_low <= q_high <= 1")
        if self.proportion is not None and self.percentile is not None:
            raise ValueError("proportion and percentile are mutually exclusive")
        if self.proportion is not None and not 0 < self.proportion <= 1:
            raise ValueError("proportion must satisfy 0 < proportion <= 1")
        if self.percentile is not None and not 0 < self.percentile <= 100:
            raise ValueError("percentile must satisfy 0 < percentile <= 100")

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        values = self.attr.evaluate(selector).reindex(candidate_ids)
        numeric = pd.to_numeric(values, errors="coerce").dropna()

        if numeric.empty:
            return SamplingResult(
                ids=[],
                scores=None,
                provenance={
                    "available": len(candidate_ids),
                    "bin_available": 0,
                    "sampled": 0,
                    "reason": "attribute had no numeric values",
                },
            )

        q_low, q_high = self._selection_quantiles()
        low_cut = float(numeric.quantile(q_low))
        high_cut = float(numeric.quantile(q_high))

        if self.bin == "low":
            binned = numeric[numeric <= low_cut]
            ordered = binned.sort_values(ascending=True, kind="mergesort")
        elif self.bin == "mid":
            binned = numeric[(numeric >= low_cut) & (numeric <= high_cut)]
            median = float(numeric.median())
            ordered = binned.loc[(binned - median).abs().sort_values(kind="mergesort").index]
        else:
            binned = numeric[numeric >= high_cut]
            ordered = binned.sort_values(ascending=False, kind="mergesort")

        if self.n is not None and len(ordered) > self.n:
            rng = np.random.default_rng(self.seed)
            sampled_positions = rng.choice(len(ordered), size=self.n, replace=False)
            sampled_index = ordered.index.take(sampled_positions)
            ordered = ordered.reindex(sampled_index)
            ordered = self._sort_sampled_bin(ordered, numeric)

        ids = [str(index) for index in ordered.index]
        return SamplingResult(
            ids=ids,
            scores=ordered,
            provenance={
                "available": len(candidate_ids),
                "bin_available": len(binned),
                "sampled": len(ids),
                "q_low": q_low,
                "q_high": q_high,
                "low_cut": low_cut,
                "high_cut": high_cut,
                "seed": self.seed,
            },
        )

    def _selection_quantiles(self) -> tuple[float, float]:
        if self.proportion is not None or self.percentile is not None:
            proportion = self.proportion
            if proportion is None:
                assert self.percentile is not None
                proportion = self.percentile / 100

            if self.bin == "low":
                return proportion, proportion
            if self.bin == "high":
                cutoff = 1 - proportion
                return cutoff, cutoff

            half_width = proportion / 2
            return 0.5 - half_width, 0.5 + half_width

        return self.q_low, self.q_high

    def _sort_sampled_bin(self, values: pd.Series, all_values: pd.Series) -> pd.Series:
        if self.bin == "low":
            return values.sort_values(ascending=True, kind="mergesort")
        if self.bin == "mid":
            median = float(all_values.median())
            return values.loc[(values - median).abs().sort_values(kind="mergesort").index]
        return values.sort_values(ascending=False, kind="mergesort")

    def to_dict(self) -> dict[str, Any]:
        result = {
            "type": "quantile_bin",
            "attr": self.attr.to_dict(),
            "bin": self.bin,
            "n": self.n,
            "seed": self.seed,
            "q_low": self.q_low,
            "q_high": self.q_high,
        }
        if self.proportion is not None:
            result["proportion"] = self.proportion
        if self.percentile is not None:
            result["percentile"] = self.percentile
        return result


@dataclass(frozen=True)
class GaussianSampler:
    """Sample ids with Gaussian weighting around a numeric attribute value."""

    attr: Attribute
    center: float
    std: float
    n: int | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        _validate_count(self.n)
        if self.std <= 0:
            raise ValueError("std must be positive")

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        values = self.attr.evaluate(selector).reindex(candidate_ids)
        numeric = pd.to_numeric(values, errors="coerce").dropna()

        if numeric.empty:
            return SamplingResult(
                ids=[],
                scores=None,
                provenance={
                    "available": len(candidate_ids),
                    "weighted_available": 0,
                    "sampled": 0,
                    "reason": "attribute had no numeric values",
                },
            )

        distances = (numeric - self.center).abs()
        weights = np.exp(-0.5 * np.square((numeric - self.center) / self.std))
        weight_series = pd.Series(weights, index=numeric.index, name="weight")

        if self.n is None or self.n >= len(weight_series):
            ordered = weight_series.loc[
                distances.sort_values(ascending=True, kind="mergesort").index
            ]
        else:
            rng = np.random.default_rng(self.seed)
            probabilities = weight_series / weight_series.sum()
            sampled_positions = rng.choice(
                len(probabilities),
                size=self.n,
                replace=False,
                p=probabilities.to_numpy(),
            )
            sampled_index = probabilities.index.take(sampled_positions)
            ordered = weight_series.reindex(sampled_index)
            ordered = ordered.loc[
                distances.reindex(sampled_index).sort_values(ascending=True, kind="mergesort").index
            ]

        ids = [str(index) for index in ordered.index]
        return SamplingResult(
            ids=ids,
            scores=ordered,
            provenance={
                "available": len(candidate_ids),
                "weighted_available": len(weight_series),
                "sampled": len(ids),
                "center": self.center,
                "std": self.std,
                "seed": self.seed,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "gaussian",
            "attr": self.attr.to_dict(),
            "center": self.center,
            "std": self.std,
            "n": self.n,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class RankSampler:
    """Return the highest or lowest ids for a numeric attribute."""

    attr: Attribute
    n: int | None = None
    by: RankDirection = "high"

    def __post_init__(self) -> None:
        _validate_count(self.n)
        if self.by not in {"high", "low"}:
            raise ValueError("by must be 'high' or 'low'")

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        values = self.attr.evaluate(selector).reindex(candidate_ids)
        numeric = pd.to_numeric(values, errors="coerce").dropna()

        if numeric.empty:
            return SamplingResult(
                ids=[],
                scores=None,
                provenance={
                    "available": len(candidate_ids),
                    "rankable_available": 0,
                    "sampled": 0,
                    "reason": "attribute had no numeric values",
                },
            )

        ascending = self.by == "low"
        ordered = numeric.sort_values(ascending=ascending, kind="mergesort")
        if self.n is not None:
            ordered = ordered.iloc[: self.n]

        ids = [str(index) for index in ordered.index]
        return SamplingResult(
            ids=ids,
            scores=ordered,
            provenance={
                "available": len(candidate_ids),
                "rankable_available": len(numeric),
                "sampled": len(ids),
                "by": self.by,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "rank",
            "attr": self.attr.to_dict(),
            "n": self.n,
            "by": self.by,
        }


@dataclass(frozen=True)
class StratifiedSampler:
    """Sample evenly across categories from a categorical attribute."""

    attr: Attribute
    n_per_category: int | None = None
    n: int | None = None
    seed: int | None = None
    categories: tuple[Any, ...] | None = None

    def __post_init__(self) -> None:
        _validate_count(self.n_per_category, "n_per_category")
        _validate_count(self.n, "n")
        if self.n is None and self.n_per_category is None:
            raise ValueError("either n or n_per_category must be provided")
        if self.n is not None and self.n_per_category is not None:
            raise ValueError("n and n_per_category are mutually exclusive")

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        values = self.attr.evaluate(selector).reindex(candidate_ids)
        non_missing = values.dropna()

        if self.categories is None:
            categories = list(pd.unique(non_missing))
        else:
            categories = list(self.categories)

        rng = np.random.default_rng(self.seed)
        group_ids_by_category: dict[Any, pd.Index] = {}
        sample_counts: dict[Any, int] = {}
        selected_ids: list[str] = []
        per_category: dict[str, dict[str, Any]] = {}

        for category in categories:
            group_ids = non_missing.index[non_missing == category]
            group_ids_by_category[category] = group_ids
            sample_counts[category] = 0

        if self.n_per_category is not None:
            for category in categories:
                sample_counts[category] = min(self.n_per_category, len(group_ids_by_category[category]))
        else:
            assert self.n is not None
            remaining = self.n
            available_categories = [
                category for category in categories if len(group_ids_by_category[category]) > 0
            ]
            while remaining > 0 and available_categories:
                progressed = False
                for category in available_categories:
                    if remaining == 0:
                        break
                    if sample_counts[category] < len(group_ids_by_category[category]):
                        sample_counts[category] += 1
                        remaining -= 1
                        progressed = True
                if not progressed:
                    break
                available_categories = [
                    category
                    for category in available_categories
                    if sample_counts[category] < len(group_ids_by_category[category])
                ]

        for category in categories:
            group_ids = group_ids_by_category[category]
            available = len(group_ids)
            count = sample_counts[category]

            if count == 0:
                sampled_ids: list[str] = []
            else:
                positions = rng.permutation(available)[:count]
                sampled_ids = [str(value) for value in group_ids.take(positions)]

            selected_ids.extend(sampled_ids)
            per_category[str(category)] = {
                "value": _json_value(category),
                "available": available,
                "sampled": len(sampled_ids),
            }

        return SamplingResult(
            ids=selected_ids,
            scores=None,
            provenance={
                "available": len(candidate_ids),
                "strata": per_category,
                "sampled": len(selected_ids),
                "seed": self.seed,
                "mode": "per_category" if self.n_per_category is not None else "total",
            },
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "type": "stratified",
            "attr": self.attr.to_dict(),
            "seed": self.seed,
        }
        if self.n_per_category is not None:
            result["n_per_category"] = self.n_per_category
        if self.n is not None:
            result["n"] = self.n
        if self.categories is not None:
            result["categories"] = _json_value(list(self.categories))
        return result


class SamplerFactory:
    """Namespace for sampler constructors exposed as ``selector.samplers``."""

    def random(
        self,
        n: int | None = None,
        seed: int | None = None,
        *,
        replace: bool = False,
    ) -> RandomSampler:
        """Return a random sampler.

        Examples
        --------
        >>> selector.select(
        ...     query=selector.attr("cluster") == "B cell",
        ...     sampler=selector.samplers.random(n=24, seed=1),
        ... )
        """
        return RandomSampler(n=n, seed=seed, replace=replace)

    def quantile_bin(
        self,
        attr: Attribute,
        bin: QuantileBin,
        n: int | None = None,
        seed: int | None = None,
        *,
        q_low: float = 1 / 3,
        q_high: float = 2 / 3,
        proportion: float | None = None,
        percentile: float | None = None,
    ) -> QuantileBinSampler:
        """Return a sampler for a low/mid/high quantile bin.

        Examples
        --------
        >>> selector.select(
        ...     query=selector.attr("cluster") == "B cell",
        ...     sampler=selector.samplers.quantile_bin(
        ...         attr=selector.gene("MS4A1"),
        ...         bin="high",
        ...         n=24,
        ...         seed=1,
        ...     ),
        ... )
        """
        if not isinstance(attr, Attribute):
            raise TypeError("attr must be created by Selector.attr(...) or Selector.gene(...)")
        return QuantileBinSampler(
            attr=attr,
            bin=bin,
            n=n,
            seed=seed,
            q_low=q_low,
            q_high=q_high,
            proportion=proportion,
            percentile=percentile,
        )

    def gaussian(
        self,
        attr: Attribute,
        center: float,
        std: float,
        n: int | None = None,
        seed: int | None = None,
    ) -> GaussianSampler:
        """Return a sampler with Gaussian weighting around a numeric center."""
        if not isinstance(attr, Attribute):
            raise TypeError("attr must be created by Selector.attr(...) or Selector.gene(...)")
        return GaussianSampler(attr=attr, center=center, std=std, n=n, seed=seed)

    def rank(
        self,
        attr: Attribute,
        n: int | None = None,
        *,
        by: RankDirection = "high",
    ) -> RankSampler:
        """Return the highest or lowest ids for a numeric attribute."""
        if not isinstance(attr, Attribute):
            raise TypeError("attr must be created by Selector.attr(...) or Selector.gene(...)")
        return RankSampler(attr=attr, n=n, by=by)

    def stratified(
        self,
        attr: Attribute,
        n_per_category: int | None = None,
        n: int | None = None,
        seed: int | None = None,
        *,
        categories: Sequence[Any] | None = None,
    ) -> StratifiedSampler:
        """Return a sampler that draws evenly across categorical strata."""
        if not isinstance(attr, Attribute):
            raise TypeError("attr must be created by Selector.attr(...) or Selector.gene(...)")
        return StratifiedSampler(
            attr=attr,
            n_per_category=n_per_category,
            n=n,
            seed=seed,
            categories=None if categories is None else tuple(categories),
        )


class Selector:
    """Query and selection interface for an AnnData object.

    ``Selector`` is the public object for building and executing Celldega
    selections. A selector is bound to one AnnData object, so every query is
    validated and evaluated against that object's ``obs``, ``var_names``, ``X``,
    and optional layers. To work with multiple AnnData objects, instantiate one
    selector per object.

    Parameters
    ----------
    adata
        AnnData-like object. The first implementation selects over ``adata.obs``
        rows and can resolve metadata attributes from ``obs`` plus gene
        expression vectors from ``X`` or a named layer.
    default_preview_n
        Maximum number of ids to return when no sampler is provided and the
        candidate set is larger than this value. Set to ``None`` to disable the
        preview guard.
    default_preview_seed
        Seed used for the deterministic random preview when ``default_preview_n``
        is triggered.

    Examples
    --------
    >>> selector = dega.select.Selector(adata)
    >>> query = (
    ...     (selector.attr("cluster") == "B cell")
    ...     & selector.attr("sample_id").isin(["S1", "S2"])
    ... )
    >>> selection = selector.select(
    ...     query=query,
    ...     sampler=selector.samplers.quantile_bin(
    ...         attr=selector.gene("MS4A1"),
    ...         bin="high",
    ...         n=24,
    ...         seed=1,
    ...     ),
    ... )
    >>> selection.names()
    """

    def __init__(
        self,
        adata: Any,
        *,
        default_preview_n: int | None = 1000,
        default_preview_seed: int = 0,
    ):
        if not hasattr(adata, "obs") or not hasattr(adata, "obs_names"):
            raise TypeError("Selector requires an AnnData-like object with obs and obs_names")
        if default_preview_n is not None and default_preview_n <= 0:
            raise ValueError("default_preview_n must be positive or None")

        self.adata = adata
        self.samplers = SamplerFactory()
        self.default_preview_n = default_preview_n
        self.default_preview_seed = default_preview_seed

    @property
    def ids(self) -> pd.Index:
        """Entity ids available to this selector."""
        return pd.Index(self.adata.obs_names)

    def attr(self, name: str) -> Attribute:
        """Reference a per-entity metadata attribute from ``adata.obs``.

        The attribute name is validated when a query or sampler using it is
        executed. Missing columns raise ``KeyError``.
        """
        return Attribute("obs", name)

    def gene(self, name: str, *, layer: str | None = None, raw: bool = False) -> Attribute:
        """Reference a gene expression vector by gene name.

        Parameters
        ----------
        name
            Gene name in ``adata.var_names``.
        layer
            Optional layer name to use instead of ``adata.X``.
        raw
            If ``True``, use ``adata.raw``.

        Notes
        -----
        Gene and layer names are validated when the attribute is evaluated.
        Missing genes or layers raise ``KeyError``.
        """
        return Attribute("gene", name, layer=layer, raw=raw)

    def select(
        self,
        query: Query | None = None,
        sampler: Sampler | Literal["all"] | int | None = None,
    ) -> Selection:
        """Evaluate a query and optionally sample/rank the matching ids.

        Parameters
        ----------
        query
            Boolean query expression built from :meth:`attr`, :meth:`gene`, and
            boolean operators. If omitted, every AnnData observation is a
            candidate.
        sampler
            Optional sampler/ranker from ``selector.samplers``. Passing an
            integer is shorthand for a deterministic random sampler returning
            that many ids. If omitted and the candidate set is larger than
            ``default_preview_n``, a deterministic random preview is returned
            with a warning. Use ``sampler="all"`` to intentionally return every
            matching id.

        Returns
        -------
        Selection
            Stable ordered selected ids plus JSON-ready query, sampler, scores,
            and provenance.
        """
        candidate_ids = self._candidate_ids(query)
        query_dict = query.to_dict() if query is not None else None

        if sampler is None and self._should_preview(candidate_ids):
            selected_ids, sampler_dict, scores, sampler_provenance = self._preview_selection(
                candidate_ids
            )
        elif sampler is None:
            selected_ids = [str(index) for index in candidate_ids]
            sampler_dict = None
            scores = None
            sampler_provenance = {"type": "identity", "sampled": len(selected_ids)}
        elif isinstance(sampler, bool):
            raise ValueError(
                "sampler must be 'all', None, an integer count, or a sampler from selector.samplers"
            )
        elif isinstance(sampler, Integral):
            random_sampler = RandomSampler(n=int(sampler), seed=self.default_preview_seed)
            sampled = random_sampler.apply(self, candidate_ids)
            selected_ids = sampled.ids
            sampler_dict = random_sampler.to_dict()
            scores = None
            sampler_provenance = {
                **sampled.provenance,
                "type": "random",
                "shorthand": "integer",
            }
        elif sampler == "all":
            selected_ids = [str(index) for index in candidate_ids]
            sampler_dict = {"type": "all"}
            scores = None
            sampler_provenance = {"type": "all", "sampled": len(selected_ids)}
        else:
            if isinstance(sampler, str):
                raise ValueError(
                    "sampler must be 'all', None, an integer count, or a sampler "
                    "from selector.samplers"
                )
            sampled = sampler.apply(self, candidate_ids)
            selected_ids = sampled.ids
            sampler_dict = sampler.to_dict()
            scores = _stable_scores_dict(sampled.scores)
            sampler_provenance = sampled.provenance

        provenance = {
            "source": "AnnData.obs",
            "n_obs": int(self.adata.n_obs),
            "n_vars": int(self.adata.n_vars),
            "candidate_count": len(candidate_ids),
            "selected_count": len(selected_ids),
            "sampler": sampler_provenance,
        }

        return Selection(
            ids=selected_ids,
            query=query_dict,
            sampler=sampler_dict,
            candidate_count=len(candidate_ids),
            selected_count=len(selected_ids),
            provenance=provenance,
            scores=scores,
        )

    def _should_preview(self, candidate_ids: pd.Index) -> bool:
        return self.default_preview_n is not None and len(candidate_ids) > self.default_preview_n

    def _preview_selection(
        self,
        candidate_ids: pd.Index,
    ) -> tuple[list[str], dict[str, Any], None, dict[str, Any]]:
        assert self.default_preview_n is not None
        preview_n = self.default_preview_n
        warnings.warn(
            (
                f"Query matched {len(candidate_ids):,} entities. Returning a deterministic "
                f"random preview of {preview_n:,} ids because no sampler "
                "was provided. Use sampler='all' to return all matches, pass "
                "an integer count such as sampler=3000, or pass selector.samplers.* "
                "for explicit sampling."
            ),
            UserWarning,
            stacklevel=3,
        )

        preview_sampler = RandomSampler(n=preview_n, seed=self.default_preview_seed)
        sampled = preview_sampler.apply(self, candidate_ids)
        selected_ids = sampled.ids
        sampler_dict = {
            "type": "default_random_preview",
            "n": preview_n,
            "seed": self.default_preview_seed,
        }
        sampler_provenance = {
            **sampled.provenance,
            "type": "default_random_preview",
            "reason": "no sampler provided",
        }
        return selected_ids, sampler_dict, None, sampler_provenance

    def _candidate_ids(self, query: Query | None) -> pd.Index:
        if query is None:
            return self.ids

        mask = query.evaluate(self).reindex(self.ids, fill_value=False)
        return self.ids[mask.to_numpy(dtype=bool)]

    def _obs_attribute(self, name: str) -> pd.Series:
        if name not in self.adata.obs.columns:
            raise KeyError(f"Attribute '{name}' not found in adata.obs")
        return pd.Series(self.adata.obs[name], index=self.ids, name=name)

    def _gene_attribute(
        self, name: str, *, layer: str | None = None, raw: bool = False
    ) -> pd.Series:
        data = self.adata.raw if raw else self.adata
        if data is None:
            raise ValueError("adata.raw is not available")
        if name not in data.var_names:
            raise KeyError(f"Gene '{name}' not found in adata.var_names")

        if raw:
            matrix = data[:, name].X
        elif layer is None:
            matrix = self.adata[:, name].X
        else:
            if layer not in self.adata.layers:
                raise KeyError(f"Layer '{layer}' not found in adata.layers")
            matrix = self.adata[:, name].layers[layer]

        return pd.Series(_as_1d_array(matrix), index=self.ids, name=name)
