"""Write an aligned AnnData to `neighborhood-cloud` DegaFiles in one call.

Mirrors :func:`~celldega.align.point_cloud.write_alignment_point_cloud`'s
ergonomics (take an aligned ``AnnData`` directly, no intermediate DegaFiles or
hand-built collection objects) for the other side of the same choice: a
point-cloud view loads every cell up front and is meant for relatively small
datasets (rule of thumb: under ~5-10M points); `neighborhood-cloud` shows
precomputed alpha-shape polygons per (cluster, slice) instead — cheap to load
regardless of dataset size — with real cell centroids streamed in only on
selection, for datasets too large to reasonably load as a point cloud.

This is a thin orchestrator over the lower-level pieces already in
`celldega.nbhd` (real alpha-shape geometry, reused rather than reimplemented
here) and `celldega.pre.nbhd_cloud` (the DegaFile parquet writers) — it does
not duplicate any computation, just chains
:func:`~celldega.nbhd.alpha_shape_cell_clusters_by_slice` ->
:class:`~celldega.nbhd.NeighborhoodCollection` ->
:func:`~celldega.pre.write_nbhd_cloud_dataset`, and optionally
:func:`~celldega.pre.write_gene_shapes_streaming` for gene-nbhds.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import anndata as ad
    import pandas as pd


def write_nbhd_cloud(
    adata: ad.AnnData,
    dega_files_dir: str | Path,
    *,
    cluster_attr: str = "cluster",
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    alphas: Sequence[float] = (150,),
    z_jitter: float = 0.1,
    meta_cluster: pd.DataFrame | None = None,
    compute_gene_nbhds: bool = False,
    gene_list: Sequence[str] | None = None,
    gene_min_expression: float = 2.0,
    gene_min_cells: int = 4,
    gene_max_cells: int = 50_000,
    gene_z_jitter: float | None = None,
    gene_progress_every: int = 500,
) -> Path:
    """Write a full `neighborhood-cloud` DegaFiles set from an aligned AnnData.

    Computes one real alpha-shape polygon per (slice, cluster) — using
    `celldega.nbhd`'s alpha-shape machinery, the same well-tested geometry
    code the rest of celldega already relies on, not a separate/duplicated
    implementation — and writes the full DegaFile layout
    (`meta_slice.parquet`, `shapes/by_slice/`, `cells/by_cluster/`,
    `meta_neighborhood.parquet`, `cell_clusters/meta_cluster.parquet`,
    `landscape_parameters.json`).

    Gene-nbhds (a curated marker-gene list's own alpha shapes, "peppered"
    with real expressing-cell centroids) are **off by default**: a real
    alpha shape per gene is expensive enough — and only useful for a
    deliberately chosen list of marker genes, not the whole transcriptome —
    that auto-computing it isn't the right default. Pass
    `compute_gene_nbhds=True` with an explicit `gene_list` to also write
    `shapes/by_gene/` + `cells/by_gene/` for those genes.

    Works on any AnnData with the right `obs`/`obsm` columns, not just the
    output of `celldega.align` specifically — e.g. straight off
    `align_serial_slices` (which already sets `obsm["spatial"]`, `obs["Z"]`,
    and carries whatever cluster/slice columns were used for landmarks), or
    any other aligned 3D AnnData with equivalent columns.

    Parameters
    ----------
    adata : AnnData
        Aligned 3D cell-level AnnData: `obsm["spatial"]` (x, y),
        `obs[cluster_attr]`, `obs[slice_attr]`, optionally `obs[z_attr]`.
        For gene-nbhds, also needs a real expression matrix in `.X`
        (`adata[:, gene].X` must be numeric counts/expression, not a
        placeholder).
    dega_files_dir : str | Path
        Output DegaFiles root directory (created if missing).
    cluster_attr, slice_attr, z_attr : str, str, str | None
        See `celldega.nbhd.alpha_shape_cell_clusters_by_slice`.
    alphas : Sequence[float]
        Single inverse-alpha resolution used for both cluster shapes and (if
        requested) gene shapes — see `alpha_shape_cell_clusters_by_slice`.
    z_jitter : float
        Per-cluster Z offset within a slice, to avoid z-fighting between
        coplanar cluster polygons (see `alpha_shape_cell_clusters_by_slice`).
    meta_cluster : pd.DataFrame | None
        Optional cluster color/metadata lookup. Without it, colors come from
        `adata.uns[f"{cluster_attr}_colors"]` if present (the usual place
        scanpy leaves them after `sc.tl.leiden`/`sc.pl.umap`), else black.
    compute_gene_nbhds : bool
        Whether to also compute and write gene-nbhds. Default `False` — see
        above. Requires `gene_list`.
    gene_list : Sequence[str] | None
        Genes to compute shapes for when `compute_gene_nbhds=True`. Required
        in that case — deliberately not auto-selected from the whole gene
        panel, since a real alpha shape per gene is too expensive to want by
        accident. Ignored otherwise.
    gene_min_expression, gene_min_cells, gene_max_cells, gene_progress_every :
        Forwarded to `celldega.pre.write_gene_shapes_streaming` — see its
        docstring for `min_expression`/`min_cells`/`max_cells`/
        `progress_every`.
    gene_z_jitter : float | None
        Per-gene Z offset (see `write_gene_shapes_streaming`). Defaults to
        `z_jitter` (the same value used for cluster shapes) if not given.

    Returns
    -------
    pathlib.Path
        `dega_files_dir`, as a `Path`.

    Examples
    --------
    >>> from celldega.align import write_nbhd_cloud
    >>> write_nbhd_cloud(adata_aligned, "my_dataset_nbhd_cloud")
    >>> # Later, once you know which marker genes you care about:
    >>> write_nbhd_cloud(
    ...     adata_aligned,
    ...     "my_dataset_nbhd_cloud",
    ...     compute_gene_nbhds=True,
    ...     gene_list=["Matn1", "Col2a1", "Col1a1"],
    ... )
    """
    from celldega.nbhd import NeighborhoodCollection, alpha_shape_cell_clusters_by_slice
    from celldega.pre import write_gene_shapes_streaming, write_nbhd_cloud_dataset

    dega_files_dir = Path(dega_files_dir)

    # Fail with an actionable message up front rather than a bare KeyError
    # from deep inside alpha_shape_cell_clusters_by_slice -- the whole point
    # of this function is a one-call entry point, so a first-time caller who
    # hasn't set cluster_attr/slice_attr to match their own AnnData should be
    # told exactly what's missing and which kwarg fixes it.
    missing_obs = [
        (name, attr)
        for name, attr in [("cluster_attr", cluster_attr), ("slice_attr", slice_attr)]
        if attr not in adata.obs.columns
    ]
    if z_attr is not None and z_attr not in adata.obs.columns:
        missing_obs.append(("z_attr", z_attr))
    if missing_obs:
        details = ", ".join(f"{param}={attr!r}" for param, attr in missing_obs)
        raise ValueError(
            f"adata.obs is missing column(s) referenced by {details}. Pass the "
            "matching column name(s) explicitly, e.g. "
            "write_nbhd_cloud(adata, ..., cluster_attr='leiden', slice_attr='batch')."
        )
    if "spatial" not in adata.obsm:
        raise ValueError(
            "adata.obsm['spatial'] is required (e.g. from "
            "celldega.align.serial_slices.align_serial_slices)."
        )

    gdf_alpha = alpha_shape_cell_clusters_by_slice(
        adata,
        cluster_attr=cluster_attr,
        slice_attr=slice_attr,
        z_attr=z_attr,
        alphas=alphas,
        meta_cluster=meta_cluster,
        z_jitter=z_jitter,
    )
    nbhd = NeighborhoodCollection.from_gdf(gdf_alpha, nbhd_type="alpha_shape")

    write_nbhd_cloud_dataset(
        adata,
        nbhd,
        dega_files_dir,
        cluster_attr=cluster_attr,
        slice_attr=slice_attr,
        z_attr=z_attr,
    )

    if compute_gene_nbhds:
        if not gene_list:
            raise ValueError(
                "compute_gene_nbhds=True requires an explicit gene_list -- a real "
                "alpha shape per gene is expensive enough that this is deliberately "
                "not auto-selected from the whole gene panel."
            )
        write_gene_shapes_streaming(
            adata,
            gene_list,
            dega_files_dir,
            slice_attr=slice_attr,
            z_attr=z_attr,
            alphas=alphas,
            min_expression=gene_min_expression,
            min_cells=gene_min_cells,
            z_jitter=gene_z_jitter if gene_z_jitter is not None else z_jitter,
            max_cells=gene_max_cells,
            progress_every=gene_progress_every,
        )

    return dega_files_dir
