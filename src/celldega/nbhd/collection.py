"""Neighborhood-level collection schema objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from anndata import AnnData
import geopandas as gpd
from mudata import MuData
import numpy as np
import pandas as pd
from scipy import sparse

from celldega.collection.collection import CelldegaCollection


_TRANSFORM_FILENAME = "micron_to_image_transform.csv"


def _resolve_neighborhood_col(gdf: gpd.GeoDataFrame, nbhd_col: str = "name") -> str:
    if nbhd_col in gdf.columns:
        return nbhd_col
    for candidate in ("neighborhood_id", "nbhd_id"):
        if candidate in gdf.columns:
            return candidate
    raise ValueError(
        f"gdf must include '{nbhd_col}', 'neighborhood_id', or 'nbhd_id' to identify neighborhoods"
    )


def _neighborhood_obs_geometry_from_gdf(
    gdf: gpd.GeoDataFrame,
    nbhd_type: str,
    nbhd_col: str = "name",
) -> tuple[pd.DataFrame, gpd.GeoDataFrame, str]:
    resolved_nbhd_col = _resolve_neighborhood_col(gdf, nbhd_col)
    geometry = gdf.copy()
    geometry.index = geometry[resolved_nbhd_col].astype(str)

    if not geometry.index.is_unique:
        raise ValueError(f"Neighborhood IDs in '{resolved_nbhd_col}' must be unique")

    obs = pd.DataFrame(geometry.drop(columns="geometry", errors="ignore"))
    obs.index = geometry.index.copy()
    obs.index.name = "neighborhood_id"

    if "neighborhood_id" not in obs.columns:
        obs.insert(0, "neighborhood_id", obs.index)
    if "neighborhood_type" not in obs.columns:
        obs["neighborhood_type"] = nbhd_type
    if "method" not in obs.columns:
        obs["method"] = nbhd_type

    geom = geometry.geometry
    if "area" not in obs.columns:
        obs["area"] = geom.area
    if "area_um2" not in obs.columns:
        obs["area_um2"] = geom.area
    if "centroid_x" not in obs.columns:
        obs["centroid_x"] = geom.centroid.x
    if "centroid_y" not in obs.columns:
        obs["centroid_y"] = geom.centroid.y

    return obs, geometry, resolved_nbhd_col


class NeighborhoodCollection(CelldegaCollection):
    """Neighborhood-level or spatial-region MuData collection.

    Observations are neighborhoods or spatial regions. Feature modalities live in
    ``mod`` and global observation relations live in ``relations``/``mdata.obsp``.
    Geometry is kept as a live ``GeoDataFrame`` in memory; durable geometry
    storage can be layered on later with WKB columns or GeoParquet sidecars.
    """

    def __init__(
        self,
        obs: pd.DataFrame | None = None,
        mod: dict[str, AnnData] | None = None,
        mdata: MuData | None = None,
        gdf: gpd.GeoDataFrame | None = None,
        nbhd_type: str | None = None,
        data_dir: str | None = None,
        source: str | dict[str, Any] | None = None,
        name: str | None = None,
        meta: dict[str, Any] | None = None,
        nbhd_col: str = "name",
        geometry: gpd.GeoDataFrame | None = None,
        relations: dict[str, sparse.spmatrix] | None = None,
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
        memberships: dict[str, sparse.spmatrix] | None = None,
        transformation_matrix: Any | None = None,
    ) -> None:
        """Build a neighborhood / spatial-region collection.

        The observation axis (one row per neighborhood) is established from a
        neighborhood ``GeoDataFrame`` (``gdf`` — the usual path, produced by
        ``alpha_shape`` / ``generate_hextile`` / etc.), from an explicit ``obs``
        table paired with ``geometry``, or from a pre-built ``mdata``. When built
        from ``gdf``, per-neighborhood ``area``/``area_um2`` and centroid columns
        are derived and the neighborhood-id column is normalized.

        Args:
            obs: Pre-built neighborhood observation table (use with ``geometry``,
                not with ``gdf``).
            mod: Feature-space modalities to attach up front.
            mdata: Pre-built ``MuData`` to wrap (e.g. from ``read``).
            gdf: Neighborhood geometry; each row becomes an observation. Mutually
                exclusive with ``obs``/``geometry``.
            nbhd_type: Label for how the neighborhoods were made (e.g.
                ``"hextile"``, ``"alpha_shape"``); defaults to ``"neighborhood"``.
            data_dir: DegaFiles/instrument directory used as the default source
                for the transcript- and transform-loading methods.
            source: Source descriptor recorded in provenance.
            name: Optional collection name.
            meta: Extra metadata merged into ``uns["celldega"]``.
            nbhd_col: Column in ``gdf`` identifying each neighborhood (falls back
                to ``neighborhood_id`` / ``nbhd_id``).
            geometry: Neighborhood geometry paired with an explicit ``obs``
                (alternative to ``gdf``).
            relations: Square neighborhood-by-neighborhood matrices for
                ``mdata.obsp``.
            provenance: Free-form provenance metadata.
            uns: Extra Celldega metadata.
            memberships: Membership matrices (e.g. cell-to-neighborhood); kept in
                memory only (not persisted by ``write``).
            transformation_matrix: Optional micron-to-pixel affine (see
                :meth:`set_transformation_matrix`).

        Raises:
            ValueError: If ``gdf`` is combined with ``obs`` or ``geometry``.
        """
        if gdf is not None:
            if obs is not None:
                raise ValueError("obs cannot be provided when gdf is provided")
            if geometry is not None:
                raise ValueError("geometry cannot be provided separately when gdf is provided")
            resolved_nbhd_type = nbhd_type or "neighborhood"
            obs, geometry, nbhd_col = _neighborhood_obs_geometry_from_gdf(
                gdf,
                nbhd_type=resolved_nbhd_type,
                nbhd_col=nbhd_col,
            )
            self.gdf = geometry.copy()
        else:
            resolved_nbhd_type = nbhd_type or "neighborhood"
            self.gdf = geometry.copy() if geometry is not None else None

        self.nbhd_type = resolved_nbhd_type
        self.data_dir = data_dir
        self.source = source
        self.name = name
        self.meta = meta or {}
        self.nbhd_col = nbhd_col
        self.memberships = memberships or {}

        collection_provenance = {"source": source} if source is not None else {}
        collection_provenance.update(provenance or {})
        collection_uns = {"name": name, **self.meta}
        collection_uns.update(uns or {})

        super().__init__(
            obs=obs,
            mod=mod,
            mdata=mdata,
            relations=relations,
            provenance=collection_provenance,
            uns=collection_uns,
            collection_type="neighborhood",
            obs_entity_type="neighborhood",
        )

        # Micron-to-pixel affine. Set explicitly here, restored from a reloaded
        # MuData's uns, or loaded later from DegaFiles via
        # ``load_transformation_matrix``. Mirrored into uns so it round-trips.
        if transformation_matrix is not None:
            self.set_transformation_matrix(transformation_matrix)
        elif "transformation_matrix" in self.uns:
            self.transformation_matrix = np.asarray(self.uns["transformation_matrix"], dtype=float)
        else:
            self.transformation_matrix = None

    @classmethod
    def from_gdf(
        cls,
        gdf: gpd.GeoDataFrame,
        nbhd_type: str = "neighborhood",
        **kwargs: Any,
    ) -> NeighborhoodCollection:
        """Create a ``NeighborhoodCollection`` from a neighborhood GeoDataFrame.

        Convenience wrapper for ``NeighborhoodCollection(gdf=gdf,
        nbhd_type=nbhd_type, **kwargs)``.

        Args:
            gdf: Neighborhood geometry; each row becomes an observation.
            nbhd_type: Label for how the neighborhoods were made.
            **kwargs: Forwarded to the constructor.

        Returns:
            A new ``NeighborhoodCollection``.
        """
        return cls(gdf=gdf, nbhd_type=nbhd_type, **kwargs)

    def calc_gradient(
        self,
        obs_name: str,
        direction: str = "both",
        bin_width: float = 10,
        max_dist: float = 50,
        nbhd_type: str = "gradient",
        *,
        technology: str | None = None,
        scale_um_per_pixel: float | None = None,
        is_pixel_space: bool = False,
        clip_boundary: Any | None = None,
        clip_reference: Any | None = None,
        clip_alpha: float = 100,
        **kwargs: Any,
    ) -> NeighborhoodCollection:
        """Calculate a gradient collection around one neighborhood in this collection.

        Picks the neighborhood identified by ``obs_name`` and grows fixed-width
        bands outward from and/or inward into it (see
        the gradient engine), returning a **new**
        gradient ``NeighborhoodCollection`` — one neighborhood (observation) per
        ring, ordered inner-most to outer-most. From there the usual
        ``calc_nbhd_by_*`` methods summarize cell composition or expression per
        ring, profiling how the tissue changes with distance from that
        neighborhood's boundary. A gradient is therefore always anchored to a
        concrete neighborhood (e.g. a per-cluster alpha shape) rather than a
        loose geometry.

        Args:
            obs_name: Identifier of the source neighborhood to anchor the gradient
                on — matched against the collection's observation index (and, as a
                fallback, the ``name`` column). Its geometry is the ROI.
            direction: ``"outward"``, ``"inward"``, or ``"both"`` (default).
            bin_width: Width of each ring in microns (default ``10``).
            max_dist: Maximum distance from the neighborhood boundary in microns
                (default ``50``).
            nbhd_type: Label recorded on the new collection (default
                ``"gradient"``).
            technology: Imaging platform used to look up ``scale_um_per_pixel``
                for pixel-space geometry (e.g. ``"Xenium"``).
            scale_um_per_pixel: Microns per pixel; required (directly or via
                ``technology``) when ``is_pixel_space=True``.
            is_pixel_space: ``True`` if this collection's geometry is in pixel
                units; ``False`` (default) if already in microns.
            clip_boundary: Optional precomputed tissue boundary to clip outward
                rings to (takes precedence over ``clip_reference``).
            clip_reference: Optional source of cell positions (an ``AnnData``,
                a ``GeoDataFrame``/``GeoSeries`` of cells, or an ``(N, 2)``
                array) from which a tissue alpha shape is computed on the fly to
                clip outward rings.
            clip_alpha: Inverse-alpha for the on-the-fly alpha shape (default
                ``100``).
            **kwargs: Forwarded to the new :class:`NeighborhoodCollection`
                (e.g. ``name``, ``data_dir``).

        Returns:
            A new ``NeighborhoodCollection`` whose observations are the gradient
            rings around ``obs_name``.

        Raises:
            ValueError: If this collection has no geometry.
            KeyError: If ``obs_name`` is not found.

        Examples:
            >>> # nbhd holds one alpha-shape neighborhood per cell-type cluster
            >>> grad_nbhd = nbhd.calc_gradient(obs_name="9", direction="both",
            ...                                bin_width=50, max_dist=200)
            >>> grad_nbhd.calc_nbhd_by_gene(adata, by="cell")
            >>> grad_nbhd.obs[["direction", "dist_start_um"]].head(3)
        """
        from celldega.nbhd.gradient import _calc_gradient

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate a gradient")

        gdf = self.gdf
        key = str(obs_name)
        mask = gdf.index.astype(str) == key
        if not mask.any() and self.nbhd_col in gdf.columns:
            mask = gdf[self.nbhd_col].astype(str) == key
        if not mask.any():
            available = list(gdf.index.astype(str)[:10])
            raise KeyError(
                f"obs_name {obs_name!r} not found in this collection. "
                f"Available (first 10): {available}"
            )

        roi_geometry = gdf.loc[mask].geometry.unary_union

        # Carry this collection's micron->pixel transform forward so the gradient
        # rings can be rendered with ``to_pixel_gdf()``.
        if self.transformation_matrix is not None and "transformation_matrix" not in kwargs:
            kwargs["transformation_matrix"] = self.transformation_matrix

        gdf_rings = _calc_gradient(
            roi_geometry,
            direction=direction,
            bin_width=bin_width,
            max_dist=max_dist,
            technology=technology,
            scale_um_per_pixel=scale_um_per_pixel,
            is_pixel_space=is_pixel_space,
            clip_boundary=clip_boundary,
            clip_reference=clip_reference,
            clip_alpha=clip_alpha,
        )
        return type(self)(gdf=gdf_rings, nbhd_type=nbhd_type, **kwargs)

    @property
    def geometry(self) -> gpd.GeoDataFrame | None:
        """Neighborhood geometry. Alias of :attr:`gdf` (single source of truth)."""
        return self.gdf

    def set_transformation_matrix(self, matrix: Any) -> np.ndarray:
        """Set the micron-to-pixel affine transformation matrix.

        Args:
            matrix: Affine mapping micron coordinates (the geometry's native
                space) to image/pixel space, as a ``(2, 3)`` or ``(3, 3)`` array.

        Returns:
            The stored matrix as a float ``ndarray``. It is also mirrored into
            ``uns`` so it round-trips through ``write``/``read``.
        """
        self.transformation_matrix = np.asarray(matrix, dtype=float)
        self.uns["transformation_matrix"] = self.transformation_matrix.tolist()
        return self.transformation_matrix

    def load_transformation_matrix(self, data_dir: str | None = None) -> np.ndarray:
        """Load the micron-to-pixel transformation matrix from DegaFiles.

        Reads ``micron_to_image_transform.csv`` and stores it via
        :meth:`set_transformation_matrix`. Later this matrix can instead be
        supplied directly (e.g. from SpatialData).

        Args:
            data_dir: Directory containing the transform CSV; defaults to
                ``self.data_dir``.

        Returns:
            The loaded matrix as a float ``ndarray``.

        Raises:
            ValueError: If no ``data_dir`` is available.
        """
        resolved_data_dir = data_dir if data_dir is not None else self.data_dir
        if resolved_data_dir is None:
            raise ValueError("data_dir is required to load a transformation matrix")
        path = Path(resolved_data_dir) / _TRANSFORM_FILENAME
        matrix = pd.read_csv(path, header=None, sep=" ").values
        return self.set_transformation_matrix(matrix)

    def to_pixel_gdf(self) -> gpd.GeoDataFrame:
        """Return the neighborhood geometry ready for pixel-space visualization.

        Adds a ``geometry_pixel`` column (micron geometry transformed to image
        space via the stored transformation matrix) and leaves the original
        micron ``geometry`` intact. The result can be passed straight to
        ``Landscape(nbhd=...)``, which renders ``geometry_pixel`` directly when
        present rather than applying its own transform.

        Returns:
            A copy of ``gdf`` with an added ``geometry_pixel`` column.

        Raises:
            ValueError: If geometry or the transformation matrix is not set.
        """
        from shapely.affinity import affine_transform

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to produce pixel geometry")
        if self.transformation_matrix is None:
            raise ValueError(
                "transformation_matrix is not set; pass it to the constructor, call "
                "set_transformation_matrix(), or load_transformation_matrix(data_dir=...)"
            )

        a, b, tx = self.transformation_matrix[0]
        c, d, ty = self.transformation_matrix[1]
        coeffs = [a, b, c, d, tx, ty]

        gdf = self.gdf.copy()
        gdf["geometry_pixel"] = gdf.geometry.apply(lambda geom: affine_transform(geom, coeffs))
        return gdf

    def calc_nbhd_by_pop(
        self,
        adata: AnnData,
        category: str = "leiden",
        modality_name: str = "population",
        output: str = "proportion",
        min_cells: int = 5,
        drop_missing: bool = True,
    ) -> None:
        """Calculate a neighborhood-by-population modality and attach it to ``self.mod``.

        Spatially assigns cells to neighborhoods and, per neighborhood, counts
        cells per ``category`` value to form a neighborhood (rows) by population
        (columns) feature matrix.

        Args:
            adata: Cell-level ``AnnData`` with spatial coordinates in
                ``obsm["spatial"]`` and ``category`` in ``obs``.
            category: ``obs`` column naming the population/cell-type/cluster.
            modality_name: Key for the modality in ``self.mod``.
            output: ``"proportion"`` (within-neighborhood fractions) or
                ``"counts"``.
            min_cells: Minimum cells for a neighborhood to be included.
            drop_missing: When ``True`` (default), neighborhoods with fewer than
                ``min_cells`` cells are removed from the collection entirely so
                the observation axis only contains neighborhoods with data. When
                ``False``, the collection keeps all neighborhoods and the
                modality is attached with zero-filled rows for those that fall
                below ``min_cells``.

        Returns:
            ``None`` — the modality is attached to ``self.mod[modality_name]``.
        """
        from celldega.nbhd.neighborhoods import (
            _calc_nbhd_by_pop,
            _subset_neighborhood_collection_to_obs,
        )

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate a population modality")

        modality = _calc_nbhd_by_pop(
            adata,
            self.gdf,
            category=category,
            nbhd_col=self.nbhd_col,
            min_cells=min_cells,
            output=output,
        )
        if drop_missing:
            _subset_neighborhood_collection_to_obs(self, pd.Index(modality.obs_names.astype(str)))
        self.add_mod(modality_name, modality, var_entity_type="cell_population")

    def calc_nbhd_by_gene(
        self,
        adata: AnnData | None = None,
        by: str = "cell",
        modality_name: str | None = None,
        min_cells: int = 1,
        data_dir: str | None = None,
        drop_missing: bool = True,
    ) -> None:
        """Calculate a neighborhood-by-gene modality and attach it to ``self.mod``.

        Builds per-neighborhood gene expression — mean expression of contained
        cells (``by="cell"``) or transcript counts (``by="cell-free"``).

        Args:
            adata: Cell-level ``AnnData`` (required when ``by="cell"``); needs
                spatial coordinates in ``obsm["spatial"]``.
            by: ``"cell"`` for cell-derived mean expression or ``"cell-free"``
                for transcript counts.
            modality_name: Key for the modality; defaults to ``"gene"``
                (cell-derived) or ``"gene_cell_free"`` (transcript-derived).
            min_cells: Minimum cells/transcripts for a neighborhood to be kept.
            data_dir: Transcript directory for ``by="cell-free"``; defaults to
                ``self.data_dir``.
            drop_missing: When ``True`` (default), neighborhoods with fewer than
                ``min_cells`` cells (or transcripts) are removed from the
                collection entirely. When ``False``, the collection keeps all
                neighborhoods and the modality is attached with zero-filled rows
                for those that fall below ``min_cells``.

        Returns:
            ``None`` — the modality is attached to ``self.mod``.

        Raises:
            ValueError: If ``adata`` is missing for ``by="cell"``, or ``data_dir``
                is missing for ``by="cell-free"``.
        """
        from celldega.nbhd.neighborhoods import (
            _calc_nbhd_by_gene,
            _subset_neighborhood_collection_to_obs,
        )

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate a gene modality")

        resolved_data_dir = data_dir if data_dir is not None else self.data_dir
        if by == "cell" and adata is None:
            raise ValueError("adata is required when by='cell'")
        if by == "cell-free" and resolved_data_dir is None:
            raise ValueError("data_dir is required when by='cell-free'")

        modality = _calc_nbhd_by_gene(
            self.gdf,
            by=by,
            adata=adata,
            data_dir=resolved_data_dir,
            nbhd_col=self.nbhd_col,
            min_cells=min_cells,
        )
        if drop_missing:
            _subset_neighborhood_collection_to_obs(self, pd.Index(modality.obs_names.astype(str)))
        self.add_mod(
            modality_name or ("gene" if by == "cell" else "gene_cell_free"),
            modality,
            var_entity_type="gene",
        )

    def calc_nbhd_overlap(
        self,
        metric: str = "iou",
        key: str = "overlap",
        category: str = "leiden",
    ) -> sparse.spmatrix:
        """Calculate a neighborhood-by-neighborhood overlap relation.

        Computes pairwise geometric overlap between neighborhoods and stores the
        square matrix in ``relations[key]`` (``mdata.obsp``).

        Args:
            metric: Overlap metric — ``"iou"`` (intersection over union),
                ``"ioa"`` (intersection over the row neighborhood's area), or
                ``"intersection"`` (raw intersection area).
            key: Name for the relation in ``relations``.
            category: Neighborhood category recorded on the computed result.

        Returns:
            The stored sparse relation matrix.

        Raises:
            ValueError: If geometry is not set.
        """
        from celldega.nbhd.neighborhoods import _calc_nbhd_overlap, _relation_from_square_adata

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate an overlap relation")

        relation_adata = _calc_nbhd_overlap(
            self.gdf[[self.nbhd_col, "geometry"]],
            metric=metric,
            name_col=self.nbhd_col,
            category=category,
        )
        relation = _relation_from_square_adata(relation_adata, self)
        self.relations[key] = relation
        return relation

    def calc_nbhd_bordering(
        self,
        metric: str = "border_ratio",
        key: str = "bordering",
        category: str = "leiden",
    ) -> sparse.spmatrix:
        """Calculate a neighborhood-by-neighborhood bordering relation.

        Computes pairwise border relationships between neighborhoods and stores
        the square matrix in ``relations[key]`` (``mdata.obsp``).

        Args:
            metric: Border metric (e.g. ``"border_ratio"``, ``"binary"``).
            key: Name for the relation in ``relations``.
            category: Neighborhood category recorded on the computed result.

        Returns:
            The stored sparse relation matrix.

        Raises:
            ValueError: If geometry is not set.
        """
        from celldega.nbhd.neighborhoods import _calc_nbhd_bordering, _relation_from_square_adata

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate a bordering relation")

        relation_adata = _calc_nbhd_bordering(
            self.gdf[[self.nbhd_col, "geometry"]],
            metric=metric,
            name_col=self.nbhd_col,
            category=category,
        )
        relation = _relation_from_square_adata(relation_adata, self)
        self.relations[key] = relation
        return relation

    def calc_nbhd_transcript_assignment(
        self,
        data_dir: str | None = None,
    ) -> None:
        """Add per-neighborhood transcript-assignment columns to ``obs``.

        From ``transcripts.parquet`` in ``data_dir``, adds three ``obs`` columns
        (on the underlying MuData) for each neighborhood:

        - ``total_transcripts`` — transcripts falling inside the neighborhood.
        - ``unassigned_transcripts`` — those with ``cell_id == "UNASSIGNED"``.
        - ``transcript_assignment_proportion`` — assigned / total (``0.0`` when
          the neighborhood has no transcripts).

        Assumption: the transcript-to-cell assignment is **not computed here** —
        it must already be present in the instrument data, with unassigned
        transcripts marked by the ``"UNASSIGNED"`` sentinel (Xenium convention).
        Only transcripts are needed — no ``adata`` or cell polygons.

        Args:
            data_dir: Directory containing ``transcripts.parquet``; defaults to
                ``self.data_dir``.

        Returns:
            ``None`` — the three columns are added to ``self.obs``.

        Raises:
            ValueError: If geometry or a usable ``data_dir`` is missing, or the
                transcripts lack a ``cell_id`` column. A complete absence of the
                ``"UNASSIGNED"`` sentinel only warns.
        """
        from celldega.nbhd.neighborhoods import _calc_nbhd_transcript_assignment
        from celldega.nbhd.utils import _get_gdf_trx

        if self.gdf is None:
            raise ValueError("gdf or geometry is required to calculate transcript assignment")
        resolved_data_dir = data_dir if data_dir is not None else self.data_dir
        if resolved_data_dir is None:
            raise ValueError("data_dir is required to calculate transcript assignment")

        gdf_trx = _get_gdf_trx(resolved_data_dir)
        stats = _calc_nbhd_transcript_assignment(self.gdf, self.nbhd_col, gdf_trx)
        stats = stats.reindex(self.obs.index.astype(str))
        obs = self.obs.copy()
        for col in stats.columns:
            obs[col] = stats[col].to_numpy()
        self.obs = obs


__all__ = ["NeighborhoodCollection"]
