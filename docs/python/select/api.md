# Select API

The `select` module provides a small query and sampling layer over AnnData. It is designed to answer questions like:

- Which entities match this metadata/gene filter?
- In what stable order should those ids be shown?
- What query and sampler produced that order?

The main class is `Selector`, used from the `dega.select` namespace:

```python
import celldega as dega

selector = dega.select.Selector(adata)
```

## Core Concepts

`Selector` separates three pieces of selection logic:

| Concept | API | Purpose |
| --- | --- | --- |
| Attribute | `selector.attr(...)`, `selector.gene(...)` | Reference per-entity values from `adata.obs` or gene expression |
| Query | `(selector.attr("cluster") == "B cell")` | Define the candidate set with categorical, numeric, and gene-expression predicates combined with boolean logic. |
| Sampler | `selector.samplers.random(...)`, `selector.samplers.quantile_bin(...)`, or `sampler=3000` | Choose or rank ids from the candidate set |

This keeps the backend responsible for producing a stable ordered list of ids plus provenance. Widgets such as `Yearbook` can then paginate over that ordered list.

## Basic Selection

```python
selector = dega.select.Selector(adata)

query = (
    (selector.attr("cluster") == "B cell")
    & selector.attr("sample_id").isin(["S1", "S2"])
)

selection = selector.select(query=query)
selection.names()
```

`selection.names()` returns the ordered ids, usually names from `adata.obs_names`.

## Safe Default Preview

If a query matches a very large number of entities and no sampler is provided, `Selector` returns a deterministic random preview instead of accidentally handing a widget or notebook hundreds of thousands of ids.

By default:

- candidate sets up to 1,000 ids are returned in full;
- candidate sets over 1,000 ids return a deterministic random preview of 1,000 ids;
- a warning explains that previewing happened and how to request all matches.

```python
selection = selector.select(query=query)
```

To intentionally return every matching id, pass `sampler="all"`:

```python
selection = selector.select(query=query, sampler="all")
```

For the common case of "give me N random ids", pass an integer. This uses the selector's `default_preview_seed` so the shorthand is reproducible:

```python
selection = selector.select(query=query, sampler=3000)
```

To make sampling explicit and reproducible, pass a sampler:

```python
selection = selector.select(
    query=query,
    sampler=selector.samplers.random(n=5000, seed=1),
)
```

The default preview size can be changed when the selector is created:

```python
selector = dega.select.Selector(adata, default_preview_n=2000)
```

Set `default_preview_n=None` to disable the preview guard.

## Sampling And Ranking

Sampler constructors are grouped under `selector.samplers`.

Each built-in sampler is backed by a concrete sampler class such as `RandomSampler`, `QuantileBinSampler`, `RankSampler`, `GaussianSampler`, or `StratifiedSampler`. `selector.samplers.*` is the notebook-friendly constructor namespace for creating those objects.

## Built-In Samplers

| Sampler | API | Behavior | Good for |
| --- | --- | --- | --- |
| Random | `selector.samplers.random(n=..., seed=...)` or `sampler=3000` | Random sample, optionally reproducible with `seed` | Quick representative subsets |
| Rank | `selector.samplers.rank(attr=..., n=..., by="high")` | Deterministic top or bottom ids by attribute value | Highest-expression or lowest-QC examples |
| Quantile Bin | `selector.samplers.quantile_bin(attr=..., bin="high", ...)` | Sample from a low/mid/high region of a distribution | Representative sampling from tails or the middle |
| Gaussian | `selector.samplers.gaussian(attr=..., center=..., std=..., n=...)` | Bias samples toward a numeric target value | “Near this score” or “around this expression level” |
| Stratified | `selector.samplers.stratified(attr=..., n_per_category=...)` or `n=...` | Evenly distribute samples across categories | Balanced cluster/sample selections |

```python
selection = selector.select(
    query=query,
    sampler=selector.samplers.random(n=24, seed=1),
)
```

Random sampling is the simplest exploratory sampler. If you just want a bounded subset and do not care about an attribute-specific distribution, this is usually the right default.

For deterministic top or bottom ids by an attribute:

```python
selection = selector.select(
    sampler=selector.samplers.rank(
        attr=selector.gene("MS4A1"),
        n=24,
        by="high",
    ),
)
```

For gene-expression-driven inspection, use a quantile-bin sampler:

```python
selection = selector.select(
    query=query,
    sampler=selector.samplers.quantile_bin(
        attr=selector.gene("MS4A1"),
        bin="high",
        n=24,
        seed=1,
    ),
)
```

The returned ids preserve the sampler's order. For `bin="high"`, selected ids are ordered from higher to lower expression after sampling.

For narrower tails such as "top 5%", use `proportion` or `percentile`:

```python
selection = selector.select(
    query=query,
    sampler=selector.samplers.quantile_bin(
        attr=selector.gene("MS4A1"),
        bin="high",
        percentile=5,
    ),
)
```

For Gaussian-weighted sampling around a target value:

```python
selection = selector.select(
    sampler=selector.samplers.gaussian(
        attr=selector.attr("qc_score"),
        center=0.8,
        std=0.05,
        n=24,
        seed=1,
    ),
)
```

For even sampling across categories:

```python
selection = selector.select(
    sampler=selector.samplers.stratified(
        attr=selector.attr("cluster"),
        n_per_category=10,
        seed=1,
    ),
)
```

For a total quota distributed as evenly as possible across categories:

```python
selection = selector.select(
    sampler=selector.samplers.stratified(
        attr=selector.attr("cluster"),
        n=100,
        seed=1,
    ),
)
```

## Result Objects

`selector.select(...)` returns a `Selection`. It behaves like an ordered list of selected ids and also carries provenance.

```python
len(selection)
selection[0]
list(selection)
selection.names()
```

For notebook work:

```python
selection.to_dataframe()
```

For serialization or frontend integration:

```python
selection.to_json()
```

The JSON-ready object includes:

- `ids`: ordered selected ids
- `query`: serialized query expression
- `sampler`: serialized sampler definition
- `candidate_count`: number of entities matching the query
- `selected_count`: number of returned ids
- `scores`: optional ranking scores keyed by id
- `provenance`: execution metadata

## Validation

Queries are validated when they are executed by `selector.select(...)`.

- Missing `adata.obs` columns raise `KeyError`.
- Missing genes raise `KeyError`.
- Missing layers raise `KeyError`.
- Missing `adata.raw` raises `ValueError` when `raw=True`.

This means query objects can be built lazily, but the selector confirms that their attributes exist in the AnnData object before returning a selection.

## Multiple AnnDatas

A selector is bound to one AnnData object. For multiple datasets, instantiate one selector per AnnData and use explicit names:

```python
skin_selector = dega.select.Selector(skin_adata)
lymph_selector = dega.select.Selector(lymph_adata)

skin_selection = skin_selector.select(
    query=skin_selector.attr("cluster") == "B cell",
)

lymph_selection = lymph_selector.select(
    query=lymph_selector.attr("cluster") == "B cell",
)
```

Spelling out `selector` and `selection` is recommended for real notebooks because the two concepts are easy to confuse if abbreviated.

## Backend vs. Front-End Selection

There are two complementary ways to decide which cells a `Yearbook` shows. They
solve the same problem — "which cells, in what order" — but run in different
places and have different requirements.

| | Back-end selection (`select` module) | Front-end query (`front_end_query`) |
| --- | --- | --- |
| Runs in | Python, before the widget renders | The browser, against LandscapeFiles |
| Requires | An in-memory `AnnData` object | Only `base_url` (no Python `AnnData`) |
| Expressiveness | Full query algebra + five samplers/rankers | Single cluster filter and/or single-gene ranking |
| Reproducibility | Seeded, serialized query + sampler + scores | Stateless; recomputed in the browser each time |
| Provenance | `selection.to_json()` captured on the widget | Query dict only |
| Pass to Yearbook as | `selection=` (or a plain id list via `cells=`) | `front_end_query=` |

Use the **back-end** path when you have an `AnnData` object and want rich,
reproducible queries (boolean logic across obs columns and genes, quantile-bin
or Gaussian sampling, stratified balancing, captured scores and provenance).

Use the **front-end** path for lightweight, AnnData-free browsing directly from
a dataset URL — for example "show cells in cluster 8" or "rank cells by `BRCA1`
expression". See the [Front-End Query](../viz/api.md#front-end-query) section
of the viz docs for the supported dict shapes.

The two map onto each other. A single-gene front-end query
`{"gene": "MS4A1"}` is the in-browser equivalent of the back-end rank sampler:

```python
selection = selector.select(
    sampler=selector.samplers.rank(attr=selector.gene("MS4A1"), by="high"),
)
```

## Yearbook Integration

`Yearbook` can render a back-end selection directly:

```python
yearbook = dega.viz.Yearbook(
    base_url=base_url,
    selection=selection,
    rows=2,
    cols=4,
)
```

Internally, Yearbook uses `selection.names()` as its ordered `cells` list and
stores `selection.to_json()` for provenance. The frontend can paginate over the
ordered ids without needing to understand the query machinery.

`selection=` accepts a `Selection`, a JSON-ready selection dict, or a plain list
of cell ids. Pass either `selection=` or `cells=`, not both.

## API Reference

::: celldega.select
    handler: python
