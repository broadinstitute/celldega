# Set Module API Reference

The `set` module provides `SetCollection`, the set-level Celldega collection.
A `SetCollection` represents collections that are *literally defined as sets* of
some base element (most commonly cells) with no intrinsic geometry of their
own — clustering results, spatial-domain algorithm outputs (SpaGCN, GraphST,
GASTON, Points2Regions), or manual annotations projected back to cells.

Each observation is one *set*. The defining modality `membership` is a sparse
`sets × cells` incidence matrix, so a set never loses track of exactly which
cells belong to it. Where `DatasetCollection` and `NeighborhoodCollection` make
a *derived* feature (an expression signature, a geometry) first-class,
`SetCollection` makes *membership itself* first-class, and signatures, population
composition, and set-to-set overlap are all derived from it.

```python
import celldega as dega

# Build one SetCollection per clustering "opinion" (the cells define the sets)
clust = dega.set.SetCollection(adata, set_col="leiden", name="leiden")

# Per-set expression signature (pseudobulk). feature_type is only required when
# passing a MuData; for an AnnData it defaults to "gene" -> modality "expression".
clust.calc_signature(adata)
clust.calc_signature(mdata, feature_type="protein")   # protein modality of a MuData

# Per-set cell-type composition (sets x populations)
clust.calc_population(adata, category="cell_type")

# Cross-algorithm comparison: membership IoU between two SetCollections that
# share the same cells (different obs). Rectangular modality on `clust`.
clust_b = dega.set.SetCollection(adata, set_col="spagcn", name="spagcn")
clust.calc_overlap(clust_b)

# Consensus across algorithms: concatenate, self-overlap (square relation),
# make it a clusterable modality, then cut the dendrogram via the Matrix.
combined = dega.set.concat_sets([clust, clust_b])
combined.calc_overlap()                        # -> combined.relations["overlap"]
combined.add_relation_modality("overlap")      # -> combined.mod["overlap_relation"]

clust.write("clusters.h5mu")
loaded = dega.set.SetCollection.read("clusters.h5mu")
```

Hierarchical clustering of any modality is done with the `Matrix` /
`Clustergram` classes, and the resulting dendrogram can be cut into flat labels
with `Matrix.to_cluster` / `Clustergram.to_cluster` (e.g. to define consensus
domains or meta-clusters), which you then attach back to the collection's `obs`.

::: celldega.set
