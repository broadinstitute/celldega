# Usage

This section provides a minimal example of displaying a clustered matrix with Celldega.

## Clustergram `parquet_data`

The `Clustergram` widget accepts a `parquet_data` argument that contains the network encoded as Parquet tables. Using this approach avoids transferring large JSON structures to the browser. You can obtain this dictionary from a [`Matrix`](../python/clust/api.md#celldega.clust.matrix.Matrix.export_viz_parquet) instance using `Matrix.export_viz_parquet()`.

```python
import celldega as dega
import pandas as pd

# Load expression data
df = pd.read_parquet("df_sig.parquet")

# Create and cluster the matrix
mat = dega.clust.Matrix(df, name="demo")
mat.clust()

# Export to Parquet-encoded bytes
pq_data = mat.export_viz_parquet()

# Initialize widget with parquet_data
cgm = dega.viz.Clustergram(parquet_data=pq_data, width=500, height=500)
cgm
```

`Clustergram` can also be initialized directly from a `Matrix` instance which internally uses `export_viz_parquet`. Passing a legacy JSON `network` is now deprecated.
