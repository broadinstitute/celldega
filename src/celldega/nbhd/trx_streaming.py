"""Streaming, spatial-index-accelerated transcript-to-entity assignment.

The other cell-free code paths in :mod:`celldega.nbhd.neighborhoods`
(``gdf_trx=`` or ``data_dir=``) load every transcript into memory as point
geometries and run a single :meth:`geopandas.GeoDataFrame.sjoin`. For a
whole-tile ``transcripts.parquet`` (tens of millions of rows, e.g. covering a
55,000 x 55,000 micron tile) that is more memory than is comfortable to hold —
especially when the same file is assigned once per radius in a
:meth:`~celldega.nbhd.collection.NeighborhoodCollection.calc_expansion`
series.

This module instead streams the parquet file in batches via ``pyarrow``, and for
each batch only tests the entities whose bounding box the batch could plausibly
intersect (using the entity ``GeoDataFrame``'s spatial index), so memory use stays
bounded by the batch size regardless of the total transcript count.
"""

from __future__ import annotations

from collections import defaultdict

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import shapely


def _assign_trx_to_entity_streaming_parquet(
    trx_parquet_path: str,
    gdf_entity: gpd.GeoDataFrame,
    id_col: str,
    *,
    x_col: str = "x",
    y_col: str = "y",
    gene_col: str = "gene",
    batch_size: int = 1_000_000,
    assume_non_overlapping: bool = True,
) -> pd.DataFrame:
    """Stream transcripts from ``trx_parquet_path`` and count them per entity/gene.

    For each streamed batch of transcripts, candidate entities are first narrowed
    down with ``gdf_entity``'s spatial index (by the batch's bounding box), then
    each candidate's exact polygon is tested with a vectorized point-in-polygon
    check (``shapely.contains_xy``). Counts are accumulated across batches.

    Args:
        trx_parquet_path: Path to a transcripts parquet file (or partitioned
            dataset directory) containing at least ``x_col``, ``y_col``, and
            ``gene_col``.
        gdf_entity: One row per entity to assign transcripts to — e.g. a nucleus,
            cell, or a single radius's buffered polygons from
            :meth:`NeighborhoodCollection.calc_expansion` — with an ``id_col``
            column and a ``geometry`` column.
        id_col: Column in ``gdf_entity`` identifying each entity.
        x_col: Transcript x-coordinate column in the parquet file.
        y_col: Transcript y-coordinate column in the parquet file.
        gene_col: Transcript gene/feature column in the parquet file.
        batch_size: Number of transcript rows read per streamed batch. Bounds
            peak memory use; does not affect the result.
        assume_non_overlapping: If ``True`` (default), a transcript is excluded
            from consideration for further entities once assigned. Valid whenever
            entities don't overlap (nuclei, cells, non-overlapping radial-buffer
            rings), and lets a batch stop early once every point has a match.

    Returns:
        A ``DataFrame`` indexed by entity id (as ``str``) with one integer count
        column per gene seen in an assigned transcript. Entities with zero
        assigned transcripts, and genes never seen in an assigned transcript, are
        simply absent — callers typically reindex/``fillna(0)`` against the full
        entity and gene axes.

    Raises:
        KeyError: If ``id_col`` is missing from ``gdf_entity``.
        ValueError: If ``gdf_entity`` has no valid (non-null) geometries.
    """
    if id_col not in gdf_entity.columns:
        raise KeyError(f"gdf_entity missing '{id_col}'")

    entity = gdf_entity[[id_col, "geometry"]].copy()
    entity = entity[entity.geometry.notna()].reset_index(drop=True)
    if entity.empty:
        raise ValueError("gdf_entity has no valid geometries")
    entity["geometry"] = entity.geometry.buffer(0)
    entity[id_col] = entity[id_col].astype(str)

    ids = entity[id_col].to_numpy()
    geoms = entity.geometry.to_numpy()
    bboxes = np.array([g.bounds for g in geoms], dtype=np.float64)
    sindex = entity.sindex

    dataset = ds.dataset(trx_parquet_path, format="parquet")
    scanner = dataset.scanner(columns=[x_col, y_col, gene_col], batch_size=batch_size)

    counts: dict[tuple[str, str], int] = defaultdict(int)

    for batch in scanner.to_batches():
        if batch.num_rows == 0:
            continue

        x = batch.column(batch.schema.get_field_index(x_col)).to_numpy(zero_copy_only=False)
        y = batch.column(batch.schema.get_field_index(y_col)).to_numpy(zero_copy_only=False)
        gene = batch.column(batch.schema.get_field_index(gene_col)).to_numpy(zero_copy_only=False)

        valid = np.isfinite(x) & np.isfinite(y)
        if not valid.all():
            x, y, gene = x[valid], y[valid], gene[valid]
        if len(x) == 0:
            continue

        assigned = np.full(len(x), -1, dtype=np.int64)

        candidates = list(sindex.intersection((x.min(), y.min(), x.max(), y.max())))
        for j in candidates:
            minx, miny, maxx, maxy = bboxes[j]
            cand = (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
            if assume_non_overlapping:
                cand &= assigned == -1
            if not cand.any():
                continue

            idx = np.flatnonzero(cand)
            inside = shapely.contains_xy(geoms[j], x[idx], y[idx])
            if inside.any():
                assigned[idx[inside]] = j

            if assume_non_overlapping and (assigned != -1).all():
                break

        keep = assigned != -1
        if not keep.any():
            continue

        chunk = pd.DataFrame({id_col: ids[assigned[keep]], gene_col: gene[keep]})
        for (eid, g), c in chunk.value_counts().items():
            counts[(eid, g)] += int(c)

    if not counts:
        return pd.DataFrame(index=pd.Index([], name=id_col))

    df_long = pd.DataFrame(
        [(eid, g, c) for (eid, g), c in counts.items()],
        columns=[id_col, gene_col, "count"],
    )
    return (
        df_long.pivot_table(
            index=id_col, columns=gene_col, values="count", fill_value=0, aggfunc="sum"
        )
        .rename_axis(None, axis=1)
        .astype(int)
    )
