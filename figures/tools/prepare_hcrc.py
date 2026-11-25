"""Data for the HCRC storyboard (figures/storyboards/hcrc.yaml).

Writes, under figures/build/hcrc/data/:

- ``labels_<set>.meta_cell.parquet`` / ``.meta_cluster.parquet``: the cell labels a
  panel colors cells by (Leiden clusters; goblet sub-clusters by crypt depth; cancer
  sub-types), encoded by Celldega's own Landscape so the browser reads them as a
  notebook widget would.
- ``matrix.zarr``: the clustered Leiden marker Matrix for the Clustergram panel.
- ``facts.json``: camera views (whole tissue, regions) and the numbers the text
  quotes (cell counts, cluster markers), so the storyboard never hard-codes them;
- ``../assets/``: the Jupyter and Scanpy logos, downloaded from the projects'
  repositories, for the panel naming the tools used to sub-cluster.

Run once (about a minute; needs the HCRC AnnData from the Visium HD CRC tutorial in
notebooks/data/visium-hd_data/Visium_HD_Human_Colon_Cancer/):

    python figures/tools/prepare_hcrc.py
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import warnings

import anndata as ad
import numpy as np
import pandas as pd


warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "notebooks/data/visium-hd_data/Visium_HD_Human_Colon_Cancer"
OUT = REPO / "figures/build/hcrc/data"
BASE_URL = (
    "https://raw.githubusercontent.com/SharkieJones/celldega_Visium-HD_hCRC/"
    "refs/heads/main/Visium_HD_Human_Colon_Cancer_2025-10-25_2um"
)

#: Cluster groups (Leiden, from their ranked markers; see the storyboard).
GROUPS = {
    "cancer": ["0", "2", "3", "8", "10"],  # CEACAM5/6, MUC12, NQO1, LCN2/PI3, APCDD1/AXIN2
    "normal_epithelium": ["4"],  # PIGR, FCGBP, MUC2, TFF3
    "immune": ["1", "5", "9", "13", "14"],  # myeloid, IgA/IgG plasma, neutrophil
    "stroma": ["6", "7", "12"],  # fibroblast, endothelial/perivascular, smooth muscle
}
#: Tentative names of the cancer clusters, from their markers (cluster 8: hypoxia and
#: inflammation genes; 0 and 3: proliferation genes; 2: LGR5; 10: Wnt targets).
CANCER_NAMES = {
    "8": "8 hypoxic",
    "0": "0 proliferative",
    "3": "3 proliferative",
    "2": "2 stem-like",
    "10": "10 Wnt-high",
}
CANCER_META = {
    "8": "hypoxic, inflamed (8)",
    "0": "proliferative (0, 3)",
    "3": "proliferative (0, 3)",
    "2": "stem-like, Wnt-high (2, 10)",
    "10": "stem-like, Wnt-high (2, 10)",
}
CANCER_META_COLORS = {
    "hypoxic, inflamed (8)": "#14b8c4",
    "proliferative (0, 3)": "#e08a1e",
    "stem-like, Wnt-high (2, 10)": "#3b5bdb",
}
CANCER_SUBTYPE_COLORS = {
    "8 hypoxic": "#14b8c4",
    "0 proliferative": "#f0a04b",
    "3 proliferative": "#c46a0c",
    "2 stem-like": "#5c7cfa",
    "10 Wnt-high": "#2b44a8",
}
#: Hypoxia-inducible genes (HIF targets) and proliferation genes, for the evidence
#: the text quotes.
HYPOXIA_GENES = [
    "NDRG1",
    "ERO1A",
    "SLC2A1",
    "DDIT4",
    "VEGFA",
    "PDK1",
    "BHLHE40",
    "P4HA1",
    "KDM3A",
    "EGLN3",
    "PFKFB3",
    "ADM",
    "ANKRD37",
    "CA9",
]
PROLIFERATION_GENES = ["MKI67", "TOP2A", "MCM2", "PCNA", "CDK1", "TYMS", "UBE2C", "BIRC5"]
#: Genes the crypt panels show, base to surface.
CRYPT_GENES = ["LGR5", "TFF3", "CA2", "CA1", "GUCA2A"]
#: Yearbook: the cells of one plasma cluster with the most of its top IG gene.
PLASMA = {"cluster": "9", "gene": "IGHG1", "n": 10}
#: Crypt-depth order of the goblet/secretory sub-clusters, base to surface (and
#: their colors), from the tutorial's sub-clustering of cluster 4.
CRYPT_COLORS = "Meta_crypt_clusters_with_vivid_colors.csv"
EXCLUDED_SUB_CLUSTERS = ["3", "6"]


#: Logos of the tools the figure names, from the projects' own repositories.
LOGOS = {
    "scanpy.png": "https://raw.githubusercontent.com/scverse/scanpy/main/docs/_static/img/Scanpy_Logo_RGB.png",
    "jupyter.svg": "https://raw.githubusercontent.com/jupyter/jupyter.github.io/main/assets/homepage/main-logo.svg",
}


def fetch_logos(out: Path) -> None:
    """Download the tool logos into the build's assets folder (once)."""
    from urllib.request import urlopen

    out.mkdir(parents=True, exist_ok=True)
    for name, url in LOGOS.items():
        path = out / name
        if not path.exists():
            with urlopen(url, timeout=30) as response:
                path.write_bytes(response.read())


def bin_microns_per_pixel(tile: str = "115_20", bin_um: float = 2.0) -> float:
    """Microns per image pixel, measured from the data: Visium HD cells are built
    from 2 um bins, so their outlines step in whole bins; the smallest common
    vertex step is one bin."""
    import io
    from urllib.request import urlopen

    url = f"{BASE_URL}/cell_segmentation/cell_tile_{tile}.parquet"
    with urlopen(url, timeout=30) as response:
        cells = pd.read_parquet(io.BytesIO(response.read()))
    steps = []
    for geometry in cells["GEOMETRY"]:
        coords = np.array([list(point) for ring in geometry for point in ring], dtype=float)
        delta = np.abs(np.diff(coords, axis=0)).ravel()
        steps.extend(delta[delta > 0.5])
    values, counts = np.unique(np.round(steps, 1), return_counts=True)
    step = float(values[np.argmax(counts)])
    return round(bin_um / step, 4)


def label_set(name, labels: pd.Series, colors: dict, out: Path) -> None:
    """Encode cell labels as the Landscape widget does (cell -> label; label -> color)."""
    import celldega as dega

    categories = [c for c in colors if c in set(labels.dropna())]
    column = pd.Categorical(labels.where(labels.isin(categories)), categories=categories)
    cells = ad.AnnData(
        obs=pd.DataFrame({name: column}, index=labels.index),
        uns={f"{name}_colors": [colors[c] for c in categories]},
    )
    landscape = dega.viz.Landscape(
        technology="Visium-HD",
        base_url=BASE_URL,
        adata=cells,
        cluster_attr=name,
        name=f"figure_labels_{name}",
    )
    (out / f"labels_{name}.meta_cell.parquet").write_bytes(landscape.meta_cell_parquet)
    (out / f"labels_{name}.meta_cluster.parquet").write_bytes(landscape.meta_cluster_parquet)
    landscape.close()


def view_for(xy: np.ndarray, width: int, height: int, pad: float = 1.1) -> dict:
    """A camera framing points (5th to 95th percentile box) in a width x height panel."""
    lo, hi = np.percentile(xy, 5, axis=0), np.percentile(xy, 95, axis=0)
    span = np.maximum(hi - lo, 1.0) * pad
    zoom = float(np.log2(min(width / span[0], height / span[1])))
    center = (lo + hi) / 2
    return {"target": [float(center[0]), float(center[1])], "zoom": round(zoom, 3)}


def densest(xy: np.ndarray, bin_px: float) -> np.ndarray:
    """The center of the densest bin_px x bin_px square of points."""
    lo = xy.min(axis=0)
    cells = np.floor((xy - lo) / bin_px).astype(int)
    keys, counts = np.unique(cells, axis=0, return_counts=True)
    return lo + (keys[np.argmax(counts)] + 0.5) * bin_px


def view_groups(matrix, level: int, cut: float = 0.5) -> list[list[str]]:
    """Column dendrogram groups of one DIM view, left to right, as the browser cuts
    them (merges below (top height + 0.01) * cut)."""
    from scipy.cluster.hierarchy import fcluster

    view = next(v for v in matrix.views if int(v["level"]) == level)
    linkage = np.asarray(view["col_linkage"], dtype=float)
    threshold = (float(linkage[-1, 2]) + 0.01) * cut
    labels = fcluster(linkage, t=np.nextafter(threshold, 0), criterion="distance")
    columns = [str(c) for c in matrix.data.columns]
    # col_clust[i]: the 1-based position of column i; the browser draws the
    # columns right to left in that order.
    n = len(columns)
    position = {name: n - int(p) for name, p in zip(columns, view["col_clust"], strict=True)}
    groups: dict[int, list[str]] = {}
    for name, label in zip(columns, labels, strict=True):
        groups.setdefault(int(label), []).append(name)
    ordered = sorted(groups.values(), key=lambda g: min(position[n] for n in g))
    return [sorted(g, key=lambda n: position[n]) for g in ordered]


def main() -> None:
    import scanpy as sc

    import celldega as dega

    OUT.mkdir(parents=True, exist_ok=True)
    fetch_logos(OUT.parent / "assets")
    source = ad.read_h5ad(SOURCE / "crc_cluster.h5ad", backed="r")
    leiden = source.obs["leiden"].astype(str)
    categories = list(source.obs["leiden"].cat.categories)
    palette = dict(zip(categories, sc.pl.palettes.default_20, strict=False))

    cells = pd.read_parquet(f"{BASE_URL}/cell_metadata.parquet")
    xy = np.array(cells["geometry"].tolist(), dtype=float)
    cells = pd.DataFrame({"x": xy[:, 0], "y": xy[:, 1]}, index=cells["name"].astype(str))
    cells["leiden"] = leiden.reindex(cells.index)

    # Label sets.
    label_set("leiden", leiden, palette, OUT)
    goblet = ad.read_h5ad(SOURCE / "cluster-4_sub-cluster.h5ad", backed="r")
    depth = pd.read_csv(SOURCE / CRYPT_COLORS)
    depth["cluster"] = depth["cluster"].astype(str)
    depth = depth[~depth["cluster"].isin(EXCLUDED_SUB_CLUSTERS)]
    crypt = goblet.obs["leiden"].astype(str)
    crypt = crypt[~crypt.isin(EXCLUDED_SUB_CLUSTERS)]
    names = {row.cluster: f"{i + 1}. {row.location}" for i, row in enumerate(depth.itertuples())}
    label_set(
        "crypt_depth",
        crypt.map(names).reindex(leiden.index),
        {names[row.cluster]: row.color_hex for row in depth.itertuples()},
        OUT,
    )
    cancer = pd.Series(np.nan, index=leiden.index, dtype=object)
    cancer[leiden == "8"] = "cluster 8 (NDRG1+)"
    cancer[leiden.isin([c for c in GROUPS["cancer"] if c != "8"])] = "other cancer"
    label_set(
        "cancer_type", cancer, {"cluster 8 (NDRG1+)": "#14b8c4", "other cancer": "#8c8c8c"}, OUT
    )

    # The Clustergram's Matrix, with a description.
    matrix = dega.clust.Matrix.read_zarr(SOURCE / "crc_leiden_marker_matrix.zarr")
    matrix.description = (
        "Pseudo-bulk expression of each Leiden cluster (log1p CPM, z-scored per gene); "
        "dot size: fraction of the cluster's cells expressing the gene."
    )
    shutil.rmtree(OUT / "matrix.zarr", ignore_errors=True)
    matrix.write_zarr(OUT / "matrix.zarr")
    markers = matrix._marker_groups()

    tumor = cells[cells["leiden"].isin(GROUPS["cancer"])]

    # Meta-clusters: the column dendrogram groups of the Clustergram's 5-marker view
    # at the figure's cut (a quarter of the tree height).
    meta_groups = view_groups(matrix, level=5, cut=0.25)

    # Cancer clusters re-analyzed on their own: mean expression per cluster,
    # z-scored across the five; markers ranked among them (rank_genes_groups).
    cancer_ids = list(CANCER_NAMES)
    cancer_cells = source[leiden.isin(cancer_ids).to_numpy()].to_memory()
    order = [CANCER_NAMES[c] for c in cancer_ids]
    cancer_cells.obs["subtype"] = pd.Categorical(
        cancer_cells.obs["leiden"].astype(str).map(CANCER_NAMES), categories=order
    )
    cancer_cells.uns["subtype_colors"] = [CANCER_SUBTYPE_COLORS[name] for name in order]
    cancer = dega.clust.Matrix(
        cancer_cells,
        groupby="subtype",
        rank_genes_groups=True,
        col_entity={"entity": "cell", "attr": "subtype"},
        name="hcrc_cancer_subtypes",
        description=(
            "Cancer clusters re-analyzed on their own: mean log-normalized expression "
            "per cluster (z-scored per gene across the five); markers ranked among "
            "them; dot size: fraction of cells expressing."
        ),
    )
    cancer.norm("row", by="zscore")
    cancer.cluster(view="rank_genes_groups", levels=[1, 2, 3, 5, 10, 25])
    shutil.rmtree(OUT / "matrix_cancer.zarr", ignore_errors=True)
    cancer.write_zarr(OUT / "matrix_cancer.zarr")
    cancer_markers = cancer._marker_groups()
    fraction = cancer.size_matrix
    evidence = {
        "hypoxia": fraction.reindex(HYPOXIA_GENES).dropna().round(2).to_dict(orient="index"),
        "proliferation": fraction.reindex(PROLIFERATION_GENES)
        .dropna()
        .round(2)
        .to_dict(orient="index"),
        "stem_wnt": fraction.reindex(["LGR5", "ASCL2", "OLFM4", "AXIN2", "NKD1", "APCDD1"])
        .dropna()
        .round(2)
        .to_dict(orient="index"),
    }
    del cancer_cells

    # Cluster 4's sub-clusters, columns in crypt-depth order (base to surface) and
    # rows in a staircase: each gene placed by the depth where it peaks, surface
    # genes on top, so the crypt reads bottom-left to top-right.
    sub_cells = goblet.to_memory()
    sub_cells = sub_cells[~sub_cells.obs["leiden"].astype(str).isin(EXCLUDED_SUB_CLUSTERS)].copy()
    depth_labels = list(names.values())
    depth_colors = {names[row.cluster]: row.color_hex for row in depth.itertuples()}
    sub_cells.obs["depth"] = pd.Categorical(
        sub_cells.obs["leiden"].astype(str).map(names), categories=depth_labels
    )
    sub_cells.uns["depth_colors"] = [depth_colors[label] for label in depth_labels]
    ranked = dega.clust.Matrix(
        sub_cells, groupby="depth", rank_genes_groups=True, name="hcrc_crypt_ranked"
    )
    sub_markers = ranked._marker_groups()
    rows = list(
        dict.fromkeys(
            [g for label in depth_labels for g in sub_markers.get(label, [])[:4]] + CRYPT_GENES
        )
    )
    rows = [g for g in rows if g in ranked.data.index]
    means = ranked.data.loc[rows, depth_labels].astype(float)
    z = means.sub(means.mean(axis=1), axis=0).div(means.std(axis=1).replace(0, 1), axis=0)
    peak = z.to_numpy().argmax(axis=1)
    peak_value = z.to_numpy().max(axis=1)
    staircase = [
        rows[i] for i in sorted(range(len(rows)), key=lambda i: (-peak[i], -peak_value[i]))
    ]
    z = z.loc[staircase]
    crypt = dega.clust.Matrix(
        z,
        meta_row=pd.DataFrame(
            {"peak": [depth_labels[p] for p in peak[[rows.index(g) for g in staircase]]]},
            index=staircase,
        ),
        meta_col=pd.DataFrame({"depth": depth_labels}, index=depth_labels),
        row_attr=["peak"],
        col_attr=["depth"],
        col_entity={"entity": "cell", "attr": "depth"},
        global_colors=depth_colors,
        name="hcrc_crypt_staircase",
        description=(
            "Cluster 4 sub-clusters, base to surface: mean log-normalized expression "
            "(z-scored per gene); rows are each sub-cluster's top 4 markers plus LGR5, "
            "TFF3, CA2, CA1 and GUCA2A, placed by the depth where they peak."
        ),
    )
    crypt.set_size_matrix(ranked.size_matrix.loc[staircase, depth_labels])
    crypt.cluster()
    shutil.rmtree(OUT / "matrix_crypt.zarr", ignore_errors=True)
    crypt.write_zarr(OUT / "matrix_crypt.zarr")
    depth_order = [row.cluster for row in depth.itertuples()]
    crypt_gene_order = [g for g in staircase if g in CRYPT_GENES][::-1]  # bottom to top
    del sub_cells

    # Yearbook: the plasma cluster's cells with the most of its top IG gene (raw
    # counts from the DegaFiles, as the Yearbook's own gene query ranks them).
    counts = pd.read_parquet(f"{BASE_URL}/cbg/{PLASMA['gene']}.parquet")[PLASMA["gene"]]
    counts.index = cells.index.to_numpy()[counts.index.to_numpy()]
    in_cluster = counts[cells["leiden"].reindex(counts.index) == PLASMA["cluster"]]
    plasma_cells = in_cluster.sort_values(ascending=False).index[: PLASMA["n"]].tolist()
    plasma_means = (
        counts.groupby(cells["leiden"].reindex(counts.index)).sum() / cells["leiden"].value_counts()
    )

    label_set(
        "cancer_meta",
        leiden.map(CANCER_META),
        CANCER_META_COLORS,
        OUT,
    )

    # Camera views and facts.
    normal = cells[cells["leiden"] == "4"][["x", "y"]].to_numpy()
    immune_xy = cells[cells["leiden"].isin(GROUPS["immune"])][["x", "y"]].to_numpy()
    tls = densest(immune_xy, 900)
    crypts = densest(normal, 1200)
    hypoxic = densest(cells[cells["leiden"] == "8"][["x", "y"]].to_numpy(), 1500)
    facts = {
        "microns_per_pixel": bin_microns_per_pixel(),
        "n_cells": int(leiden.notna().sum()),
        "n_clusters": len(categories),
        "groups": GROUPS,
        "cluster_4_markers": markers.get("4", [])[:25],
        "cluster_sizes": leiden.value_counts().to_dict(),
        "crypt_depth": [
            {
                "label": names[row.cluster],
                "sub_cluster": row.cluster,
                "identity": row.identity,
                "markers": row.key_markers,
            }
            for row in depth.itertuples()
        ],
        "views": {
            "tissue": view_for(xy, 600, 520, pad=1.02),
            "normal": view_for(normal, 260, 420, pad=1.0),
            "tumor": view_for(tumor[["x", "y"]].to_numpy(), 400, 420, pad=1.02),
            "tls": {"target": [float(tls[0]), float(tls[1])], "zoom": -1.6},
            "crypts": {"target": [float(crypts[0]), float(crypts[1])], "zoom": -1.4},
            "cluster_8": {"target": [float(hypoxic[0]), float(hypoxic[1])], "zoom": -1.9},
        },
        "markers": {k: markers.get(k, [])[:8] for k in categories},
        "meta_groups": meta_groups,
        "cluster_8_markers": cancer_markers.get(CANCER_NAMES["8"], [])[:50],
        "cancer_markers": {k: v[:10] for k, v in cancer_markers.items()},
        "evidence": evidence,
        "crypt_column_order": depth_order,
        "crypt_gene_order": crypt_gene_order,
        "crypt_rows": staircase,
        "plasma": {
            **PLASMA,
            "cells": plasma_cells,
            "top_counts": in_cluster.sort_values(ascending=False).head(PLASMA["n"]).tolist(),
            "mean_counts": plasma_means.dropna()
            .round(1)
            .sort_values(ascending=False)
            .head(5)
            .to_dict(),
        },
        "palettes": {
            "cancer_meta": CANCER_META_COLORS,
            "cancer_subtype": CANCER_SUBTYPE_COLORS,
            "leiden": palette,
            "crypt_depth": {names[row.cluster]: row.color_hex for row in depth.itertuples()},
            "cancer_type": {"cluster 8 (NDRG1+)": "#14b8c4", "other cancer": "#8c8c8c"},
        },
    }
    (OUT / "facts.json").write_text(json.dumps(facts, indent=2, default=str))
    print(
        json.dumps(
            {
                k: facts[k]
                for k in (
                    "n_cells",
                    "meta_groups",
                    "cancer_markers",
                    "evidence",
                    "crypt_gene_order",
                    "crypt_rows",
                    "plasma",
                )
            },
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
