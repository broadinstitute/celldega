# Select API

The `select` module provides a small query and sampling layer over AnnData. It is designed to answer questions like:

- Which cells match this metadata/gene filter?
- In what stable order should those cells be shown?
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
| Query | `(selector.attr("cluster") == "B cell")` | Define the candidate set with boolean logic |
| Sampler | `selector.samplers.random(...)` | Choose or rank cells from the candidate set |

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

`selection.names()` returns the ordered ids, usually cell names from `adata.obs_names`.

## Sampling And Ranking

Sampler constructors are grouped under `selector.samplers`.

```python
selection = selector.select(
    query=query,
    sampler=selector.samplers.random(n=24, seed=1),
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

The returned ids preserve the sampler's order. For `bin="high"`, selected cells are ordered from higher to lower expression after sampling.

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

## Yearbook Integration

`Yearbook` can render a selection directly:

```python
yearbook = dega.viz.Yearbook(
    base_url=base_url,
    selection=selection,
    rows=2,
    cols=4,
)
```

Internally, Yearbook uses `selection.names()` as its ordered `cells` list and stores `selection.to_json()` for provenance. The frontend can paginate over the ordered cells without needing to understand the query machinery.

Pass either `selection=` or `cells=`, not both.

## API Reference

::: celldega.select
    handler: python
