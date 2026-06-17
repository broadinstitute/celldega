"""Selection/query layer for AnnData-backed entities.

The :mod:`celldega.select` module separates three related ideas:

- attributes, such as ``adata.obs`` columns or gene expression vectors;
- queries, such as "B cells from samples S1 or S2";
- samplers/rankers, such as random sampling or high-expression quantile bins.

The main entry point is :class:`Selector`, which evaluates these expressions
against one AnnData object and returns a :class:`Selection`.

Pipeline
--------
A selection flows through four composable stages, each of which is independently
serializable so the whole result can be reproduced or shipped to a frontend as
JSON::

    selector.attr("x") / selector.gene("G")   -> Attribute   (lazy value reference)
    Attribute compared with ==, .isin(), & |  -> Query        (boolean expression)
    selector.select(query, sampler)           -> Selector     (orchestrator)
        query.evaluate -> candidate ids       -> pd.Index
        sampler.apply(candidate_ids)          -> SamplingResult (ordered ids + scores)
                                              -> Selection    (ordered ids + provenance)

Design notes
------------
- **Lazy attributes.** :class:`Attribute` objects are plain references; they
  resolve to concrete values only when a :class:`Selector` evaluates them, so a
  query can be built before its AnnData even exists.
- **Axis-agnostic core.** :class:`Query` and the samplers operate on a
  ``pd.Series`` / ``pd.Index`` keyed by the entity axis and do not care what the
  entities are. The current :class:`Selector` binds that axis to
  ``adata.obs_names`` (cells), but the same machinery generalizes to other axes.
- **Everything serializes.** Queries, samplers, and selections all expose
  ``to_dict`` / ``to_json``, and provenance is coerced to JSON-friendly types via
  :func:`_json_value`. Entity ids are stringified at the boundary so they survive
  the Python -> JSON -> JavaScript round-trip used by widgets such as
  :class:`celldega.viz.Yearbook`.
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
    """Convert common scientific Python values to JSON-friendly objects.

    Provenance and serialized queries routinely contain numpy scalars,
    timestamps, and pandas missing values, none of which the ``json`` module
    handles natively. This helper recursively normalizes them:

    - numpy scalars (``np.generic``) become native Python scalars via ``.item()``;
    - ``pd.Timestamp`` becomes an ISO-8601 string;
    - tuples and lists are converted element-wise (tuples become lists, since
      JSON has no tuple type);
    - dict keys are stringified and values converted recursively;
    - ``None``, ``pd.NA``, and other missing scalars become ``None``.

    Anything already JSON-native is returned unchanged. The ``pd.isna`` check is
    guarded because it raises on array-like inputs, which should pass through.
    """
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
    """Flatten a (possibly sparse) single-gene expression slice to a 1-D array.

    Slicing an AnnData by one gene yields an ``n_obs x 1`` matrix that may be a
    scipy sparse matrix, a ``np.matrix``, or a dense array. This densifies sparse
    inputs (``toarray``/``todense``) and reshapes to a flat vector aligned with
    the observation axis. It is the single place gene expression is materialized,
    so backend-specific handling stays contained here.
    """
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    elif hasattr(matrix, "todense"):
        matrix = matrix.todense()
    return np.asarray(matrix).reshape(-1)


def _validate_count(n: int | None, name: str = "n") -> None:
    """Raise ``ValueError`` if a count argument is negative.

    ``None`` is allowed (it means "no limit" for most samplers); only an explicit
    negative value is rejected. ``name`` is used in the message so callers can
    report the offending argument (e.g. ``"n_per_category"``).
    """
    if n is not None and n < 0:
        raise ValueError(f"{name} must be non-negative")


def _stable_scores_dict(scores: pd.Series | None) -> dict[str, float] | None:
    """Convert a per-id score Series into a JSON-stable ``{id: score}`` dict.

    Keys (entity ids) are stringified and values are coerced to native ``float``.
    Both are required for a stable JSON object: JSON keys must be strings, and a
    raw ``numpy.float64`` is not JSON-serializable. Returns ``None`` for a
    ``None`` input so samplers that produce no scores propagate cleanly.

    Note that stringified keys collide if two ids map to the same string; the
    :class:`Selector` guards against this by rejecting duplicate ``obs_names``.
    """
    if scores is None:
        return None
    return {str(index): float(value) for index, value in scores.items()}


class Query:
    """Base class for boolean query expressions.

    A query is a small, immutable expression tree. Leaves are
    :class:`PredicateQuery` nodes (one comparison on one attribute) and internal
    nodes are :class:`BooleanQuery` combinators. Query objects are normally
    created by comparing attributes from :meth:`Selector.attr` or
    :meth:`Selector.gene` rather than constructed directly, and combined with the
    Python boolean operators below::

        (selector.attr("cluster") == "B cell") & selector.gene("MS4A1") > 2

    Evaluation is deferred: a query holds no data until :meth:`evaluate` runs it
    against a :class:`Selector`.
    """

    def evaluate(self, selector: Selector) -> pd.Series:
        """Evaluate this query against ``selector`` and return a boolean mask.

        The returned ``pd.Series`` is indexed by the selector's entity ids, with
        ``True`` for entities that match. Subclasses implement the actual logic.
        """
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of this query expression."""
        raise NotImplementedError

    def __and__(self, other: Query) -> Query:
        """Combine with ``other`` using logical AND (``q1 & q2``)."""
        return BooleanQuery("and", (self, _coerce_query(other)))

    def __or__(self, other: Query) -> Query:
        """Combine with ``other`` using logical OR (``q1 | q2``)."""
        return BooleanQuery("or", (self, _coerce_query(other)))

    def __invert__(self) -> Query:
        """Negate this query using logical NOT (``~q``)."""
        return BooleanQuery("not", (self,))


def _coerce_query(value: Any) -> Query:
    """Validate that ``value`` is a query before combining it with another.

    Guards the ``&`` / ``|`` operators so that mixing a query with a non-query
    (e.g. ``query & "B cell"``) fails fast with a clear ``TypeError`` instead of
    producing a confusing expression.
    """
    if not isinstance(value, Query):
        raise TypeError("Can only combine celldega.select query expressions")
    return value


@dataclass(frozen=True, eq=False)
class Attribute:
    """Reference to an AnnData-backed attribute.

    An ``Attribute`` is a lazy reference to one column of per-entity values: an
    ``adata.obs`` column (``kind="obs"``) or a gene's expression vector
    (``kind="gene"``, optionally from a named ``layer`` or from ``adata.raw``). It
    becomes concrete only when a query or sampler is evaluated by a
    :class:`Selector`.

    Attributes are usually created through :meth:`Selector.attr` or
    :meth:`Selector.gene` rather than instantiated directly.

    Comparison operators build queries, they do not return booleans. Because the
    operators (``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``) and the helper
    methods (:meth:`isin`, :meth:`between`, ...) return :class:`PredicateQuery`
    objects, an ``Attribute`` reads like a value but composes like an expression::

        selector.attr("qc") >= 0.8            # PredicateQuery, not a bool
        selector.attr("cluster").isin(["B", "T"])

    The dataclass is declared ``frozen=True, eq=False``: ``frozen`` makes it an
    immutable value object, and ``eq=False`` is required so that overriding
    ``__eq__`` to return a query does not clash with dataclass value-equality
    (it keeps the default identity-based ``__hash__``).
    """

    kind: Literal["obs", "gene"]
    name: str
    layer: str | None = None
    raw: bool = False

    def evaluate(self, selector: Selector) -> pd.Series:
        """Resolve this reference to a concrete Series aligned to ``selector.ids``.

        Dispatches to the selector's private resolver for the attribute kind:
        ``obs`` columns via :meth:`Selector._obs_attribute`, gene expression via
        :meth:`Selector._gene_attribute` (honoring ``layer`` and ``raw``).
        """
        if self.kind == "obs":
            return selector._obs_attribute(self.name)
        if self.kind == "gene":
            return selector._gene_attribute(self.name, layer=self.layer, raw=self.raw)
        raise ValueError(f"Unknown attribute kind: {self.kind}")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready description of this reference.

        Always includes ``type`` (the kind) and ``name``; ``layer`` and ``raw``
        are included only when set, so the serialized form stays minimal.
        """
        result: dict[str, Any] = {"type": self.kind, "name": self.name}
        if self.layer is not None:
            result["layer"] = self.layer
        if self.raw:
            result["raw"] = True
        return result

    def isin(self, values: Sequence[Any]) -> Query:
        """Build a query matching entities whose value is in ``values``."""
        return PredicateQuery("isin", self, tuple(values))

    def notin(self, values: Sequence[Any]) -> Query:
        """Build a query matching entities whose value is not in ``values``."""
        return PredicateQuery("notin", self, tuple(values))

    def isna(self) -> Query:
        """Build a query matching entities with a missing value."""
        return PredicateQuery("isna", self)

    def notna(self) -> Query:
        """Build a query matching entities with a non-missing value."""
        return PredicateQuery("notna", self)

    def between(
        self,
        left: Any,
        right: Any,
        inclusive: Literal["both", "neither", "left", "right"] = "both",
    ) -> Query:
        """Build a query matching values in the range ``[left, right]``.

        ``inclusive`` controls which endpoints count, mirroring
        ``pandas.Series.between`` (``"both"``, ``"neither"``, ``"left"``,
        ``"right"``).
        """
        return PredicateQuery("between", self, (left, right), {"inclusive": inclusive})

    def __eq__(self, other: Any) -> Query:  # type: ignore[override]
        """Build an equality query (``attr == value``)."""
        return PredicateQuery("eq", self, other)

    def __ne__(self, other: Any) -> Query:  # type: ignore[override]
        """Build an inequality query (``attr != value``)."""
        return PredicateQuery("ne", self, other)

    def __lt__(self, other: Any) -> Query:
        """Build a less-than query (``attr < value``)."""
        return PredicateQuery("lt", self, other)

    def __le__(self, other: Any) -> Query:
        """Build a less-than-or-equal query (``attr <= value``)."""
        return PredicateQuery("le", self, other)

    def __gt__(self, other: Any) -> Query:
        """Build a greater-than query (``attr > value``)."""
        return PredicateQuery("gt", self, other)

    def __ge__(self, other: Any) -> Query:
        """Build a greater-than-or-equal query (``attr >= value``)."""
        return PredicateQuery("ge", self, other)


@dataclass(frozen=True)
class PredicateQuery(Query):
    """A single comparison of one :class:`Attribute` against a value.

    This is the leaf node of a query expression. It is normally produced by the
    operators and helpers on :class:`Attribute` (e.g. ``attr == x`` builds
    ``PredicateQuery("eq", attr, x)``) rather than constructed directly.

    Attributes
    ----------
    op
        The comparison operator (see :data:`QueryOp`).
    attr
        The attribute being tested.
    value
        The comparison operand. Unused for ``isna``/``notna``; a 2-tuple
        ``(left, right)`` for ``between``; a tuple of members for ``isin``/``notin``.
    options
        Operator-specific options, e.g. ``{"inclusive": ...}`` for ``between``.
    """

    op: QueryOp
    attr: Attribute
    value: Any = None
    options: dict[str, Any] | None = None

    def evaluate(self, selector: Selector) -> pd.Series:
        """Resolve the attribute and apply the operator, returning a boolean mask.

        The attribute is materialized to a Series, the operator is applied with
        pandas semantics, and the result is normalized to a clean boolean mask:
        missing comparisons (e.g. ``NaN > 2``) are filled with ``False`` so they
        never match, and the dtype is forced to ``bool``.
        """
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
        """Return a JSON-ready ``{op, attr, [value], [options]}`` description.

        ``value`` is omitted for the unary ``isna``/``notna`` operators, and
        ``options`` only appears when present. Operands are passed through
        :func:`_json_value` so numpy/tuple operands serialize cleanly.
        """
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
    """A logical combination of child queries (``and`` / ``or`` / ``not``).

    Produced by the :class:`Query` operators (``&``, ``|``, ``~``). ``not`` holds
    exactly one child; ``and``/``or`` hold two or more and fold left-to-right.
    """

    op: BooleanOp
    queries: tuple[Query, ...]

    def evaluate(self, selector: Selector) -> pd.Series:
        """Evaluate each child and combine the masks with the boolean operator.

        ``not`` inverts its single child. ``and``/``or`` evaluate every child and
        reduce them with ``&`` / ``|``. Arity is validated (``not`` needs exactly
        one child, ``and``/``or`` need at least two), and the combined result is
        normalized to a clean boolean mask (NaN -> ``False``).
        """
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
        """Return a JSON-ready ``{op, queries}`` tree, recursing into children."""
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
        """Iterate over the ordered ids, so a ``Selection`` works like a list."""
        return iter(self.ids)

    def __len__(self) -> int:
        """Return the number of selected ids."""
        return len(self.ids)

    def __getitem__(self, index):
        """Index or slice the ordered ids (e.g. ``selection[0]``, ``selection[:5]``)."""
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
        """Return a JSON-ready object including query, sampler, and provenance.

        The payload contains ``ids``, the serialized ``query`` and ``sampler``
        (each ``None`` when unused), ``candidate_count``, ``selected_count``,
        JSON-coerced ``provenance``, and ``scores`` when the sampler produced
        them. This is exactly what :class:`celldega.viz.Yearbook` stores to
        record how a portrait set was chosen.
        """
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
        columns, with rows in result order. If the sampler produced scores, a
        ``score`` column is included (aligned by id; entries default to ``None``
        for any id without a score). Handy for inspecting a selection in a
        notebook or joining it back onto other per-entity tables.
        """
        frame = pd.DataFrame({"id": self.ids, "rank": np.arange(len(self.ids))})
        if self.scores is not None:
            frame["score"] = [self.scores.get(inst_id) for inst_id in self.ids]
        return frame

    def page(self, page: int, per_page: int) -> list[str]:
        """Return one zero-based page of ids.

        Slices the ordered ids into fixed-size pages, e.g. for paginating a
        portrait grid. ``page(0, 24)`` returns the first 24 ids, ``page(1, 24)``
        the next 24, and so on. A page past the end returns an empty list.

        Parameters
        ----------
        page
            Zero-based page index. Must be non-negative.
        per_page
            Number of ids per page. Must be positive.
        """
        _validate_count(page, "page")
        if per_page <= 0:
            raise ValueError("per_page must be positive")
        start = page * per_page
        return self.ids[start : start + per_page]


@dataclass(frozen=True)
class SamplingResult:
    """Internal return value of :meth:`Sampler.apply`.

    Bundles the ordered string ``ids`` chosen by a sampler with an optional
    per-id score ``Series`` (ranking samplers populate this; others leave it
    ``None``) and a ``provenance`` dict describing how the sampling ran. The
    :class:`Selector` unpacks this into the public :class:`Selection`.
    """

    ids: list[str]
    scores: pd.Series | None
    provenance: dict[str, Any]


class Sampler(Protocol):
    """Structural protocol implemented by every sampler/ranker.

    A sampler turns a candidate ``pd.Index`` into an ordered subset. Anything
    with the two methods below satisfies the protocol, so :meth:`Selector.select`
    accepts the built-in samplers (and any duck-typed equivalent) uniformly.
    """

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        """Choose and order ids from ``candidate_ids``, returning a SamplingResult.

        Receives the bound ``selector`` (so attribute-based samplers can resolve
        their values) and the already-narrowed candidate index, so the sampler
        only ever does work proportional to the candidate set, not the full
        AnnData.
        """

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready description of the sampler and its parameters."""


@dataclass(frozen=True)
class RandomSampler:
    """Randomly order or sample candidate ids.

    With ``n=None`` this is a shuffle: it returns all candidates in random order.
    With an ``n``, it draws that many. Without ``replace`` the draw is a subset
    (``n`` is clamped to the number of candidates); with ``replace=True`` ids may
    repeat and the result can be longer than the candidate set. A ``seed`` makes
    the draw reproducible. This sampler attaches no scores.

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
        """Validate that ``n`` is non-negative (or ``None``)."""
        _validate_count(self.n)

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        """Draw (or shuffle) ids with a seeded NumPy generator.

        Returns an empty result when there are no candidates or ``n == 0``.
        Without replacement, uses a permutation truncated to ``min(n, len)``;
        with replacement, uses ``rng.choice`` so ids may repeat. ``selector`` is
        unused (the draw needs no attribute values).
        """
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
    """Sample ids from a low/mid/high quantile bin for a numeric attribute.

    The attribute's values define two cut points at quantiles ``q_low`` and
    ``q_high``, splitting entities into three bins. ``bin`` selects which one to
    draw from:

    - ``"low"``  -> values ``<= low_cut``, ordered ascending;
    - ``"mid"``  -> values strictly between the cuts, ordered by closeness to the
      median;
    - ``"high"`` -> values ``>= high_cut``, ordered descending.

    The interior boundaries are half-open so the bins partition cleanly (a value
    sitting exactly on a cut lands in one bin only) -- this matters for tie-heavy
    data such as raw counts.

    Useful for representative inspection: e.g. "show me high-expressing cells for
    this gene" while preserving a stable ranked order in the returned selection.

    Specifying the band
    -------------------
    The band width can be given three ways (mutually exclusive forms of the same
    idea):

    - ``q_low`` / ``q_high`` directly (default thirds: ``1/3`` and ``2/3``);
    - ``proportion`` -- a fraction in ``(0, 1]`` giving the tail/center size;
    - ``percentile`` -- the same as ``proportion`` but on a 0-100 scale.

    With ``proportion``/``percentile`` the cut(s) are derived per bin: ``"low"``
    takes the bottom fraction, ``"high"`` the top fraction, and ``"mid"`` a
    centered band of that width around the median.

    Sampling vs ranking
    -------------------
    If ``n`` is ``None`` or the bin has ``<= n`` members, the whole bin is
    returned in ranked order. If the bin is larger than ``n``, a seeded random
    subset of size ``n`` is drawn and then re-sorted into the bin's natural order.
    The per-id value is attached as the selection's score.

    Parameters
    ----------
    attr
        Numeric attribute to bin (an ``obs`` column or a gene).
    bin
        Which bin to draw from: ``"low"``, ``"mid"``, or ``"high"``.
    n
        Maximum number of ids to return. ``None`` returns the whole bin.
    seed
        Random seed used only when the bin is subsampled.
    q_low, q_high
        Lower/upper quantile cut points in ``[0, 1]`` with ``q_low <= q_high``.
    proportion
        Alternative band specification as a fraction in ``(0, 1]``.
    percentile
        Alternative band specification as a percentage in ``(0, 100]``.
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
        """Validate ``n``, the bin name, the quantile order, and the band specs.

        Enforces ``0 <= q_low <= q_high <= 1``, that ``proportion`` and
        ``percentile`` are not both set, and that each falls in its valid range.
        """
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
        """Bin the candidates by quantile, then rank or subsample the chosen bin.

        Resolves the attribute over the candidates, drops non-numeric/missing
        values, computes the two quantile cuts, selects the requested bin in its
        natural order, and (if larger than ``n``) draws a seeded random subset
        that is then re-sorted. Returns an empty result with a ``reason`` when no
        numeric values are available. Provenance records the cut points, bin
        size, and seed.
        """
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

        # Bins partition the values: the interior boundaries are half-open so a
        # value equal to a cut lands in exactly one bin (important for tie-heavy
        # data such as raw counts). low: <= low_cut, mid: (low_cut, high_cut),
        # high: >= high_cut.
        if self.bin == "low":
            binned = numeric[numeric <= low_cut]
            ordered = binned.sort_values(ascending=True, kind="mergesort")
        elif self.bin == "mid":
            binned = numeric[(numeric > low_cut) & (numeric < high_cut)]
            median = float(numeric.median())
            ordered = binned.loc[(binned - median).abs().sort_values(kind="mergesort").index]
        else:
            binned = numeric[numeric >= high_cut]
            ordered = binned.sort_values(ascending=False, kind="mergesort")

        if self.n is not None and len(ordered) > self.n:
            # Bin is bigger than the quota: draw a random subset, then restore the
            # bin's natural order (the random draw scrambled it).
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
        """Resolve the effective ``(q_low, q_high)`` cut points for this bin.

        When ``proportion``/``percentile`` is given it overrides ``q_low``/
        ``q_high``: ``"low"`` returns the bottom fraction (both cuts equal),
        ``"high"`` the top fraction, and ``"mid"`` a centered band of that width
        around the median. Otherwise the configured ``q_low``/``q_high`` are used.
        """
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
        """Re-sort a randomly subsampled bin back into the bin's natural order.

        After random subsampling scrambles the order, this restores it: ascending
        for ``"low"``, descending for ``"high"``, and by distance to the median
        (computed over ``all_values``) for ``"mid"``.
        """
        if self.bin == "low":
            return values.sort_values(ascending=True, kind="mergesort")
        if self.bin == "mid":
            median = float(all_values.median())
            return values.loc[(values - median).abs().sort_values(kind="mergesort").index]
        return values.sort_values(ascending=False, kind="mergesort")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready description, including the band specification.

        Always includes the attribute, ``bin``, ``n``, ``seed``, and the
        ``q_low``/``q_high`` cuts; ``proportion``/``percentile`` are added only
        when they were supplied.
        """
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
    """Select ids whose numeric attribute value is near a target ``center``.

    Each candidate gets a Gaussian weight ``exp(-0.5 * ((value - center) / std)
    ** 2)``: a value exactly at ``center`` scores ``1.0`` and the weight falls
    off with distance. ``std`` controls the tolerance -- small ``std`` is a sharp
    peak (only very close values matter), large ``std`` is broad. (The usual
    ``1 / (std * sqrt(2*pi))`` normalizing constant is omitted because it cancels
    when sorting and when normalizing the sampling probabilities.)

    Two modes
    ---------
    - **Rank everything** (``n`` is ``None`` or ``>=`` the candidate count):
      return all candidates ordered by closeness to ``center`` (closest first).
    - **Weighted subsample** (``n`` smaller than the candidate count): draw ``n``
      ids without replacement using the Gaussian weights as probabilities
      (seeded via ``seed``), then re-order the draw closest-first.

    In both modes the per-id weight is attached as the selection's score.

    Use for "around this value" inspection -- e.g. cells near a particular QC
    score or expression level.

    Parameters
    ----------
    attr
        Numeric attribute to weight on.
    center
        Target value the sampler is biased toward.
    std
        Standard deviation of the Gaussian; must be positive. Larger = broader.
    n
        Number of ids to draw. ``None`` ranks all candidates by closeness.
    seed
        Random seed used only in the weighted-subsample mode.

    Notes
    -----
    In the subsample mode, an aggressively small ``std`` can drive many weights to
    underflow to exactly ``0``. If fewer than ``n`` candidates retain a positive
    weight, the underlying ``rng.choice(replace=False, p=...)`` will raise.
    """

    attr: Attribute
    center: float
    std: float
    n: int | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate that ``n`` is non-negative and ``std`` is strictly positive."""
        _validate_count(self.n)
        if self.std <= 0:
            raise ValueError("std must be positive")

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        """Weight candidates by a Gaussian and either rank or weighted-sample them.

        Resolves the attribute, drops non-numeric/missing values, computes the
        Gaussian weights, and either returns all candidates ordered by closeness
        (when ``n`` covers them all) or draws a seeded weighted subset that is
        then re-ordered closest-first. Returns an empty result with a ``reason``
        when no numeric values are available.
        """
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
        # Unnormalized Gaussian kernel: weight 1.0 at the center, decaying with
        # distance. The 1/(std*sqrt(2*pi)) constant is dropped because it cancels
        # under both sorting and probability normalization below.
        weights = np.exp(-0.5 * np.square((numeric - self.center) / self.std))
        weight_series = pd.Series(weights, index=numeric.index, name="weight")

        if self.n is None or self.n >= len(weight_series):
            # Rank mode: keep everyone, ordered closest-to-center first (sorting
            # by distance ascending == sorting by weight descending).
            ordered = weight_series.loc[
                distances.sort_values(ascending=True, kind="mergesort").index
            ]
        else:
            # Subsample mode: weighted draw favoring the center, then re-order the
            # drawn ids closest-first.
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
        """Return a JSON-ready ``{type, attr, center, std, n, seed}`` description."""
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
    """Deterministically return the highest- or lowest-valued ids for an attribute.

    Sorts the candidates by a numeric attribute and takes the top (``by="high"``)
    or bottom (``by="low"``) ``n``. Unlike the random/Gaussian samplers this is
    fully deterministic (no seed): a stable mergesort is used so ties keep their
    original relative order. The per-id value is attached as the score.

    Good for "top markers" style inspection -- e.g. the highest-expressing cells
    for a gene, or the lowest-QC cells.

    Parameters
    ----------
    attr
        Numeric attribute to rank by.
    n
        Number of ids to return. ``None`` returns all candidates, ranked.
    by
        ``"high"`` for descending (largest first), ``"low"`` for ascending.
    """

    attr: Attribute
    n: int | None = None
    by: RankDirection = "high"

    def __post_init__(self) -> None:
        """Validate that ``n`` is non-negative and ``by`` is ``"high"`` or ``"low"``."""
        _validate_count(self.n)
        if self.by not in {"high", "low"}:
            raise ValueError("by must be 'high' or 'low'")

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        """Sort candidates by value and take the top/bottom ``n``.

        Resolves the attribute, drops non-numeric/missing values, sorts in the
        requested direction, and truncates to ``n``. Returns an empty result with
        a ``reason`` when no numeric values are available.
        """
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
        """Return a JSON-ready ``{type, attr, n, by}`` description."""
        return {
            "type": "rank",
            "attr": self.attr.to_dict(),
            "n": self.n,
            "by": self.by,
        }


@dataclass(frozen=True)
class StratifiedSampler:
    """Draw a balanced sample across the categories of a categorical attribute.

    Provide exactly one of two quota modes:

    - ``n_per_category`` -- take up to this many ids from *each* category
      (capped by how many that category actually has);
    - ``n`` -- a total quota distributed as evenly as possible across categories,
      via round-robin allocation (categories that run out are skipped, so larger
      categories absorb the remainder).

    Within each category the ids are drawn at random (seeded via ``seed``). The
    result is grouped by category in the order the categories are processed
    (i.e. not interleaved across categories). No scores are attached.

    Good for balanced inspection -- e.g. an equal number of cells per cluster.

    Parameters
    ----------
    attr
        Categorical attribute to stratify on.
    n_per_category
        Per-category quota. Mutually exclusive with ``n``.
    n
        Total quota spread evenly across categories. Mutually exclusive with
        ``n_per_category``.
    seed
        Random seed for the within-category draws.
    categories
        Optional explicit category order/subset. When ``None``, categories are
        discovered from the data in first-seen order.
    """

    attr: Attribute
    n_per_category: int | None = None
    n: int | None = None
    seed: int | None = None
    categories: tuple[Any, ...] | None = None

    def __post_init__(self) -> None:
        """Validate the quotas: non-negative, and exactly one of ``n`` / ``n_per_category``."""
        _validate_count(self.n_per_category, "n_per_category")
        _validate_count(self.n, "n")
        if self.n is None and self.n_per_category is None:
            raise ValueError("either n or n_per_category must be provided")
        if self.n is not None and self.n_per_category is not None:
            raise ValueError("n and n_per_category are mutually exclusive")

    def apply(self, selector: Selector, candidate_ids: pd.Index) -> SamplingResult:
        """Allocate per-category quotas, then draw that many ids from each category.

        Resolves the attribute and drops missing values, groups candidates by
        category, computes each category's quota (fixed per-category, or
        round-robin for a total ``n``), draws ids at random within each, and
        concatenates the groups. Provenance records per-stratum availability and
        sampled counts plus the quota ``mode``.
        """
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
            # Fixed per-category quota, capped by what each category actually has.
            for category in categories:
                sample_counts[category] = min(
                    self.n_per_category, len(group_ids_by_category[category])
                )
        else:
            # Total quota: hand out one slot per category per pass (round-robin)
            # until the quota is met or every category is exhausted. This spreads
            # the total as evenly as possible; categories that run out are skipped.
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
                    # Every remaining category is full but quota is unmet (n
                    # exceeds the available pool): stop instead of looping forever.
                    break
                # Drop categories that just filled up so later passes skip them.
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
        """Return a JSON-ready description; includes whichever quota and categories were set."""
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
    """Notebook-friendly constructors for samplers, exposed as ``selector.samplers``.

    Each method builds and returns one of the sampler dataclasses
    (:class:`RandomSampler`, :class:`QuantileBinSampler`, :class:`GaussianSampler`,
    :class:`RankSampler`, :class:`StratifiedSampler`). The methods add light
    type-checking (attribute-based samplers verify their ``attr`` came from
    :meth:`Selector.attr` / :meth:`Selector.gene`) and otherwise just forward
    their arguments, so ``selector.samplers.rank(...)`` reads naturally inside a
    :meth:`Selector.select` call.
    """

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
        """Return a sampler biased toward a numeric ``center`` value.

        ``std`` sets the Gaussian width (tolerance). With ``n`` set, draws a
        seeded weighted subset; otherwise ranks all candidates by closeness. See
        :class:`GaussianSampler` for the weighting and the two modes.
        """
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
        """Return a deterministic top/bottom-``n`` ranker for a numeric attribute.

        ``by="high"`` takes the largest values, ``by="low"`` the smallest. See
        :class:`RankSampler`.
        """
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
        """Return a sampler that draws evenly across categorical strata.

        Provide exactly one of ``n_per_category`` (a per-category quota) or ``n``
        (a total spread evenly across categories). ``categories`` optionally fixes
        the category order/subset. See :class:`StratifiedSampler`.
        """
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

        obs_names = pd.Index(adata.obs_names)
        if obs_names.has_duplicates:
            dups = obs_names[obs_names.duplicated()].unique().tolist()
            shown = ", ".join(repr(d) for d in dups[:5])
            suffix = ", ..." if len(dups) > 5 else ""
            raise ValueError(
                "Selector requires unique obs_names because they are used as selection "
                f"ids; found {len(dups)} duplicated name(s): {shown}{suffix}"
            )

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
            How to order/subset the candidates. Accepts several forms, dispatched
            in this order:

            - ``None`` -- return candidates in source order, unless the candidate
              set exceeds ``default_preview_n``, in which case a deterministic
              random preview is returned with a warning (the guard against
              accidentally materializing a huge selection);
            - a ``bool`` -- rejected with a clear error (guards against
              ``sampler=True`` being silently treated as the integer ``1``);
            - an ``int`` -- shorthand for a deterministic random sample of that
              many ids, seeded with ``default_preview_seed``;
            - ``"all"`` -- explicitly return every matching id, no preview guard;
            - a sampler from ``selector.samplers`` -- applied to the candidates.

        Returns
        -------
        Selection
            Stable ordered selected ids plus JSON-ready query, sampler, scores,
            and provenance (source shape, candidate/selected counts, and the
            sampler's own provenance).

        Notes
        -----
        The query is evaluated first to narrow the candidate set, and the sampler
        only ever sees that narrowed index -- so expensive samplers do work
        proportional to the matches, not the whole AnnData.
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
            # Must precede the Integral check: bool is a subclass of int, so this
            # rejects sampler=True/False instead of silently treating it as 1/0.
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
        """Return ``True`` when an unsampled selection should fall back to a preview.

        True only when the preview guard is enabled (``default_preview_n`` is not
        ``None``) and the candidate set exceeds it.
        """
        return self.default_preview_n is not None and len(candidate_ids) > self.default_preview_n

    def _preview_selection(
        self,
        candidate_ids: pd.Index,
    ) -> tuple[list[str], dict[str, Any], None, dict[str, Any]]:
        """Build the deterministic random preview for an oversized unsampled query.

        Warns the user (explaining how to opt into ``"all"``, an integer count,
        or an explicit sampler), then draws ``default_preview_n`` ids with a
        seeded :class:`RandomSampler`. Returns the tuple
        ``(ids, sampler_dict, scores, sampler_provenance)`` consumed by
        :meth:`select`; ``scores`` is always ``None`` for a preview.
        """
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
        """Return the ids matching ``query`` (all ids when ``query`` is ``None``).

        Evaluates the query to a boolean mask, reindexes it onto the full id
        index filling any gaps with ``False`` (a safety net so the mask always
        aligns), and returns the matching ids in source order.
        """
        if query is None:
            return self.ids

        mask = query.evaluate(self).reindex(self.ids, fill_value=False)
        return self.ids[mask.to_numpy(dtype=bool)]

    def _obs_attribute(self, name: str) -> pd.Series:
        """Resolve an ``adata.obs`` column to a Series indexed by the entity ids.

        Raises ``KeyError`` with a clear message if the column is missing.
        """
        if name not in self.adata.obs.columns:
            raise KeyError(f"Attribute '{name}' not found in adata.obs")
        return pd.Series(self.adata.obs[name], index=self.ids, name=name)

    def _gene_attribute(
        self, name: str, *, layer: str | None = None, raw: bool = False
    ) -> pd.Series:
        """Resolve a gene's expression vector to a Series indexed by the entity ids.

        Reads from ``adata.raw`` when ``raw=True``, a named ``layer`` when given,
        or ``adata.X`` otherwise. The single-gene slice is densified and flattened
        via :func:`_as_1d_array`, so sparse matrices are handled transparently.

        Raises ``KeyError`` for a missing gene or layer, ``ValueError`` when
        ``raw`` is requested but ``adata.raw`` is absent, and ``ValueError`` when
        the gene name is not unique in ``var_names`` (which would make the slice
        ambiguous).
        """
        data = self.adata.raw if raw else self.adata
        if data is None:
            raise ValueError("adata.raw is not available")
        if name not in data.var_names:
            raise KeyError(f"Gene '{name}' not found in adata.var_names")
        if np.count_nonzero(np.asarray(data.var_names) == name) > 1:
            raise ValueError(
                f"Gene '{name}' is not unique in adata.var_names; gene selection "
                "requires unique gene names"
            )

        if raw:
            matrix = data[:, name].X
        elif layer is None:
            matrix = self.adata[:, name].X
        else:
            if layer not in self.adata.layers:
                raise KeyError(f"Layer '{layer}' not found in adata.layers")
            matrix = self.adata[:, name].layers[layer]

        return pd.Series(_as_1d_array(matrix), index=self.ids, name=name)
