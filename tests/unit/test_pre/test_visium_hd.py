import importlib.util
import json
from pathlib import Path
import sys
import types

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[3]
PRE_ROOT = ROOT_DIR / "src" / "celldega" / "pre"

CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)
PREPKG = types.ModuleType("celldega.pre")
PREPKG.__path__ = [str(PRE_ROOT)]
sys.modules.setdefault("celldega.pre", PREPKG)

spec = importlib.util.spec_from_file_location("celldega.pre", PRE_ROOT / "__init__.py")
pre = importlib.util.module_from_spec(spec)
pre.__package__ = "celldega.pre"
sys.modules["celldega.pre"] = pre
spec.loader.exec_module(pre)


def _write_gzip_tsv(path: Path, lines: list[str]) -> None:
    import gzip

    with gzip.open(path, "wt") as f:
        for line in lines:
            f.write(line + "\n")


def test_visium_hd_pipeline(tmp_path: Path):
    data_dir = tmp_path / "dataset"
    binned = data_dir / "binned_outputs" / "square_008um"
    spatial = binned / "spatial"
    spatial.mkdir(parents=True)

    # tissue positions
    df_pos = pd.DataFrame(
        {
            "barcode": ["AA", "BB"],
            "pxl_row_in_fullres": [1.0, 2.0],
            "pxl_col_in_fullres": [3.0, 4.0],
            "in_tissue": [1, 1],
        }
    )
    df_pos.to_parquet(spatial / "tissue_positions.parquet")

    # scalefactors
    with (spatial / "scalefactors_json.json").open("w") as f:
        json.dump({"tissue_hires_scalef": 2.0}, f)

    # image
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="white")
    img.save(spatial / "tissue_hires_image.png")

    # clusters
    clust_dir = binned / "analysis" / "clustering" / "gene_expression_graphclust"
    clust_dir.mkdir(parents=True)
    pd.DataFrame({"Barcode": ["AA", "BB"], "Cluster": [0, 1]}).to_csv(
        clust_dir / "clusters.csv", index=False
    )

    # expression matrix
    ffm = binned / "filtered_feature_bc_matrix"
    ffm.mkdir()
    _write_gzip_tsv(ffm / "features.tsv.gz", ["ENSG1\tGene1", "ENSG2\tGene2"])
    _write_gzip_tsv(ffm / "barcodes.tsv.gz", ["AA", "BB"])
    import gzip
    import shutil

    from scipy.io import mmwrite
    from scipy.sparse import csr_matrix

    mat = csr_matrix([[1, 0], [0, 1]])
    mmwrite(ffm / "matrix.mtx", mat)
    with (ffm / "matrix.mtx").open("rb") as f_in, gzip.open(ffm / "matrix.mtx.gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    (ffm / "matrix.mtx").unlink()

    landscape_dir = tmp_path / "landscape"
    landscape_dir.mkdir()

    # meta cell coordinates
    pre.make_meta_cell_image_coord(
        "Visium-HD",
        str(spatial / "scalefactors_json.json"),
        str(spatial / "tissue_positions.parquet"),
        str(landscape_dir / "cell_metadata.parquet"),
    )
    meta = pd.read_parquet(landscape_dir / "cell_metadata.parquet")
    assert list(meta["name"]) == ["AA", "BB"]

    # gene expression and clusters
    cbg = pre.read_cbg_mtx(str(ffm))
    pre.cluster_gene_expression("Visium-HD", str(landscape_dir), cbg, str(binned))
    pre.create_cluster_and_meta_cluster("Visium-HD", str(landscape_dir), data_dir=str(binned))

    assert (landscape_dir / "cell_clusters" / "cluster.parquet").exists()

    info = pre.get_image_info("Visium-HD", "cells")
    assert info[0]["name"] == "cells"
