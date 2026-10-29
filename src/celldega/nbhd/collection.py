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

    The collection only stores data. Computation lives in ``celldega.nbhd``
    functions, which accept the collection wherever they take a neighborhood
    ``GeoDataFrame`` and return plain objects to store back::

        nc = NeighborhoodCollection(gdf=gdf_alpha)
        pop = dega.nbhd.calc_nbhd_by_pop(adata, nc, category="leiden")
        nc.subset(pop.obs_names)  # optional: drop neighborhoods below min_cells
        nc.add_mod("population", pop)
        nc.add_mod("gene", dega.nbhd.calc_nbhd_by_gene(nc, adata=adata))
        nc.add_relation("overlap", dega.nbhd.calc_nbhd_overlap(nc))
        rings = NeighborhoodCollection(
            gdf=dega.nbhd.calc_gradient(nc.gdf.loc[["9"]]), nbhd_type="gradient"
        )
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
                for :meth:`load_transformation_matrix`.
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

    @property
    def geometry(self) -> gpd.GeoDataFrame | None:
        """Neighborhood geometry. Alias of :attr:`gdf` (single source of truth)."""
        return self.gdf

    def to_geodataframe(self) -> gpd.GeoDataFrame:
        """Return the neighborhood geometry, one row per neighborhood.

        This is the hook Celldega uses to accept a collection wherever it takes
        a neighborhood ``GeoDataFrame`` (e.g. ``celldega.nbhd`` functions,
        ``Landscape(nbhd=...)``).
        """
        if self.gdf is None:
            raise ValueError("this collection has no geometry")
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

    def subset(self, obs_names: Any) -> None:
        """Keep only the neighborhoods in ``obs_names``, in that order (in place).

        Modalities, geometry, square relations and memberships are subset
        together so they stay aligned to the observation axis. Use it to drop
        neighborhoods a ``celldega.nbhd`` function filtered out, e.g.
        ``nc.subset(pop.obs_names)`` after ``calc_nbhd_by_pop(..., min_cells=5)``.

        Args:
            obs_names: Neighborhood ids to keep.

        Raises:
            ValueError: If any id is not in the collection.
        """
        from celldega.nbhd._glue import _subset_neighborhood_collection_to_obs

        _subset_neighborhood_collection_to_obs(self, pd.Index(pd.Index(obs_names).astype(str)))

    def add_relation(self, key: str, relation: Any) -> sparse.csr_matrix:
        """Store a square neighborhood-by-neighborhood relation in ``relations[key]``.

        Args:
            key: Name for the relation in ``relations`` (``mdata.obsp``).
            relation: A square ``AnnData`` labelled by neighborhood id on both
                axes (e.g. from ``celldega.nbhd.calc_nbhd_overlap`` or
                ``calc_nbhd_bordering``), aligned to this collection's ``obs``
                by id with absent neighborhoods as zero rows/columns; or a
                matrix already in ``obs`` order.

        Returns:
            The stored sparse relation matrix.

        Raises:
            ValueError: If a matrix is not ``(n_obs, n_obs)``.
        """
        if isinstance(relation, AnnData):
            from celldega.nbhd._glue import _relation_from_square_adata

            matrix = _relation_from_square_adata(relation, self)
        else:
            matrix = sparse.csr_matrix(relation)
            n_obs = len(self.obs)
            if matrix.shape != (n_obs, n_obs):
                raise ValueError(f"relation must have shape ({n_obs}, {n_obs}), got {matrix.shape}")
        self.relations[key] = matrix
        return matrix


__all__ = ["NeighborhoodCollection"]
