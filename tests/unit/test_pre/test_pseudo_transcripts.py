import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from pathlib import Path

path = Path(__file__).resolve().parents[3] / "src" / "celldega" / "pre" / "__init__.py"
source_lines = []
collect = False
with open(path) as fh:
    for line in fh:
        if line.startswith("def make_pseudo_transcript_tiles"):
            collect = True
        if collect:
            if line.startswith("def make_cell_boundaries_ist"):
                break
            source_lines.append(line)

namespace = {}
exec("".join(source_lines), globals(), namespace)
make_pseudo_transcript_tiles = namespace["make_pseudo_transcript_tiles"]


def test_make_pseudo_transcript_tiles(tmp_path) -> None:
    cbg = pd.DataFrame.sparse.from_spmatrix(
        csr_matrix([[1, 0], [2, 3]]),
        index=["spot1", "spot2"],
        columns=["g1", "g2"],
    )

    spots = pd.DataFrame(
        {"name": ["spot1", "spot2"], "geometry": [[5.0, 10.0], [15.0, 20.0]]}
    )
    spot_file = tmp_path / "spot_positions.parquet"
    spots.to_parquet(spot_file)

    out_dir = tmp_path / "tiles"
    bounds = make_pseudo_transcript_tiles(
        cbg=cbg,
        path_spot_positions=str(spot_file),
        path_output=str(out_dir),
        tile_size=10,
        jitter=0.0,
    )

    files = list(out_dir.glob("transcripts_tile_*.parquet"))
    assert files

    total = sum(len(pd.read_parquet(p)) for p in files)
    assert total == cbg.to_numpy().sum()

    assert bounds["x_min"] <= bounds["x_max"]
    assert bounds["y_min"] <= bounds["y_max"]
